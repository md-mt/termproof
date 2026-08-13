from __future__ import annotations

import sys
import time


def main() -> int:
    emit(["Generic TUI demo", "Use commands: open dashboard, filter errors, export report, exit", ""], 0.1)
    prompt()
    for raw_line in sys.stdin:
        text = raw_line.strip().lower()
        if text == "exit":
            emit(["demo> closing session", "GENERIC TUI COMPLETE"], 0.15)
            return 0
        if text == "open dashboard":
            emit(["demo> loading dashboard", "demo> widgets rendered", "DASHBOARD READY"], 0.2)
        elif text == "filter errors":
            emit(["demo> applying status:error filter", "demo> 3 rows visible", "FILTER READY"], 0.2)
        elif text == "export report":
            emit(["demo> writing verification summary", "demo> report artifact linked", "EXPORT READY"], 0.2)
        else:
            emit(["demo> unknown command"], 0.1)
        print("", flush=True)
        prompt()
    return 0


def emit(lines: list[str], delay: float) -> None:
    for line in lines:
        print(line, flush=True)
        time.sleep(delay)


def prompt() -> None:
    print("demo> ", end="", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
