from __future__ import annotations

from pathlib import Path
from typing import Protocol

from .session import TerminalSession


class SessionBackend(Protocol):
    """Protocol for pluggable session/terminal backends."""

    def create_session(
        self,
        argv: list[str],
        cast_path: Path,
        cwd: str | None,
        env: dict[str, str],
        cols: int,
        rows: int,
    ) -> TerminalSession:
        ...


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
