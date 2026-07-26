"""Self-contained demo TUI for termproof demo command.

No external dependencies beyond stdlib. Exercises all step and assertion types.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="termproof-demo-tui")
    parser.add_argument("--out", type=Path, default=Path(".termproof/demo"))
    parser.add_argument("--export-name", type=str, default="demo_export.txt")
    args = parser.parse_args(argv)

    out_dir = args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    export_path = out_dir / args.export_name

    _emit(
        [
            "TermProof Demo TUI v2.0.1",
            "Type commands to explore the demo workflow.",
            "Commands: dashboard, filter, export, status, help, exit",
            "",
        ],
        0.05,
    )

    _prompt()

    for raw_line in sys.stdin:
        line = raw_line.strip()
        low = line.lower()

        if low == "":
            _prompt()
            continue

        if low in ("exit", "quit"):
            if not export_path.exists():
                export_path.write_text(
                    "export complete id=123\nversion=2.0.1\nstatus: ok\n",
                    encoding="utf-8",
                )
            _emit(
                [
                    "demo> closing session",
                    "Session summary: dashboard opened, filter applied, export done",
                    "GENERIC DEMO COMPLETE",
                    "Version: 2.0.1 Status: SUCCESS",
                ],
                0.1,
            )
            _emit([f"Export artifact: {export_path}"], 0.05)
            return 0

        elif low in ("dashboard", "open dashboard"):
            _emit(
                [
                    "demo> loading dashboard...",
                    "demo> widgets rendered",
                    "DASHBOARD READY",
                    "version: 2.0.1 build: 2026-07-25",
                    "status: active",
                ],
                0.15,
            )
            print("", flush=True)
            _prompt()

        elif "filter" in low:
            _emit(
                [
                    "demo> applying filter status:error",
                    "demo> 3 rows visible",
                    "FILTER READY",
                    "filtered rows: 3 ids=[101,102,103]",
                ],
                0.15,
            )
            print("", flush=True)
            _prompt()

        elif low.startswith("export"):
            export_path.write_text(
                "export complete id=123\nversion=2.0.1\nstatus: ok\nfiltered rows: 3\n",
                encoding="utf-8",
            )
            _emit(
                [
                    f"demo> writing verification summary to {export_path}",
                    "demo> report artifact linked",
                    "EXPORT READY",
                    f"export id: 123 path: {export_path}",
                ],
                0.15,
            )
            print("", flush=True)
            _prompt()

        elif low == "status":
            _emit(
                [
                    "demo> current status",
                    "DASHBOARD: ready",
                    "FILTER: applied",
                    f"EXPORT: {'ready' if export_path.exists() else 'pending'}",
                    "Version: 2.0.1 Status: SUCCESS",
                ],
                0.1,
            )
            print("", flush=True)
            _prompt()

        elif low == "help":
            _emit(
                [
                    "Available commands:",
                    "  dashboard - Open dashboard (triggers DASHBOARD READY)",
                    "  filter    - Apply filter (triggers FILTER READY)",
                    "  export    - Export report (triggers EXPORT READY, creates file)",
                    "  status    - Show current status",
                    "  help      - Show this help",
                    "  exit      - Exit demo",
                    "",
                    "This demo exercises all TermProof step types:",
                    " wait_for_text, wait_for_idle, send_text, send_line, press, sleep, wait_for_regex",
                    "And all assertion types:",
                    " output_contains, output_not_contains, screen_contains, screen_not_contains, exit_code, file_exists, file_contains",
                ],
                0.05,
            )
            print("", flush=True)
            _prompt()

        else:
            _emit([f"demo> unknown command: {line}", "Type 'help' for available commands"], 0.05)
            print("", flush=True)
            _prompt()

    return 0


def _emit(lines: list[str], delay: float) -> None:
    for l in lines:
        print(l, flush=True)
        if delay:
            time.sleep(delay)


def _prompt() -> None:
    print("demo> ", end="", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
