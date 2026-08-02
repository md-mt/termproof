#!/usr/bin/env python3
"""Deterministic non-interactive fixture app."""
from __future__ import annotations

import sys


def main() -> int:
    sys.stdout.write("TermProof Fixture App v1.2.3\n")
    sys.stdout.write("status: ready\n")
    sys.stdout.write("menu: [status] [help] [quit]\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
