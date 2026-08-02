from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from termproof.session import (
    KEYS,
    TerminalSession,
    asciinema_rec_command,
    recorded_command,
)


def _make_session(tmp: str) -> TerminalSession:
    return TerminalSession(
        argv=["true"],
        cast_path=Path(tmp) / "session.cast",
        cwd=None,
        env={},
        cols=80,
        rows=24,
    )


class RecordedCommandTest(unittest.TestCase):
    def test_builds_status_capturing_wrapper(self) -> None:
        exit_path = Path("/tmp/session.exitcode")

        command = recorded_command(["echo", "hi"], exit_path)

        quoted_exit = str(exit_path.resolve())
        self.assertTrue(command.startswith("echo hi; "))
        self.assertIn("__termproof_status=$?;", command)
        self.assertIn(f"printf '%s' \"$__termproof_status\" > {quoted_exit};", command)
        self.assertTrue(command.endswith('exit "$__termproof_status"'))

    def test_shell_quotes_arguments_with_spaces_and_specials(self) -> None:
        command = recorded_command(["ls", "-la", "my dir", "$HOME"], Path("/tmp/e.exitcode"))

        # shlex.join must quote the space-containing and dollar-sign arguments so
        # they are passed literally rather than expanded by the wrapper shell.
        self.assertIn("ls -la 'my dir' '$HOME';", command)

    def test_quotes_exit_code_path_with_spaces(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            exit_path = Path(tmp) / "a dir" / "run.exitcode"

            command = recorded_command(["true"], exit_path)

            self.assertIn(f"'{exit_path.resolve()}'", command)


class AsciinemaRecCommandTest(unittest.TestCase):
    def test_composes_full_recording_command(self) -> None:
        cast_path = Path("/tmp/out.cast")
        exit_path = Path("/tmp/out.exitcode")

        with mock.patch(
            "termproof.session.shutil.which", return_value="/usr/bin/asciinema"
        ):
            command = asciinema_rec_command(["true"], cast_path, exit_path, 100, 30)

        self.assertEqual(
            [
                "/usr/bin/asciinema",
                "rec",
                "--overwrite",
                "--stdin",
                "--quiet",
                "--cols",
                "100",
                "--rows",
                "30",
                "--command",
                recorded_command(["true"], exit_path),
                str(cast_path),
            ],
            command,
        )

    def test_raises_when_asciinema_missing(self) -> None:
        with mock.patch("termproof.session.shutil.which", return_value=None):
            with self.assertRaises(RuntimeError):
                asciinema_rec_command(["true"], Path("/tmp/x.cast"), Path("/tmp/x.exitcode"), 80, 24)


class ExitCodeResolutionTest(unittest.TestCase):
    def test_sidecar_file_takes_priority_over_child_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            session = _make_session(tmp)
            session.exit_code_path.write_text("0", encoding="utf-8")
            session.child = mock.Mock(closed=True, exitstatus=1, signalstatus=None)

            self.assertEqual(0, session._collect_exit_code())

    def test_sidecar_nonzero_value_is_parsed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            session = _make_session(tmp)
            session.exit_code_path.write_text("42\n", encoding="utf-8")
            session.child = mock.Mock(closed=True, exitstatus=None, signalstatus=None)

            self.assertEqual(42, session._collect_exit_code())

    def test_falls_back_to_child_exitstatus_when_no_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            session = _make_session(tmp)
            session.child = mock.Mock(closed=True, exitstatus=3, signalstatus=None)

            self.assertEqual(3, session._collect_exit_code())

    def test_falls_back_to_signal_offset_when_no_exitstatus(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            session = _make_session(tmp)
            session.child = mock.Mock(closed=True, exitstatus=None, signalstatus=9)

            self.assertEqual(137, session._collect_exit_code())

    def test_returns_none_when_no_status_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            session = _make_session(tmp)
            session.child = mock.Mock(closed=True, exitstatus=None, signalstatus=None)

            self.assertIsNone(session._collect_exit_code())

    def test_empty_sidecar_falls_back_to_child_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            session = _make_session(tmp)
            session.exit_code_path.write_text("   ", encoding="utf-8")
            session.child = mock.Mock(closed=True, exitstatus=5, signalstatus=None)

            self.assertEqual(5, session._collect_exit_code())

    def test_cached_exit_code_is_returned_without_touching_child(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            session = _make_session(tmp)
            session.exit_code = 7
            child = mock.Mock(closed=False, exitstatus=1, signalstatus=None)
            session.child = child

            self.assertEqual(7, session._collect_exit_code())
            child.close.assert_not_called()


class ReadRecordedExitCodeTest(unittest.TestCase):
    def test_missing_file_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            session = _make_session(tmp)

            self.assertIsNone(session._read_recorded_exit_code())

    def test_reads_and_strips_value(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            session = _make_session(tmp)
            session.exit_code_path.write_text("  13  \n", encoding="utf-8")

            self.assertEqual(13, session._read_recorded_exit_code())

    def test_empty_file_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            session = _make_session(tmp)
            session.exit_code_path.write_text("", encoding="utf-8")

            self.assertIsNone(session._read_recorded_exit_code())


class KeyPressTest(unittest.TestCase):
    def test_named_key_sends_escape_sequence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            session = _make_session(tmp)
            session.child = mock.Mock()

            session.press("up")

            session.child.send.assert_called_once_with(KEYS["up"])

    def test_key_name_is_case_insensitive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            session = _make_session(tmp)
            session.child = mock.Mock()

            session.press("ENTER")

            session.child.send.assert_called_once_with("\r")

    def test_ctrl_prefix_uses_sendcontrol(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            session = _make_session(tmp)
            session.child = mock.Mock()

            session.press("Ctrl-C")

            session.child.sendcontrol.assert_called_once_with("c")
            session.child.send.assert_not_called()

    def test_unknown_key_raises_key_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            session = _make_session(tmp)
            session.child = mock.Mock()

            with self.assertRaises(KeyError):
                session.press("f13")


class SendHelpersTest(unittest.TestCase):
    def test_send_line_appends_carriage_return(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            session = _make_session(tmp)
            session.child = mock.Mock()

            session.send_line("hello")

            session.child.send.assert_called_once_with("hello\r")

    def test_send_text_passes_text_through(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            session = _make_session(tmp)
            session.child = mock.Mock()

            session.send_text("abc")

            session.child.send.assert_called_once_with("abc")

    def test_send_eof_delegates_to_child(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            session = _make_session(tmp)
            session.child = mock.Mock()

            session.send_eof()

            session.child.sendeof.assert_called_once_with()

    def test_operations_before_start_raise_runtime_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            session = _make_session(tmp)

            with self.assertRaises(RuntimeError):
                session.send_text("x")


if __name__ == "__main__":
    unittest.main()
