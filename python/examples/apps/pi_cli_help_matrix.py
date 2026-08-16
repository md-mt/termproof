from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PI = Path(__file__).resolve().parents[1] / "bin" / "pi-clean"

COMMANDS = {
    "overview": [
        ["--help"],
    ],
    "packages": [
        ["install", "--help"],
        ["remove", "--help"],
        ["update", "--help"],
        ["list", "--help"],
        ["config", "--help"],
    ],
}


def main() -> int:
    scenario = sys.argv[1] if len(sys.argv) > 1 else "overview"
    commands = COMMANDS[scenario]
    for index, args in enumerate(commands):
        if index:
            print()
        print("$ pi " + " ".join(args), flush=True)
        completed = subprocess.run(
            [str(PI), *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        print(completed.stdout.rstrip(), flush=True)
        if completed.returncode != 0:
            return completed.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
