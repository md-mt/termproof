from __future__ import annotations

import sys
import time


def main() -> int:
    emit(
        [
            "Pi-style terminal conversation demo",
            "Goal: verify a multi-turn workflow and publish terminal evidence.",
            "",
        ],
        0.25,
    )
    prompt()
    for raw_line in sys.stdin:
        text = raw_line.strip()
        if not text:
            prompt()
            continue
        lower = text.lower()
        if lower in {"exit", "quit"}:
            emit(["assistant> Closing the verification session.", "SESSION COMPLETE"], 0.45)
            return 0
        print(f"user> {text}", flush=True)
        time.sleep(0.35)
        respond(lower)
        print("", flush=True)
        prompt()
    return 0


def respond(text: str) -> None:
    if "inspect" in text:
        emit(
            [
                "assistant> Inspecting the repository shape.",
                "assistant> Found recipe files under examples/.",
                "assistant> Found evidence renderer in termproof/evidence.py.",
                "assistant> Found asciinema wrapper in termproof/session.py.",
                "assistant> Repository inspection complete.",
            ],
            0.65,
        )
        return
    if "run" in text or "pipeline" in text:
        emit(
            [
                "assistant> Running the verification pipeline.",
                "assistant> Recording terminal session with asciinema rec.",
                "assistant> Replaying the cast into final.txt and final.svg.",
                "assistant> Rendering MP4 with agg plus ffmpeg.",
                "assistant> Writing result.json and report.md.",
                "assistant> Pipeline completed.",
            ],
            0.7,
        )
        return
    if "summarize" in text or "evidence" in text:
        emit(
            [
                "assistant> Evidence package:",
                "assistant> - session.cast is the source of truth.",
                "assistant> - final.svg is the review screenshot.",
                "assistant> - session.mp4 is the playable video.",
                "assistant> - report.md links every artifact.",
                "assistant> Multi-turn verification passed.",
            ],
            0.65,
        )
        return
    emit(["assistant> I can inspect, run the pipeline, or summarize evidence."], 0.4)


def emit(lines: list[str], delay: float) -> None:
    for line in lines:
        print(line, flush=True)
        time.sleep(delay)


def prompt() -> None:
    print("you> ", end="", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
