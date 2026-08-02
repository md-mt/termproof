#!/usr/bin/env python3
"""Deterministic interactive fixture app."""
from __future__ import annotations

import sys


def main() -> int:
    sys.stdout.write("version: 1.2.3\n")
    sys.stdout.write("demo> ")
    sys.stdout.flush()
    for raw in sys.stdin:
        line = raw.rstrip("\n").rstrip("\r")
        if line == "quit":
            sys.stdout.write("bye\n")
            sys.stdout.flush()
            return 0
        if line == "status":
            sys.stdout.write("STATUS: ok\n")
        elif line == "help":
            sys.stdout.write("HELP: available\n")
        else:
            sys.stdout.write(f"got: {line}\n")
        sys.stdout.write("demo> ")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
