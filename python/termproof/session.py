from __future__ import annotations

import os
import shlex
import shutil
import time
from pathlib import Path

import pexpect
import pyte

from .attributed import AttributedScreen
from .cast import CastRecorder
from .screen import screen_attributed, screen_text

#: How a session produces its ``.cast`` file.
#:
#: ``"internal"`` records the pty itself — no external binary, and the child is
#: spawned directly. ``"asciinema"`` wraps the child in ``asciinema rec``, which
#: needs the CLI installed but produces a file that tool wrote.
RECORDERS = ("internal", "asciinema")

KEYS = {
    "enter": "\r",
    "escape": "\x1b",
    "tab": "\t",
    "backspace": "\x7f",
    "up": "\x1b[A",
    "down": "\x1b[B",
    "right": "\x1b[C",
    "left": "\x1b[D",
}


class TerminalSession:
    def __init__(
        self,
        argv: list[str],
        cast_path: Path,
        cwd: str | None,
        env: dict[str, str],
        cols: int,
        rows: int,
        recorder: str = "internal",
    ) -> None:
        if recorder not in RECORDERS:
            raise ValueError(f"unknown recorder {recorder!r}; expected one of {RECORDERS}")
        self.argv = argv
        self.recorder = recorder
        self.cast_path = cast_path
        self.exit_code_path = cast_path.with_suffix(".exitcode")
        self.cwd = cwd
        self.cols = cols
        self.rows = rows
        self.raw_output = ""
        self.exit_code: int | None = None
        self._screen = pyte.Screen(cols, rows)
        self._stream = pyte.Stream(self._screen)
        merged_env = os.environ.copy()
        if merged_env.get("TERM") in (None, "", "dumb"):
            merged_env["TERM"] = "xterm-256color"
        merged_env.update(env)
        self.child: pexpect.spawn | None = None
        self._env = merged_env
        self._cast: CastRecorder | None = None

    def __enter__(self) -> TerminalSession:
        self.cast_path.parent.mkdir(parents=True, exist_ok=True)
        self.cast_path.unlink(missing_ok=True)
        self.exit_code_path.unlink(missing_ok=True)
        if self.recorder == "asciinema":
            command = asciinema_rec_command(
                self.argv,
                self.cast_path,
                self.exit_code_path,
                self.cols,
                self.rows,
            )
        else:
            command = shell_recorded_command(self.argv, self.exit_code_path)
            self._cast = CastRecorder(self.cast_path, self.cols, self.rows, self.argv)
            self._cast.__enter__()
        self.child = pexpect.spawn(
            command[0],
            command[1:],
            cwd=self.cwd,
            env=self._env,
            dimensions=(self.rows, self.cols),
            encoding="utf-8",
            codec_errors="replace",
        )
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    @property
    def screen(self) -> str:
        return screen_text(self._screen)

    def screen_attributed(self) -> AttributedScreen:
        """The pyte buffer as a grid, colour and text attributes intact.

        The same emulator state :attr:`screen` flattens, so the two cannot
        describe different moments. Dim is the one attribute missing: pyte
        0.8.2's ``Char`` does not model SGR 2, so it is consumed before this can
        read it. The tmux backend parses the escapes itself and does carry it.
        """
        return screen_attributed(self._screen)

    def send_text(self, text: str) -> None:
        if self._cast is not None:
            self._cast.input(text)
        self._require_child().send(text)

    def send_line(self, text: str) -> None:
        self.send_text(text + "\r")

    def press(self, key: str) -> None:
        normalized = key.lower()
        if normalized.startswith("ctrl-"):
            self._require_child().sendcontrol(normalized.removeprefix("ctrl-"))
            return
        sequence = KEYS[normalized]
        self._require_child().send(sequence)

    def send_eof(self) -> None:
        self._require_child().sendeof()

    def set_echo(self, enabled: bool) -> None:
        self._require_child().setecho(enabled)

    def wait_for_text(self, text: str, timeout_seconds: float) -> bool:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            self.read_available(0.05)
            if text in self.screen or text in self.raw_output:
                return True
            if not self.is_alive():
                self.read_available(0)
                return text in self.screen or text in self.raw_output
        return False

    def wait_for_idle(self, stable_seconds: float, timeout_seconds: float) -> bool:
        deadline = time.monotonic() + timeout_seconds
        last_screen = self.screen
        last_raw_len = len(self.raw_output)
        # `None` means no activity has been observed yet, so the stable window has not
        # started. Without this, a session whose first output is still pending would
        # have its blank initial screen counted as idle.
        stable_since: float | None = time.monotonic() if self.raw_output else None
        while time.monotonic() < deadline:
            self.read_available(0.05)
            current = self.screen
            raw_len = len(self.raw_output)
            # Raw length only *arms* the window: a first byte that is pure escape
            # sequence never changes the rendered screen, so without it the timer
            # would never start. Once armed, only rendered-text changes count —
            # otherwise title ticks or colour-only animation would never go idle.
            if current != last_screen or (stable_since is None and raw_len != last_raw_len):
                last_screen = current
                last_raw_len = raw_len
                stable_since = time.monotonic()
            if stable_since is not None and time.monotonic() - stable_since >= stable_seconds:
                return True
            if not self.is_alive():
                self.read_available(0)
                return True
        return False

    def wait_for_exit(self, timeout_seconds: float) -> int | None:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            self.read_available(0.05)
            if not self.is_alive():
                return self._collect_exit_code()
        return self.exit_code

    def read_available(self, timeout: float) -> None:
        child = self._require_child()
        if child.closed:
            return
        while True:
            try:
                chunk = child.read_nonblocking(size=4096, timeout=timeout)
            except pexpect.TIMEOUT:
                return
            except pexpect.EOF:
                self._collect_exit_code()
                return
            except ValueError:
                return
            if not chunk:
                return
            self.raw_output += chunk
            self._stream.feed(chunk)
            if self._cast is not None:
                self._cast.output(chunk)
            timeout = 0

    def is_alive(self) -> bool:
        child = self._require_child()
        return child.isalive()

    def close(self) -> None:
        if self.child is None:
            return
        try:
            self.read_available(0)
        finally:
            if not self.child.closed and self.child.isalive():
                self.child.close(force=True)
            self._collect_exit_code()
            if self._cast is not None:
                self._cast.__exit__()
                self._cast = None

    def _collect_exit_code(self) -> int | None:
        child = self._require_child()
        if self.exit_code is not None:
            return self.exit_code
        if not child.closed:
            child.close()
        recorded_exit_code = self._read_recorded_exit_code()
        if recorded_exit_code is not None:
            self.exit_code = recorded_exit_code
        elif child.exitstatus is not None:
            self.exit_code = int(child.exitstatus)
        elif child.signalstatus is not None:
            self.exit_code = 128 + int(child.signalstatus)
        return self.exit_code

    def _require_child(self) -> pexpect.spawn:
        if self.child is None:
            raise RuntimeError("session has not started")
        return self.child

    def _read_recorded_exit_code(self) -> int | None:
        if not self.exit_code_path.exists():
            return None
        value = self.exit_code_path.read_text(encoding="utf-8").strip()
        return int(value) if value else None


