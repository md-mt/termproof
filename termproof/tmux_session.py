"""A session whose terminal emulator is tmux rather than a bare pty.

A pty is a byte pipe, not a terminal. :class:`~termproof.session.TerminalSession`
therefore reconstructs the screen by feeding that stream to ``pyte``, which is
accurate but is a second emulator's opinion of what the first one would have
shown. Programs that repaint whole frames on the alternate screen are where the
two are most likely to differ.

tmux owns a real grid, and ``capture-pane`` returns what is actually on it. This
backend swaps only the transport — spawn, input, screen read, teardown — so
recipes and steps are unchanged.

The cast is recorded from ``pipe-pane``, so the recording is the pane's real
output with real timings, not a screen poll.

Needs ``tmux`` on PATH.
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from .attributed import AttributedScreen, attributed_screen_from_ansi_text
from .cast import CastRecorder

TMUX = "tmux"
SESSION_NAME = "termproof"
TMUX_TIMEOUT_SECONDS = 30
# Shorter than the command timeout: a kill-server that hangs too must not mask
# the original failure with its own.
KILL_SERVER_TIMEOUT_SECONDS = 5

# tmux only accepts environment names that are shell identifiers. os.environ can
# carry exported shell functions ("BASH_FUNC_foo%%") that break the wrapper.
_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

#: termproof key names to tmux key names. `press` takes names, so unlike a raw
#: byte stream there is nothing to parse out of the text.
KEYS = {
    "enter": "Enter",
    "escape": "Escape",
    "tab": "Tab",
    "backspace": "BSpace",
    "up": "Up",
    "down": "Down",
    "right": "Right",
    "left": "Left",
}


class TmuxSession:
    """A terminal session backed by tmux, matching ``TerminalSession``'s surface."""

    def __init__(
        self,
        argv: list[str],
        cast_path: Path,
        cwd: str | None,
        env: dict[str, str],
        cols: int,
        rows: int,
        tmux_path: str | None = None,
    ) -> None:
        self.argv = argv
        self.cast_path = cast_path
        self.exit_code_path = cast_path.with_suffix(".exitcode")
        self.cwd = cwd
        self.cols = cols
        self.rows = rows
        self.raw_output = ""
        self.exit_code: int | None = None
        self.tmux_path = tmux_path
        merged = os.environ.copy()
        if merged.get("TERM") in (None, "", "dumb"):
            merged["TERM"] = "xterm-256color"
        merged.update(env)
        self._env = merged
        self._socket: str | None = None
        self._gate: str | None = None
        self._workdir: tempfile.TemporaryDirectory[str] | None = None
        self._cast: CastRecorder | None = None
        self._pipe_thread: threading.Thread | None = None
        self._stop = threading.Event()

    # -- lifecycle ----------------------------------------------------------

    def __enter__(self) -> TmuxSession:
        self.cast_path.parent.mkdir(parents=True, exist_ok=True)
        self.cast_path.unlink(missing_ok=True)
        self.exit_code_path.unlink(missing_ok=True)
        # A private socket per session: parallel runs cannot see each other's
        # panes, and the session's environment is ours alone.
        self._workdir = tempfile.TemporaryDirectory(prefix="termproof-tmux-")
        self._socket = os.path.join(self._workdir.name, "tmux.sock")
        self._gate = os.path.join(self._workdir.name, "gate.fifo")
        os.mkfifo(self._gate)
        wrapper = self._write_launch_script()
        self._tmux(
            "new-session",
            "-d",
            "-s",
            SESSION_NAME,
            "-x",
            str(self.cols),
            "-y",
            str(self.rows),
            "-c",
            self.cwd or os.getcwd(),
            "sh",
            wrapper,
        )
        self._start_recording()
        # The pane is blocked on the gate until here. `pipe-pane` only carries
        # output produced after it attaches, and `new-session` starts the
        # command immediately, so without this the first writes — which for a
        # short command is all of them — never reach the recording.
        with open(self._gate, "w", encoding="utf-8") as gate:
            gate.write("go\n")
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        if self._socket is None:
            return
        self._collect_exit_code()
        # kill-server, not kill-session: it reaps the server process too, so a
        # run cannot leak one tmux daemon per recipe.
        self._tmux("kill-server", check=False)
        self._stop.set()
        if self._pipe_thread is not None:
            self._pipe_thread.join(timeout=2.0)
            self._pipe_thread = None
        if self._cast is not None:
            self._cast.__exit__()
            self._cast = None
        self._socket = None
        if self._workdir is not None:
            self._workdir.cleanup()
            self._workdir = None

    # -- output -------------------------------------------------------------

    @property
    def screen(self) -> str:
        text = self._capture()
        lines = [line.rstrip() for line in text.split("\n")]
        while lines and not lines[-1]:
            lines.pop()
        return "\n".join(lines)

    def screen_attributed(self) -> AttributedScreen:
        """The grid with SGR attributes intact, straight from tmux."""
        return attributed_screen_from_ansi_text(
            self._capture(escapes=True),
            columns=self.cols,
            rows=self.rows,
        )

    def read_available(self, timeout: float) -> None:
        """No stream to drain — tmux owns the grid.

        Kept so the step implementations can call it uniformly. It still sleeps,
        because callers use it to give the child a moment before reading.
        """
        if timeout > 0:
            time.sleep(timeout)

    # -- input --------------------------------------------------------------

    def send_text(self, text: str) -> None:
        # `send-keys -l` sends the argument literally, so text that happens to
        # look like a key name is not interpreted as one.
        self._tmux("send-keys", "-t", SESSION_NAME, "-l", text)

    def send_line(self, text: str) -> None:
        self.send_text(text)
        self.press("enter")

    def press(self, key: str) -> None:
        normalized = key.lower()
        if normalized.startswith("ctrl-"):
            self._tmux("send-keys", "-t", SESSION_NAME, f"C-{normalized.removeprefix('ctrl-')}")
            return
        self._tmux("send-keys", "-t", SESSION_NAME, KEYS[normalized])

    def send_eof(self) -> None:
        self.press("ctrl-d")

    def set_echo(self, enabled: bool) -> None:
        """No-op: tmux does not expose the pane's termios to the client."""

    # -- waiting ------------------------------------------------------------

    def wait_for_text(self, text: str, timeout_seconds: float) -> bool:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if text in self.screen or text in self.raw_output:
                return True
            if not self.is_alive():
                return text in self.screen or text in self.raw_output
            time.sleep(0.05)
        return False

    def wait_for_idle(self, stable_seconds: float, timeout_seconds: float) -> bool:
        deadline = time.monotonic() + timeout_seconds
        last = self.screen
        stable_since: float | None = time.monotonic() if last else None
        while time.monotonic() < deadline:
            time.sleep(0.05)
            current = self.screen
            if current != last:
                last = current
                stable_since = time.monotonic()
            elif stable_since is None and current:
                stable_since = time.monotonic()
            if stable_since is not None and time.monotonic() - stable_since >= stable_seconds:
                return True
            if not self.is_alive():
                return True
        return False

    def wait_for_exit(self, timeout_seconds: float) -> int | None:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if not self.is_alive():
                return self._collect_exit_code()
            time.sleep(0.05)
        return self.exit_code

    def is_alive(self) -> bool:
        if self._socket is None:
            return False
        return self._tmux("has-session", "-t", SESSION_NAME, check=False).returncode == 0

    # -- internal -----------------------------------------------------------

    def _resolve_tmux(self) -> str:
        if self.tmux_path is not None:
            return self.tmux_path
        resolved = shutil.which(TMUX)
        if resolved is None:
            raise RuntimeError("tmux is required by the tmux session backend but was not found on PATH.")
        return resolved

    def _write_launch_script(self) -> str:
        """A shell wrapper that exports the environment then execs the target.

        Passing the environment as ``new-session -e`` flags would be hundreds of
        arguments in a real environment; a wrapper sidesteps both the argv
        length limit and tmux's own quoting.
        """
        assert self._workdir is not None
        path = os.path.join(self._workdir.name, "launch.sh")
        assert self._gate is not None
        # Wait for the recording pipe to be attached before producing any
        # output. See `__enter__`.
        lines = ["#!/bin/sh", f"read _ < {shlex.quote(self._gate)}"]
        lines.extend(
            f"export {key}={shlex.quote(value)}"
            for key, value in self._env.items()
            if _ENV_NAME.match(key)
        )
        exit_file = shlex.quote(str(self.exit_code_path.resolve()))
        lines.append(f"{shlex.join(self.argv)}")
        lines.append("__termproof_status=$?")
        lines.append(f"printf '%s' \"$__termproof_status\" > {exit_file}")
        lines.append('exit "$__termproof_status"')
        Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.chmod(path, 0o755)
        return path

    def _start_recording(self) -> None:
        """Tee the pane through a fifo and timestamp it into a cast.

        ``pipe-pane`` gives the pane's real byte stream, so the recording keeps
        the timing the session actually had rather than a poll interval's.
        """
        assert self._workdir is not None
        fifo = os.path.join(self._workdir.name, "pane.fifo")
        os.mkfifo(fifo)
        self._cast = CastRecorder(self.cast_path, self.cols, self.rows, self.argv)
        self._cast.__enter__()
        self._pipe_thread = threading.Thread(target=self._drain_pipe, args=(fifo,), daemon=True)
        self._pipe_thread.start()
        self._tmux("pipe-pane", "-t", SESSION_NAME, "-O", f"cat > {shlex.quote(fifo)}")

    def _drain_pipe(self, fifo: str) -> None:
        # Opening a fifo for reading blocks until a writer appears, which is why
        # this runs on its own thread and is started before `pipe-pane`.
        try:
            with open(fifo, encoding="utf-8", errors="replace") as pipe:
                while not self._stop.is_set():
                    chunk = pipe.read(4096)
                    if not chunk:
                        break
                    self.raw_output += chunk
                    if self._cast is not None:
                        self._cast.output(chunk)
        except OSError:
            return

    def _capture(self, escapes: bool = False) -> str:
        if self._socket is None:
            raise RuntimeError("session has not started")
        args = ["capture-pane", "-t", SESSION_NAME, "-p"]
        if escapes:
            args.append("-e")
        result = self._tmux(*args, check=False)
        return result.stdout if result.returncode == 0 else ""

    def _collect_exit_code(self) -> int | None:
        if self.exit_code is not None:
            return self.exit_code
        if self.exit_code_path.exists():
            value = self.exit_code_path.read_text(encoding="utf-8").strip()
            if value:
                self.exit_code = int(value)
        return self.exit_code

    def _tmux(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        if self._socket is None:
            raise RuntimeError("session has not started")
        command = [self._resolve_tmux(), "-S", self._socket, *args]
        try:
            return subprocess.run(
                command,
                check=check,
                capture_output=True,
                text=True,
                timeout=TMUX_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            # Not via self._tmux(): a fully hung server would hit the same
            # timeout and could recurse.
            try:
                subprocess.run(
                    [self._resolve_tmux(), "-S", self._socket, "kill-server"],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=KILL_SERVER_TIMEOUT_SECONDS,
                )
            except subprocess.TimeoutExpired:
                pass
            raise


class TmuxBackend:
    """Session backend that runs the target inside tmux."""

    name = "tmux"

    def __init__(self, tmux_path: str | None = None) -> None:
        self.tmux_path = tmux_path

    def create_session(
        self,
        argv: list[str],
        cast_path: Path,
        cwd: str | None,
        env: dict[str, str],
        cols: int,
        rows: int,
    ) -> TmuxSession:
        return TmuxSession(argv, cast_path, cwd, env, cols, rows, tmux_path=self.tmux_path)


__all__ = ["KEYS", "SESSION_NAME", "TMUX", "TmuxBackend", "TmuxSession"]
