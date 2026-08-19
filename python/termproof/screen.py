from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pyte

from .attributed import AttributedScreen, attributed_screen_from_pyte
from .config import SvgRenderConfig


def _replay(cast_path: Path) -> tuple[pyte.Screen, int, int]:
    with cast_path.open(encoding="utf-8") as file:
        header = json.loads(file.readline())
        cols = int(header.get("width", 100))
        rows = int(header.get("height", 30))
        screen = pyte.Screen(cols, rows)
        stream = pyte.Stream(screen)
        for line in file:
            event = json.loads(line)
            if len(event) >= 3 and event[1] == "o":
                stream.feed(event[2])
    return screen, cols, rows


def replay_cast(cast_path: Path) -> tuple[str, int, int]:
    screen, cols, rows = _replay(cast_path)
    return screen_text(screen), cols, rows


def replay_cast_attributed(cast_path: Path) -> tuple[AttributedScreen, int, int]:
    """Replay a cast and return the final screen with its attributes intact.

    The text-only :func:`replay_cast` discards colour, which is most of what a
    TUI uses to say what state it is in.
    """
    screen, cols, rows = _replay(cast_path)
    return screen_attributed(screen), cols, rows


def replay_cast_both(cast_path: Path) -> tuple[str, AttributedScreen, int, int]:
    """Replay once, returning the text and the attributed grid together.

    Two replays of the same cast cannot disagree, but they do cost twice as
    much, and a caller that wants both wants them from the same final state.
    """
    screen, cols, rows = _replay(cast_path)
    return screen_text(screen), screen_attributed(screen), cols, rows


def screen_text(screen: pyte.Screen) -> str:
    lines = [line.rstrip() for line in screen.display]
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def screen_attributed(screen: pyte.Screen) -> AttributedScreen:
    """Read *screen* as an attributed grid, colour and styles included."""
    return attributed_screen_from_pyte(screen)


def grid_text(screen: AttributedScreen) -> str:
    """A grid's text, normalised the way a session normalises its own.

    Trailing whitespace off each row, then trailing blank rows dropped — the
    same two steps :func:`screen_text` and ``TmuxSession.screen`` apply, so a
    text derived from a grid still reads as the string an assertion matched.
    """
    lines = screen.text_lines(trim_right=True)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


@dataclass(frozen=True)
class ScreenCapture:
    """One reading of a session's screen, as of one instant.

    ``attributed`` is ``None`` when the session has no grid to report, which is
    not an error: the text alone is a complete screenshot source, just a
    monochrome one.
    """

    screen: str
    attributed: AttributedScreen | None = None


def capture_screen(session: Any) -> ScreenCapture:
    """Read *session*'s screen once, as text and grid together.

    Text and grid have to describe the same instant. Fetched separately against
    a live program they need not, and the result is evidence that validates and
    lies: ``steps/NN.txt`` describing the screen before an action while
    ``steps/NN.svg`` and the dedup verdict describe the screen after it. The
    tmux backend makes that concrete — its two readings are two ``capture-pane``
    invocations, and the pty backend's ``screen`` and grid are two reads of an
    emulator the child is still feeding.

    So the grid is read first and the text is derived from it. One grid, one
    text, no window. A session with no ``screen_attributed`` falls back to its
    ``screen`` string and reports no grid, which is what keeps a third-party
    session backend working unchanged.

    This is the *only* place in TermProof where a screen's text is derived from
    a grid rather than taken from the source that produced it, and it is worth
    knowing what that costs on each backend:

    - **pty.** The grid comes from the same ``pyte.Screen`` :func:`screen_text`
      flattens, so no parsing is involved and the two cannot disagree. Pinned by
      ``test_grid_text_reproduces_the_flattening_a_pty_session_does``.
    - **tmux.** The grid is parsed out of ``capture-pane -e`` while
      ``TmuxSession.screen`` is what ``capture-pane`` returns already flat.
      Here the derived text is only as good as
      :func:`~termproof.attributed.attributed_screen_from_ansi_text`, so a gap
      in that parser becomes corrupted evidence — which it did: an unhandled
      OSC-8 hyperlink rendered its URL as visible text in both the ``.txt`` and
      the screenshot. ``TmuxTextEquivalenceTest`` pins the two readings against
      each other over every escape family, so a future gap fails a test rather
      than a screenshot.
    """
    read_grid = getattr(session, "screen_attributed", None)
    grid = read_grid() if callable(read_grid) else None
    if grid is None:
        return ScreenCapture(screen=str(getattr(session, "screen", "") or ""))
    return ScreenCapture(screen=grid_text(grid), attributed=grid)


def render_svg(
    text: str,
    output_path: Path,
    cols: int,
    rows: int,
    config: SvgRenderConfig | None = None,
) -> None:
    """Render a screen to SVG.

    Thin wrapper over :class:`~termproof.builtin_renderers.SvgRenderer`. There
    is one renderer behind both entry points, not two copies to keep in step.
    """
    from .builtin_renderers import SvgRenderer

    SvgRenderer(config).render(text, output_path, cols, rows)
