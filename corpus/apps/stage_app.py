#!/usr/bin/env python3
"""Deterministic multi-stage fixture app."""
from __future__ import annotations

import sys
import time


def main() -> int:
    sys.stdout.write("stage one\n")
    sys.stdout.flush()
    time.sleep(0.2)
    sys.stdout.write("stage two complete\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
