from __future__ import annotations

from pathlib import Path

from .protocols import SessionBackend
from .session import TerminalSession


class PexpectAsciinemaBackend:
    """pexpect + asciinema backend (current behavior)."""

    def create_session(
        self,
        argv: list[str],
        cast_path: Path,
        cwd: str | None,
        env: dict[str, str],
        cols: int,
        rows: int,
    ) -> TerminalSession:
        return TerminalSession(argv, cast_path, cwd, env, cols, rows)
