#!/usr/bin/env python3
"""Deterministic JSON-output fixture app."""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    payload = {"app": "fixture", "version": "1.2.3", "status": "ok", "items": ["alpha", "beta", "gamma"]}
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()
    Path("fixture-artifact.txt").write_text("fixture artifact content\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
