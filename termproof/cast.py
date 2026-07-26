from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import TextIO


class CastRecorder:
    def __init__(self, path: Path, cols: int, rows: int, command: list[str]) -> None:
        self.path = path
        self.cols = cols
        self.rows = rows
        self.command = command
        self._start = time.monotonic()
        self._file: TextIO | None = None

    def __enter__(self) -> "CastRecorder":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self.path.open("w", encoding="utf-8")
        header = {
            "version": 2,
            "width": self.cols,
            "height": self.rows,
            "timestamp": int(time.time()),
            "command": " ".join(self.command),
            "env": {
                "SHELL": os.environ.get("SHELL", ""),
                "TERM": os.environ.get("TERM", "xterm-256color"),
            },
        }
        self._file.write(json.dumps(header) + "\n")
        self._file.flush()
        return self

    def __exit__(self, *args: object) -> None:
        if self._file is not None:
            self._file.close()

    def output(self, data: str) -> None:
        self._record("o", data)

    def input(self, data: str) -> None:
        self._record("i", data)

    def _record(self, kind: str, data: str) -> None:
        if not data or self._file is None:
            return
        event = [round(time.monotonic() - self._start, 6), kind, data]
        self._file.write(json.dumps(event) + "\n")
        self._file.flush()
