from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BuildInfo:
    mode: str
    command: list[str]
    binary_path: str | None
    version: str
    git_commit: str | None
    timestamp: str

    @classmethod
    def from_command(cls, command: list[str], cwd: str | None = None) -> "BuildInfo":
        binary_path = shutil.which(command[0]) if command else None
        return cls(
            mode="installed",
            command=command,
            binary_path=binary_path,
            version=_probe_version(binary_path),
            git_commit=_git_commit(Path(cwd or ".")),
            timestamp=datetime.now().isoformat(timespec="seconds"),
        )

    def verify_provenance(self) -> bool:
        if self.mode == "installed":
            return bool(self.binary_path)
        if self.mode == "source":
            return bool(self.git_commit)
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "command": self.command,
            "binary_path": self.binary_path,
            "version": self.version,
            "git_commit": self.git_commit,
            "timestamp": self.timestamp,
            "provenance_verified": self.verify_provenance(),
        }


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
