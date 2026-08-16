"""Colour-stress TUI fixture.

Every other example in this corpus is monochrome, so none of them can tell a
renderer that reproduces colour from one that discards it. This one can.

Deliberately exercises everything the current pipeline throws away:

  * 16-colour foreground + background (normal and bright)
  * 256-colour indexed palette (the 6x6x6 cube and the greyscale ramp)
  * 24-bit truecolour foreground + background gradients
  * bold / dim / italic / underline / reverse / strikethrough
  * Unicode box drawing
  * an animated spinner and progress bar (redraws in place -> video motion)
  * CJK wide characters and an emoji

Driven the same way as examples/generic/generic_tui.py: line commands on stdin.
"""

from __future__ import annotations

import sys
import time

CSI = "\x1b["
RESET = f"{CSI}0m"


def sgr(*codes: object) -> str:
    return CSI + ";".join(str(c) for c in codes) + "m"


def out(text: str = "", end: str = "\n") -> None:
    sys.stdout.write(text + end)
    sys.stdout.flush()


# -- panels -----------------------------------------------------------------


def banner() -> None:
    title = " TERMPROOF COLOUR STRESS FIXTURE "
    out(f"{sgr(1, 97, 44)}┌" + "─" * 62 + f"┐{RESET}")
    out(f"{sgr(1, 97, 44)}│{title:^62}│{RESET}")
    out(f"{sgr(1, 97, 44)}└" + "─" * 62 + f"┘{RESET}")


def panel_16() -> None:
    out(f"{sgr(1, 4)}16-colour{RESET}  fg 30-37 / bright 90-97, bg 40-47 / bright 100-107")
    fg = "".join(f"{sgr(c)}██{RESET}" for c in range(30, 38))
    fgb = "".join(f"{sgr(c)}██{RESET}" for c in range(90, 98))
    bg = "".join(f"{sgr(c)} {c} {RESET}" for c in range(40, 48))
    bgb = "".join(f"{sgr(30, c)}{c}{RESET}" for c in range(100, 108))
    out(f"  fg {fg}  bright {fgb}")
    out(f"  bg {bg}")
    out(f"  bgbright {bgb}")


def panel_256() -> None:
    out(f"{sgr(1, 4)}256-colour{RESET}  6x6x6 cube (16-231) then greyscale ramp (232-255)")
    for row_start in (16, 88, 160):
        row = "".join(f"{sgr(48, 5, n)} {RESET}" for n in range(row_start, row_start + 72))
        out("  " + row)
    grey = "".join(f"{sgr(48, 5, n)}  {RESET}" for n in range(232, 256))
    out("  " + grey)


def panel_truecolour() -> None:
    out(f"{sgr(1, 4)}24-bit truecolour{RESET}  bg sweep then fg sweep")
    width = 72
    bg = "".join(
        f"{sgr(48, 2, int(255 * i / width), int(120 + 100 * (1 - i / width)), int(255 * (1 - i / width)))} {RESET}"
        for i in range(width)
    )
    out("  " + bg)
    fg = "".join(
        f"{sgr(38, 2, int(255 * (1 - i / width)), int(40 + 200 * i / width), 200)}█{RESET}"
        for i in range(width)
    )
    out("  " + fg)


def panel_attributes() -> None:
    out(f"{sgr(1, 4)}attributes{RESET}")
    cells = [
        (sgr(1), "bold"),
        (sgr(2), "dim"),
        (sgr(3), "italic"),
        (sgr(4), "underline"),
        (sgr(7), "reverse"),
        (sgr(9), "strike"),
        (sgr(1, 31), "bold-red"),
        (sgr(2, 32), "dim-green"),
        (sgr(4, 38, 2, 255, 170, 0), "ul-truecolour"),
    ]
    out("  " + "  ".join(f"{code}{label}{RESET}" for code, label in cells))


def panel_unicode() -> None:
    out(f"{sgr(1, 4)}unicode{RESET}  box drawing, CJK wide cells, emoji")
    out(f"  {sgr(36)}┏━━━┳━━━┓  ╔═╗  ╭─╮{RESET}")
    out(f"  {sgr(36)}┃ A ┃ B ┃  ║ ║  │ │{RESET}")
    out(f"  {sgr(36)}┗━━━┻━━━┛  ╚═╝  ╰─╯{RESET}")
    out(f"  {sgr(33)}中文宽字符{RESET} | {sgr(35)}日本語テキスト{RESET} | {sgr(32)}한국어{RESET} | \U0001f680 ✔ ✗")


def spinner(cycles: int = 12, delay: float = 0.08) -> None:
    """Animate in place. Produces motion for the video and a settled final frame."""
    frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    for i in range(cycles):
        pct = int(100 * (i + 1) / cycles)
        filled = pct * 40 // 100
        bar = (
            f"{sgr(48, 2, 40, 200, 120)}" + " " * filled + RESET
            + f"{sgr(48, 2, 45, 50, 60)}" + " " * (40 - filled) + RESET
        )
        out(
            f"\r  {sgr(96)}{frames[i % len(frames)]}{RESET} indexing {bar} {sgr(1)}{pct:3d}%{RESET}",
            end="",
        )
        time.sleep(delay)
    out()


def prompt() -> None:
    out(f"{sgr(1, 92)}colour>{RESET} ", end="")


# -- driver -----------------------------------------------------------------


def main() -> int:
    out(f"{sgr(2)}colour stress fixture ready; commands: palette, attrs, animate, exit{RESET}")
    prompt()
    for raw in sys.stdin:
        cmd = raw.strip().lower()
        out()
        if cmd == "exit":
            out(f"{sgr(1, 92)}COLOUR STRESS COMPLETE{RESET}")
            return 0
        if cmd == "palette":
            banner()
            panel_16()
            panel_256()
            panel_truecolour()
            out(f"{sgr(1, 92)}PALETTE READY{RESET}")
        elif cmd == "attrs":
            panel_attributes()
            panel_unicode()
            out(f"{sgr(1, 92)}ATTRS READY{RESET}")
        elif cmd == "animate":
            spinner()
            out(f"{sgr(1, 92)}ANIMATE READY{RESET}")
        else:
            out(f"{sgr(31)}unknown command{RESET}")
        out()
        prompt()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