def asciinema_rec_command(
    argv: list[str],
    cast_path: Path,
    exit_code_path: Path,
    cols: int,
    rows: int,
) -> list[str]:
    asciinema = shutil.which("asciinema")
    if not asciinema:
        raise RuntimeError("asciinema CLI is required to record terminal sessions")
    return [
        asciinema,
        "rec",
        "--overwrite",
        "--stdin",
        "--quiet",
        "--cols",
        str(cols),
        "--rows",
        str(rows),
        "--command",
        recorded_command(argv, exit_code_path),
        str(cast_path),
    ]


def shell_recorded_command(argv: list[str], exit_code_path: Path) -> list[str]:
    """argv wrapped in a shell that records the child's exit status.

    The status has to reach a file: the shell is what pexpect reaps, so the
    child's own code would otherwise be lost.
    """
    shell = shutil.which("sh") or "/bin/sh"
    return [shell, "-c", recorded_command(argv, exit_code_path)]


def recorded_command(argv: list[str], exit_code_path: Path) -> str:
    target = shlex.join(argv)
    exit_file = shlex.quote(str(exit_code_path.resolve()))
    return (
        f"{target}; "
        "__termproof_status=$?; "
        f"printf '%s' \"$__termproof_status\" > {exit_file}; "
        'exit "$__termproof_status"'
    )
