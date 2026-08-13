from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from termproof.builtin_session import PexpectAsciinemaBackend, PexpectBackend
from termproof.screen import replay_cast
from termproof.session import TerminalSession, shell_recorded_command


class ShellRecordedCommandTest(unittest.TestCase):
    def test_the_child_status_is_written_where_the_session_can_read_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            exit_path = Path(tmp) / "session.exitcode"
            argv = shell_recorded_command(["sh", "-c", "exit 7"], exit_path)
            self.assertEqual(3, len(argv))
            self.assertEqual("-c", argv[1])
            self.assertIn(str(exit_path.resolve()), argv[2])


class InternalRecorderTest(unittest.TestCase):
    """The default backend, driving a real child over a real pty."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.cast = Path(self._tmp.name) / "session.cast"

    def _run(self, argv: list[str]) -> TerminalSession:
        backend = PexpectBackend()
        with backend.create_session(argv, self.cast, None, {}, 80, 24) as session:
            session.wait_for_exit(10.0)
        return session

    def test_it_writes_a_cast_without_the_asciinema_cli(self) -> None:
        self._run(["sh", "-c", "printf 'hello\\n'"])
        self.assertTrue(self.cast.is_file())
        header = json.loads(self.cast.read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(2, header["version"])
        self.assertEqual(80, header["width"])
        self.assertEqual(24, header["height"])

    def test_the_cast_replays_to_what_the_child_printed(self) -> None:
        self._run(["sh", "-c", "printf 'hello world\\n'"])
        text, cols, rows = replay_cast(self.cast)
        self.assertIn("hello world", text)
        self.assertEqual((80, 24), (cols, rows))

    def test_colour_survives_into_the_cast(self) -> None:
        self._run(["sh", "-c", "printf '\\033[31mred\\033[0m\\n'"])
        events = self.cast.read_text(encoding="utf-8").splitlines()[1:]
        self.assertTrue(any("\x1b[31m" in json.loads(line)[2] for line in events if line))

    def test_the_child_exit_code_is_the_child_s_not_the_shell_s(self) -> None:
        session = self._run(["sh", "-c", "exit 7"])
        self.assertEqual(7, session.exit_code)

    def test_a_zero_exit_is_reported_as_zero(self) -> None:
        self.assertEqual(0, self._run(["sh", "-c", "exit 0"]).exit_code)

    def test_input_is_recorded_as_an_input_event(self) -> None:
        backend = PexpectBackend()
        with backend.create_session(["cat"], self.cast, None, {}, 80, 24) as session:
            session.send_line("typed")
            session.wait_for_text("typed", 10.0)
            session.send_eof()
            session.wait_for_exit(10.0)
        kinds = [json.loads(line)[1] for line in self.cast.read_text(encoding="utf-8").splitlines()[1:] if line]
        self.assertIn("i", kinds)
        self.assertIn("o", kinds)

    def test_events_are_ordered_in_time(self) -> None:
        self._run(["sh", "-c", "printf 'a'; sleep 0.05; printf 'b'"])
        stamps = [json.loads(line)[0] for line in self.cast.read_text(encoding="utf-8").splitlines()[1:] if line]
        self.assertEqual(stamps, sorted(stamps))


class BackendSelectionTest(unittest.TestCase):
    def test_the_default_backend_records_internally(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            session = PexpectBackend().create_session(["true"], Path(tmp) / "s.cast", None, {}, 80, 24)
            self.assertEqual("internal", session.recorder)

    def test_the_asciinema_backend_asks_for_the_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            session = PexpectAsciinemaBackend().create_session(
                ["true"], Path(tmp) / "s.cast", None, {}, 80, 24
            )
            self.assertEqual("asciinema", session.recorder)

    def test_an_unknown_recorder_is_rejected_at_construction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                TerminalSession(["true"], Path(tmp) / "s.cast", None, {}, 80, 24, recorder="magic")


if __name__ == "__main__":
    unittest.main()
