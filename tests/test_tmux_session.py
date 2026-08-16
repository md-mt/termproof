from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from termproof.tmux_session import KEYS, TmuxBackend, TmuxSession

requires_tmux = unittest.skipUnless(shutil.which("tmux"), "tmux is not installed")


def _pexpect_available() -> bool:
    return importlib.util.find_spec("pexpect") is not None


class KeyMapTest(unittest.TestCase):
    @unittest.skipUnless(_pexpect_available(), "pexpect is not installed")
    def test_every_named_key_the_pty_session_knows_has_a_tmux_name(self) -> None:
        """A key the pty backend accepts must not silently no-op under tmux."""
        from termproof.session import KEYS as PTY_KEYS

        self.assertEqual(sorted(PTY_KEYS), sorted(KEYS))


@requires_tmux
class TmuxSessionTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.cast = Path(self._tmp.name) / "session.cast"

    def _session(self, argv: list[str], cols: int = 80, rows: int = 24) -> TmuxSession:
        return TmuxBackend().create_session(argv, self.cast, None, {}, cols, rows)

    def _cast_events(self) -> list[list[object]]:
        lines = self.cast.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines[1:] if line.strip()]

    def test_the_screen_is_what_the_pane_shows(self) -> None:
        with self._session(["sh", "-c", "printf 'hello world\\n'; sleep 0.5"]) as session:
            self.assertTrue(session.wait_for_text("hello world", 10.0))
            self.assertIn("hello world", session.screen)

    def test_attributes_survive_the_capture(self) -> None:
        with self._session(["sh", "-c", "printf '\\033[31mred\\033[0m plain\\n'; sleep 0.5"]) as session:
            session.wait_for_text("red", 10.0)
            grid = session.screen_attributed()
        self.assertTrue(grid.to_text().startswith("red plain"))
        self.assertEqual(["red", "red", "red"], [cell.fg for cell in grid.rows[0][:3]])
        self.assertEqual("default", grid.rows[0][4].fg)

    def test_the_child_exit_code_is_reported(self) -> None:
        with self._session(["sh", "-c", "exit 7"]) as session:
            session.wait_for_exit(10.0)
        self.assertEqual(7, session.exit_code)

    def test_a_zero_exit_is_reported_as_zero(self) -> None:
        with self._session(["sh", "-c", "exit 0"]) as session:
            session.wait_for_exit(10.0)
        self.assertEqual(0, session.exit_code)

    def test_output_written_before_the_pipe_attaches_is_still_recorded(self) -> None:
        """The startup gate exists for exactly this.

        `new-session` starts the command immediately and `pipe-pane` only
        carries what is written after it attaches, so a command that prints and
        exits would otherwise record nothing at all.
        """
        with self._session(["sh", "-c", "printf 'first line\\n'"]) as session:
            session.wait_for_exit(10.0)
        recorded = "".join(str(event[2]) for event in self._cast_events())
        self.assertIn("first line", recorded)

    def test_the_cast_keeps_the_escape_sequences(self) -> None:
        with self._session(["sh", "-c", "printf '\\033[32mgreen\\033[0m\\n'"]) as session:
            session.wait_for_exit(10.0)
        recorded = "".join(str(event[2]) for event in self._cast_events())
        self.assertIn("\x1b[32m", recorded)

    def test_the_cast_keeps_carriage_returns(self) -> None:
        """A cast with the CRs translated away replays as a staircase.

        Reading the pipe in Python's default text mode applies universal-newline
        translation, which turns every `\\r\\n` into `\\n` and every bare `\\r`
        into `\\n`. Nothing about the recording looks wrong -- the bytes are all
        there -- but pyte then never returns the cursor to column 0, so the
        replayed screen steps diagonally and any `\\r`-redrawn progress line is
        lost.
        """
        with self._session(["sh", "-c", "printf '10%%\\rdone\\n'"]) as session:
            session.wait_for_exit(10.0)
        recorded = "".join(str(event[2]) for event in self._cast_events())
        self.assertIn("\r", recorded)

    def test_the_cast_header_describes_the_grid(self) -> None:
        with self._session(["sh", "-c", "printf 'x\\n'"], cols=100, rows=30) as session:
            session.wait_for_exit(10.0)
        header = json.loads(self.cast.read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual((2, 100, 30), (header["version"], header["width"], header["height"]))

    def test_typed_text_reaches_the_child(self) -> None:
        with self._session(["cat"]) as session:
            session.send_line("typed input")
            self.assertTrue(session.wait_for_text("typed input", 10.0))
            session.send_eof()
            session.wait_for_exit(10.0)

    def test_a_control_key_reaches_the_child(self) -> None:
        with self._session(["sh", "-c", "trap 'printf caught; exit 0' INT; sleep 5"]) as session:
            session.read_available(0.5)
            session.press("ctrl-c")
            self.assertTrue(session.wait_for_text("caught", 10.0))

    def test_it_reports_when_the_session_is_gone(self) -> None:
        with self._session(["sh", "-c", "exit 0"]) as session:
            session.wait_for_exit(10.0)
            self.assertFalse(session.is_alive())

    def test_wait_for_idle_returns_once_the_screen_settles(self) -> None:
        with self._session(["sh", "-c", "printf 'settled\\n'; sleep 3"]) as session:
            self.assertTrue(session.wait_for_idle(0.3, 10.0))

    def test_the_environment_reaches_the_child(self) -> None:
        session = TmuxBackend().create_session(
            ["sh", "-c", 'printf "%s\\n" "$TERMPROOF_MARKER"'],
            self.cast,
            None,
            {"TERMPROOF_MARKER": "present"},
            80,
            24,
        )
        with session:
            self.assertTrue(session.wait_for_text("present", 10.0))

    def test_an_environment_name_tmux_cannot_export_is_skipped(self) -> None:
        # Exported shell functions arrive as names like "BASH_FUNC_foo%%",
        # which are not shell identifiers and break the wrapper script.
        session = TmuxBackend().create_session(
            ["sh", "-c", "printf 'ran\\n'"],
            self.cast,
            None,
            {"BASH_FUNC_x%%": "() { :; }", "GOOD": "kept"},
            80,
            24,
        )
        with session:
            self.assertTrue(session.wait_for_text("ran", 10.0))

    def test_the_socket_and_workdir_are_gone_after_close(self) -> None:
        session = self._session(["sh", "-c", "exit 0"])
        with session:
            workdir = session._workdir
            self.assertIsNotNone(workdir)
        self.assertIsNone(session._socket)
        self.assertFalse(Path(workdir.name).exists())  # type: ignore[union-attr]

    def test_a_missing_tmux_says_so(self) -> None:
        session = TmuxSession(["true"], self.cast, None, {}, 80, 24, tmux_path=None)
        session._socket = "/nonexistent/tmux.sock"
        original = shutil.which
        try:
            shutil.which = lambda _name: None  # type: ignore[assignment]
            with self.assertRaises(RuntimeError) as raised:
                session._resolve_tmux()
        finally:
            shutil.which = original  # type: ignore[assignment]
        self.assertIn("tmux", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
