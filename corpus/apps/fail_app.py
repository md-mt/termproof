#!/usr/bin/env python3
"""Deterministic failing fixture app."""
from __future__ import annotations

import sys


def main() -> int:
    sys.stdout.write("fixture failure app\n")
    sys.stdout.write("about to exit non-zero\n")
    sys.stdout.flush()
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
