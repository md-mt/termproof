from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BuildInfo:
    """Where the binary under test came from.

    ``mode`` is ``"installed"`` for something already on the machine, or
    ``"source"`` for something built for this run. A source build has to name
    what produced it (``build_target``) and which revision it was built from
    (``source_ref`` or ``git_commit``): a report that cannot be traced back to
    an exact build is not evidence of much.
    """

    mode: str
    command: list[str]
    binary_path: str | None
    version: str
    git_commit: str | None
    timestamp: str
    #: What produced the binary — a Buck target, a make target, a build script.
    build_target: str | None = None
    #: Which change it was built from — a PR number, a diff number, a tag.
    source_ref: str | None = None

    @classmethod
    def from_command(cls, command: list[str], cwd: str | None = None) -> BuildInfo:
        """Resolve *command* on PATH and describe what it found."""
        binary_path = shutil.which(command[0]) if command else None
        return cls(
            mode="installed",
            command=command,
            binary_path=binary_path,
            version=_probe_version(binary_path),
            git_commit=_git_commit(Path(cwd or ".")),
            timestamp=_now(),
        )

    @classmethod
    def from_binary(cls, binary_path: str, cwd: str | None = None) -> BuildInfo:
        """Describe a binary at a known path, rather than one found on PATH."""
        return cls(
            mode="installed",
            command=[binary_path],
            binary_path=binary_path,
            version=_probe_version(binary_path),
            git_commit=_git_commit(Path(cwd or ".")),
            timestamp=_now(),
        )

    @classmethod
    def from_source_build(
        cls,
        build_target: str,
        binary_path: str | None = None,
        source_ref: str | None = None,
        git_commit: str | None = None,
        cwd: str | None = None,
    ) -> BuildInfo:
        """Describe a binary built for this run from a known revision."""
        return cls(
            mode="source",
            command=[binary_path] if binary_path else [],
            binary_path=binary_path,
            version=_probe_version(binary_path),
            git_commit=git_commit if git_commit is not None else _git_commit(Path(cwd or ".")),
            timestamp=_now(),
            build_target=build_target,
            source_ref=source_ref,
        )

    def verify_provenance(self) -> bool:
        """True when this mode's identifying fields are present and real."""
        if self.mode == "installed":
            return bool(self.binary_path) and Path(self.binary_path or "").exists()
        if self.mode == "source":
            return (
                bool(self.build_target)
                and bool(self.source_ref or self.git_commit)
                and bool(self.binary_path)
                and Path(self.binary_path or "").exists()
            )
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "command": self.command,
            "binary_path": self.binary_path,
            "version": self.version,
            "git_commit": self.git_commit,
            "timestamp": self.timestamp,
            "build_target": self.build_target,
            "source_ref": self.source_ref,
            "provenance_verified": self.verify_provenance(),
        }


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _probe_version(binary_path: str | None) -> str:
    if not binary_path:
        return "unknown"
    try:
        completed = subprocess.run(
            [binary_path, "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return completed.stdout.strip() or "unknown"


def _git_commit(cwd: Path) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None
