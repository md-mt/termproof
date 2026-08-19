"""Per-step screenshots rendered from the grid the session reported.

`final.svg` has been rendered from an attributed grid for some time; the
per-step images had not, because `StepResult` carried only flattened text and a
grid rebuilt from flattened text is monochrome by construction. These tests
cover the field that closes that — `StepResult.screen_attributed` — from three
directions:

- it is optional, and a session that cannot report a grid keeps working and
  keeps getting its screenshots;
- when it is present the colour reaches the image, and reaches the dedup
  fingerprint, which is where the colour-awareness dedup already had was inert;
- it is affordable, because the grid builders share one object between equal
  cells.
"""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import sys
import tempfile
import unittest
from dataclasses import fields
from pathlib import Path
from typing import Any

import pyte

from termproof import evidence
from termproof.attributed import (
    AttributedCell,
    AttributedScreen,
    attributed_screen_from_ansi_text,
    attributed_screen_from_pyte,
)
from termproof.builtin_renderers import PngRenderer, SvgRenderer
from termproof.builtin_steps import Press, WaitForRegex, step_result
from termproof.config import EvidenceConfig, SvgRenderConfig
from termproof.models import StepResult
from termproof.screen import capture_screen, grid_text, screen_text

_FILL = re.compile(r'fill="(#[0-9a-fA-F]{6})"')
_DEFAULT_FILLS = {SvgRenderConfig().fg.lower(), SvgRenderConfig().bg.lower()}


def _fills(path: Path) -> set[str]:
    return {fill.lower() for fill in _FILL.findall(path.read_text(encoding="utf-8"))}


def _has_colour(path: Path) -> bool:
    return bool(_fills(path) - _DEFAULT_FILLS)


def _grid(text: str, fg: str = "default") -> AttributedScreen:
    """A one-row grid of *text* in *fg*, built without going through any parser."""
    return AttributedScreen(rows=(tuple(AttributedCell(text=ch, fg=fg) for ch in text),))


class _GridlessSession:
    """A session backend that has no attributes to report.

    Third-party backends written against the existing surface look exactly like
    this: a `screen` string and nothing else. Nothing here may break.
    """

    def __init__(self, screen: str = "plain screen") -> None:
        self.screen = screen
        self.raw_output = screen

    def press(self, key: str) -> None:
        pass

    def read_available(self, timeout: float) -> None:
        pass

    def is_alive(self) -> bool:
        return False


class _GridSession(_GridlessSession):
    """A session that can report a grid, as the built-in backends do."""

    def __init__(self, text: str = "status", fg: str = "green") -> None:
        super().__init__(text)
        self._grid = _grid(text, fg)

    def screen_attributed(self) -> AttributedScreen:
        return self._grid


class StepResultCompatibilityTest(unittest.TestCase):
    """`StepResult` is published API; the new field must cost existing callers nothing."""

    def test_the_four_argument_construction_still_works(self) -> None:
        step = StepResult("name", True, "detail", "screen")
        self.assertIsNone(step.screen_attributed)

    def test_the_grid_is_the_last_field_so_positional_callers_are_unmoved(self) -> None:
        names = [field.name for field in fields(StepResult)]
        self.assertEqual(["name", "passed", "detail", "screen", "screen_attributed"], names)

    def test_the_serialised_shape_is_unchanged(self) -> None:
        """`result.json` is shared with the Rust implementation and with the run cache.

        A grid per step would dwarf the rest of the file and nothing downstream
        of the JSON re-renders an image, so the field is deliberately absent.
        """
        step = StepResult("name", True, "detail", "screen", _grid("screen", "red"))
        self.assertEqual(
            {"name": "name", "passed": True, "detail": "detail", "screen": "screen"},
            step.to_dict(),
        )
        json.dumps(step.to_dict())

    def test_a_round_trip_through_the_dict_drops_the_grid_rather_than_faking_one(self) -> None:
        step = StepResult("name", True, "detail", "screen", _grid("screen", "red"))
        restored = StepResult.from_dict(step.to_dict())
        self.assertIsNone(restored.screen_attributed)
        self.assertEqual(step.screen, restored.screen)

    def test_equality_tracks_the_serialised_shape(self) -> None:
        """A live result equals its own round trip, grid or no grid.

        The field is omitted from `to_dict`, so if it also took part in `__eq__`
        then `RunResult.from_dict(result.to_dict()) == result` would be `False`
        for any run that captured a grid — a comparison tests here and
        downstream make routinely, failing for a reason nothing in the JSON
        shows. `compare=False` keeps equality on the shape callers can see.
        """
        step = StepResult("name", True, "detail", "screen", _grid("screen", "red"))
        self.assertEqual(step, StepResult.from_dict(step.to_dict()))
        self.assertEqual(step, StepResult("name", True, "detail", "screen"))
        # Two grids of different colour are still the same step: same verdict,
        # same detail, same screen text.
        self.assertEqual(step, StepResult("name", True, "detail", "screen", _grid("screen", "green")))
        # The fields that do identify a step still separate them.
        self.assertNotEqual(step, StepResult("name", False, "detail", "screen"))
        self.assertNotEqual(step, StepResult("name", True, "detail", "other"))

    def test_a_whole_run_result_equals_its_round_trip(self) -> None:
        from termproof.models import AssertionResult, RunResult

        result = RunResult(
            recipe_name="r",
            passed=True,
            exit_code=0,
            duration_seconds=1.0,
            priority="P2",
            execution="scripted",
            renderer="default",
            score=1.0,
            steps=[StepResult("s", True, "", "screen", _grid("screen", "red"))],
            assertions=[AssertionResult("a", True, "")],
            artifacts={},
        )
        self.assertEqual(result, RunResult.from_dict(result.to_dict()))

    def test_a_step_carrying_a_grid_is_still_hashable_and_cheaply_so(self) -> None:
        """`frozen=True` derives `__hash__` from the compared fields only."""
        with_grid = StepResult("name", True, "detail", "screen", _grid("screen", "red"))
        self.assertEqual(hash(StepResult("name", True, "detail", "screen")), hash(with_grid))

    def test_the_repr_stays_readable_when_a_grid_is_attached(self) -> None:
        """An assertion failure must not print half a megabyte of cells."""
        import pyte

        screen = pyte.Screen(100, 32)
        pyte.Stream(screen).feed("hello world")
        step = StepResult("name", True, "detail", "hello world", attributed_screen_from_pyte(screen))
        self.assertLess(len(repr(step)), 400)
        self.assertIn("AttributedScreen(", repr(step))


class CaptureScreenTest(unittest.TestCase):
    def test_a_session_with_no_grid_reports_none_and_keeps_its_text(self) -> None:
        capture = capture_screen(_GridlessSession("hello"))
        self.assertEqual("hello", capture.screen)
        self.assertIsNone(capture.attributed)

    def test_a_session_with_a_grid_reports_both_from_one_read(self) -> None:
        capture = capture_screen(_GridSession("status", fg="green"))
        self.assertEqual("status", capture.screen)
        assert capture.attributed is not None
        self.assertEqual("green", capture.attributed.rows[0][0].fg)

    def test_the_text_comes_from_the_grid_so_the_two_cannot_disagree(self) -> None:
        """The `.txt` beside a step image must describe the same screen it does.

        A session that reads text and grid separately can hand back one of each
        from different instants — the tmux backend's two readings are two
        `capture-pane` runs. Deriving the text from the grid removes the window
        rather than narrowing it.
        """

        class Drifting(_GridlessSession):
            def __init__(self) -> None:
                super().__init__("stale text nobody should see")

            def screen_attributed(self) -> AttributedScreen:
                return _grid("live text")

        self.assertEqual("live text", capture_screen(Drifting()).screen)

    def test_grid_text_reproduces_the_flattening_a_pty_session_does(self) -> None:
        """`step.screen` must not shift meaning now that it comes from the grid.

        Assertions match against it and `steps/NN.txt` is written from it, so
        the derived text has to be the same string `screen_text` produced.
        """
        cases = (
            "\x1b[31mred\x1b[0m \x1b[1mbold\x1b[0m",
            "hello\r\nworld\r\n",
            "",
            "   trailing spaces   \r\n\r\n\r\n",
            "日本語テキスト wide\r\nmixed ascii\r\n",
            "\x1b[2J\x1b[H\x1b[48;5;33mbg\x1b[0m",
            "a" * 250,
            "\x1b[38;2;12;34;56mtruecolour\x1b[0m tail",
        )
        for cols, rows in ((100, 30), (80, 24), (20, 3)):
            for feed in cases:
                screen = pyte.Screen(cols, rows)
                pyte.Stream(screen).feed(feed)
                with self.subTest(size=(cols, rows), feed=feed[:20]):
                    self.assertEqual(
                        screen_text(screen),
                        grid_text(attributed_screen_from_pyte(screen)),
                    )


class StepActionCaptureTest(unittest.TestCase):
    def test_a_built_in_step_carries_the_grid_when_the_session_has_one(self) -> None:
        result = Press().execute(_GridSession("status", fg="red"), {"key": "enter"}, 1)
        assert result.screen_attributed is not None
        self.assertEqual("red", result.screen_attributed.rows[0][0].fg)

    def test_a_built_in_step_against_a_gridless_session_still_produces_a_result(self) -> None:
        result = Press().execute(_GridlessSession("plain screen"), {"key": "enter"}, 1)
        self.assertTrue(result.passed)
        self.assertEqual("plain screen", result.screen)
        self.assertIsNone(result.screen_attributed)

    def test_wait_for_regex_reports_the_screen_it_matched(self) -> None:
        """Not a fresh read afterwards: the image must show what the match saw."""
        session = _GridSession("READY", fg="green")
        result = WaitForRegex().execute(session, {"pattern": "READY"}, 1)
        self.assertTrue(result.passed)
        self.assertEqual("READY", result.screen)
        assert result.screen_attributed is not None
        self.assertEqual("green", result.screen_attributed.rows[0][0].fg)

    def test_wait_for_regex_validation_failures_survive_a_gridless_session(self) -> None:
        result = WaitForRegex().execute(_GridlessSession(), {"pattern": 42}, 1)
        self.assertFalse(result.passed)
        self.assertIn("must be a string", result.detail)
        self.assertIsNone(result.screen_attributed)

    def test_the_helper_is_exported_for_third_party_step_actions(self) -> None:
        result = step_result("custom", True, "did a thing", _GridSession("x", fg="blue"))
        assert result.screen_attributed is not None
        self.assertEqual("blue", result.screen_attributed.rows[0][0].fg)


class StepScreenshotColourTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.run_dir = Path(self._tmp.name)

    def _render(self, steps: list[StepResult], config: EvidenceConfig | None = None) -> Path:
        evidence._render_step_screens(
            self.run_dir, steps, 80, 24, SvgRenderer(), "svg", config or EvidenceConfig()
        )
        return self.run_dir / "steps"

    def test_the_grid_on_the_step_reaches_the_image(self) -> None:
        step_dir = self._render([StepResult("coloured", True, "", "status", _grid("status", "red"))])
        written = next(iter(step_dir.glob("*.svg")))
        self.assertIn("#ff7b72", _fills(written))
        self.assertTrue(_has_colour(written))

    def test_a_step_with_no_grid_still_gets_a_monochrome_screenshot(self) -> None:
        """The path that has always worked must keep working, unchanged."""
        step_dir = self._render([StepResult("plain", True, "", "status")])
        written = next(iter(step_dir.glob("*.svg")))
        self.assertFalse(_has_colour(written))
        self.assertEqual("status\n", (step_dir / "01-plain.txt").read_text(encoding="utf-8"))

    def test_a_run_mixing_both_renders_every_step(self) -> None:
        step_dir = self._render(
            [
                StepResult("with-grid", True, "", "status", _grid("status", "green")),
                StepResult("without-grid", True, "", "status"),
            ]
        )
        self.assertEqual(2, len(list(step_dir.glob("*.svg"))))
        self.assertTrue(_has_colour(step_dir / "01-with-grid.svg"))
        self.assertFalse(_has_colour(step_dir / "02-without-grid.svg"))

    def test_the_png_renderer_stays_monochrome_because_it_takes_no_grid(self) -> None:
        """An honest limit, pinned so it is not claimed away.

        `PngRenderer` implements only the text-only protocol, so a step grid
        cannot reach it. Colour in step screenshots is an SVG-renderer property.
        """
        self.assertFalse(hasattr(PngRenderer(), "render_attributed"))
        evidence._render_step_screens(
            self.run_dir,
            [StepResult("coloured", True, "", "status", _grid("status", "red"))],
            80,
            24,
            PngRenderer(),
            "png",
            EvidenceConfig(),
        )
        self.assertTrue((self.run_dir / "steps" / "01-coloured.png").exists())


class StepScreenshotDedupTest(unittest.TestCase):
    """The second-order effect: dedup's colour-awareness was inert for steps.

    `_render_step_screens` has always fingerprinted the grid rather than the
    text, so that a colour-only change counts as a change. It could not fire,
    because the grid it fingerprinted was rebuilt from `StepResult.screen` —
    already flattened, so a colour-only change was invisible to it. The first
    two tests are the before and after of exactly that.
    """

    COLOURS = ("green", "red")

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.run_dir = Path(self._tmp.name)

    def _dedup(self, steps: list[StepResult]) -> Path:
        evidence._render_step_screens(
            self.run_dir,
            steps,
            80,
            24,
            SvgRenderer(),
            "svg",
            EvidenceConfig(dedup_step_screenshots=True),
        )
        return self.run_dir / "steps"

    def test_a_colour_only_change_between_two_steps_is_now_detected(self) -> None:
        step_dir = self._dedup(
            [
                StepResult("idle", True, "", "status", _grid("status", "green")),
                StepResult("failed", True, "", "status", _grid("status", "red")),
            ]
        )
        written = sorted(path.name for path in step_dir.glob("*.svg"))
        self.assertEqual(["01-idle.svg", "02-failed.svg"], written)
        self.assertIn("#7ee787", _fills(step_dir / "01-idle.svg"))
        self.assertIn("#ff7b72", _fills(step_dir / "02-failed.svg"))
        manifest = json.loads(
            (step_dir / evidence.STEPS_MANIFEST_NAME).read_text(encoding="utf-8")
        )
        self.assertEqual([False, False], [entry["unchanged_from_previous"] for entry in manifest])

    def test_the_same_two_steps_without_grids_are_still_collapsed(self) -> None:
        """The defect, kept as a control.

        Identical text and no grid is genuinely one image: with nothing but the
        text to go on there is no difference to see. This is what every step
        looked like before the grid was carried, and it is what a session that
        cannot report one still looks like.
        """
        step_dir = self._dedup(
            [
                StepResult("idle", True, "", "status"),
                StepResult("failed", True, "", "status"),
            ]
        )
        self.assertEqual(["01-idle.svg"], sorted(p.name for p in step_dir.glob("*.svg")))
        manifest = json.loads(
            (step_dir / evidence.STEPS_MANIFEST_NAME).read_text(encoding="utf-8")
        )
        self.assertEqual([False, True], [entry["unchanged_from_previous"] for entry in manifest])
        self.assertEqual(2, len(list(step_dir.glob("*.txt"))))

    def test_two_identical_grids_still_dedup(self) -> None:
        step_dir = self._dedup(
            [
                StepResult("first", True, "", "status", _grid("status", "red")),
                StepResult("second", True, "", "status", _grid("status", "red")),
            ]
        )
        self.assertEqual(1, len(list(step_dir.glob("*.svg"))))

    def test_a_grid_and_a_gridless_step_with_the_same_text_are_not_confused(self) -> None:
        """A missing grid is not the same screen as a coloured one."""
        step_dir = self._dedup(
            [
                StepResult("coloured", True, "", "status", _grid("status", "red")),
                StepResult("plain", True, "", "status"),
            ]
        )
        self.assertEqual(2, len(list(step_dir.glob("*.svg"))))


class AnsiCaptureRobustnessTest(unittest.TestCase):
    """`capture-pane -e` returns escape sequences, and they can arrive broken.

    A capture is a snapshot of a pane a program is still painting, so a
    sequence can be cut anywhere. None of these may raise, and none may put a
    raw control byte into a cell — a stray byte makes the SVG invalid XML,
    which a rasterizer reports by writing a zero-byte image rather than by
    failing.
    """

    MALFORMED = (
        "\x1b",
        "\x1b[",
        "\x1b[3",
        "\x1b[31",
        "\x1b[31;",
        "\x1b[31;4",
        "\x1b[38;5",
        "\x1b[38;2;1;2",
        "\x1b[38;2;999;-1;2mX",
        "\x1b[999mX",
        "\x1b[;;;mX",
        "\x1b[abcmX",
        "\x1b]0;title\x07X",
        "\x1b[31mred\x1b",
        "\x1b[31mred\x1b[",
        "text\x1b[0",
        "\x1b[0m\x1b[0m\x1b[0m",
        "\x1b[1;31;4;7;9mstyled\x1b[0m tail",
        # Final bytes outside the letters. `isalpha()` scanning ran past these
        # and ate the next letter of real text with the escape.
        "before\x1b[1~after",
        "before\x1b[5@after",
        "before\x1b[2^after",
        "before\x1b[?25lafter",
        "before\x1b[1;2Hafter",
        "before\x1b[0`after",
        "before\x1b[3{after",
        # A sequence abandoned by a fresh ESC mid-parameters.
        "\x1b[31\x1b[32mX",
        "\x1b[38;5\x1b[0mX",
        # Intermediate bytes, which are also below the final-byte range.
        "before\x1b[1 qafter",
        "before\x1b[!pafter",
        # Non-CSI families. Only CSI was handled, so every one of these had its
        # ESC dropped and its body rendered as text — the OSC-8 hyperlink case
        # reached real step evidence through `capture-pane -e`.
        "before\x1b]8;;http://example.invalid\x1b\\\x1b]8;;\x1b\\after",
        "before\x1b]0;window title\x07after",
        "before\x1b]8;id=x;http://example.invalid\x07after",
        "before\x1bP1$r0m\x1b\\after",
        "before\x1bXsos\x1b\\after",
        "before\x1b^pm\x1b\\after",
        "before\x1b_apc\x1b\\after",
        "before\x1b(Bafter",
        "before\x1b)0after",
        "before\x1b#8after",
        "before\x1b7after",
        "before\x1b8after",
        "before\x1b=after",
        "before\x1bcafter",
        "before\x1b Fafter",
        # String sequences cut before their terminator, and abandoned ones.
        "before\x1b]8;;http://example.invalid",
        "before\x1bP1$r",
        "before\x1b]0;title\x1b[0mafter",
    )

    def test_no_string_sequence_leaks_its_body(self) -> None:
        """An OSC body is a URL or a window title, never screen content."""
        for payload in self.MALFORMED:
            with self.subTest(payload=payload):
                text = attributed_screen_from_ansi_text(payload, columns=80, rows=3).to_text()
                for leak in ("http://", "window title", "id=x", "$r0m", "sos", "apc"):
                    self.assertNotIn(leak, text)

    def test_no_payload_loses_the_text_around_the_sequence(self) -> None:
        """Consuming an escape must consume the escape and nothing else.

        Only the payloads that bracket a sequence with text on both sides. The
        deliberately truncated ones have no trailing text by construction: a
        sequence whose terminator never arrived swallows the rest of the line,
        which is the behaviour, not a loss.
        """
        for payload in self.MALFORMED:
            if not (payload.startswith("before") and payload.endswith("after")):
                continue
            with self.subTest(payload=payload):
                text = attributed_screen_from_ansi_text(payload, columns=60, rows=2).to_text()
                self.assertEqual("beforeafter", text)

    def test_no_malformed_sequence_raises_or_leaks_a_control_byte(self) -> None:
        for payload in self.MALFORMED:
            with self.subTest(payload=payload):
                screen = attributed_screen_from_ansi_text(payload, columns=40, rows=4)
                text = screen.to_text()
                self.assertNotIn("\x1b", text)
                for ch in text:
                    self.assertFalse(ch < " " and ch != "\n", f"control byte {ch!r} reached a cell")

    def test_a_malformed_capture_still_renders_well_formed_markup(self) -> None:
        from xml.etree import ElementTree

        from termproof.attributed import screen_svg

        for payload in self.MALFORMED:
            with self.subTest(payload=payload):
                markup = screen_svg(attributed_screen_from_ansi_text(payload, columns=40, rows=4))
                ElementTree.fromstring(markup)

    def test_a_partial_sequence_does_not_swallow_the_text_after_it(self) -> None:
        screen = attributed_screen_from_ansi_text("\x1b[3visible", columns=40, rows=2)
        self.assertIn("isible", screen.to_text())

    def test_an_unterminated_sequence_at_end_of_line_ends_the_line(self) -> None:
        screen = attributed_screen_from_ansi_text("ok\x1b[31", columns=40, rows=2)
        self.assertEqual("ok", screen.to_text())

    def test_a_style_set_on_one_row_carries_to_the_next_as_a_terminal_would(self) -> None:
        screen = attributed_screen_from_ansi_text("\x1b[31mred\nstill red", columns=40, rows=3)
        self.assertEqual("red", screen.rows[1][0].fg)


class StepScreenMemoryTest(unittest.TestCase):
    """A grid per step for a whole run has to be affordable.

    A grid built without sharing costs about half a megabyte per 100x32 screen,
    which over a hundred-step run is tens of megabytes retained for as long as
    the run holds its results. `_CellPool` shares one object between cells that
    compare equal, which a terminal screen is mostly made of.

    These assertions are the *property*: the cost is bounded by the number of
    distinct cells rather than the number of cells. They are deliberately not
    the byte counts quoted in the changelog, which come from a `tracemalloc`
    measurement over a real run — a machine-dependent figure has no business
    failing a test suite. The sizing helper here is a `sys.getsizeof` walk,
    which reads higher than `tracemalloc` because `getsizeof` on a
    key-sharing instance dict overstates what was actually allocated; it is
    fine for an upper bound, which is all it is used for.
    """

    def _grid_bytes(self, screen: AttributedScreen) -> int:
        seen: set[int] = set()
        total = sys.getsizeof(screen) + sys.getsizeof(screen.rows)
        for row in screen.rows:
            total += sys.getsizeof(row)
            for cell in row:
                if id(cell) in seen:
                    continue
                seen.add(id(cell))
                total += sys.getsizeof(cell) + sys.getsizeof(cell.text)
        return total

    def _pyte_screen(self, feed: str) -> Any:
        screen = pyte.Screen(100, 32)
        pyte.Stream(screen).feed(feed)
        return screen

    def test_equal_cells_are_one_object(self) -> None:
        screen = attributed_screen_from_pyte(self._pyte_screen("ordinary output\r\n"))
        blanks = [cell for row in screen.rows for cell in row if cell.text == " "]
        self.assertGreater(len(blanks), 1000)
        self.assertEqual(1, len({id(cell) for cell in blanks}))

    def test_a_typical_screen_costs_far_less_than_one_object_per_cell(self) -> None:
        feed = "\r\n".join(f"$ ordinary shell output line {index}" for index in range(20))
        screen = attributed_screen_from_pyte(self._pyte_screen(feed))
        cells = sum(len(row) for row in screen.rows)
        self.assertGreater(cells, 3000)
        # One cell object per cell would be several hundred KiB. The pointers
        # alone are ~8 bytes each, so this bound is well clear of the floor and
        # well under the unshared cost.
        self.assertLess(self._grid_bytes(screen), 120_000)

    def test_the_parsed_path_shares_cells_too(self) -> None:
        screen = attributed_screen_from_ansi_text(
            "\r\n".join("\x1b[32mready\x1b[0m" for _ in range(20)), columns=100, rows=32
        )
        cells = [cell for row in screen.rows for cell in row]
        self.assertGreater(len(cells), 80)
        self.assertLessEqual(len({id(cell) for cell in cells}), 10)


@unittest.skipUnless(importlib.util.find_spec("pexpect"), "pexpect is not installed")
class PtySessionGridTest(unittest.TestCase):
    """The pty backend can report a grid, and its two readings agree."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.cast = Path(self._tmp.name) / "session.cast"

    def test_a_live_pty_session_reports_colour_and_agrees_with_its_own_text(self) -> None:
        from termproof.session import TerminalSession

        argv = ["sh", "-c", "printf '\\033[31mred\\033[0m plain\\n'; sleep 0.5"]
        with TerminalSession(argv, self.cast, None, {}, 80, 24) as session:
            self.assertTrue(session.wait_for_text("red", 10.0))
            capture = capture_screen(session)
            self.assertEqual(session.screen, capture.screen)
        assert capture.attributed is not None
        self.assertEqual(["red", "red", "red"], [cell.fg for cell in capture.attributed.rows[0][:3]])
        self.assertEqual("default", capture.attributed.rows[0][4].fg)


#: A TUI whose second screen differs from its first in colour and nothing else.
#: `\x1b[2J\x1b[H` repaints from the top, so the two screens are the same
#: characters in the same cells — the case dedup was built to notice and could
#: not, because what it was handed had already been flattened.
_COLOUR_ONLY_TUI = """\
import sys

def paint(colour):
    sys.stdout.write("\\x1b[2J\\x1b[H")
    sys.stdout.write("\\x1b[" + colour + "mSTATUS OK\\x1b[0m\\n")
    sys.stdout.write("READY\\n")
    sys.stdout.flush()

paint("32")
sys.stdin.readline()
paint("31")
sys.stdin.readline()
"""


@unittest.skipUnless(importlib.util.find_spec("pexpect"), "pexpect is not installed")
class ColourOnlyChangeEndToEndTest(unittest.TestCase):
    """The reported second-order effect, through the whole pipeline.

    Dedup fingerprints the rendered grid rather than the screen text so that a
    colour-only change counts as a change. It could not fire on a real run,
    because the grid came from `StepResult.screen` and a colour-only change
    leaves that byte-identical. This drives a real pty session whose two screens
    differ only in colour and asserts on the manifest the run writes.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.tui = self.root / "colour_only_tui.py"
        self.tui.write_text(_COLOUR_ONLY_TUI, encoding="utf-8")

    def _recipe(self) -> Any:
        from termproof.models import CommandSpec, Recipe

        return Recipe(
            name="colour-only-change",
            command=CommandSpec(argv=[sys.executable, str(self.tui)], pty=True),
            cols=40,
            rows=6,
            timeout_seconds=30.0,
            steps=[
                # Gate on observed output before measuring anything: time to
                # first pty byte is environment-bound. See AGENTS.md.
                {"name": "green", "action": "wait_for_text", "text": "READY", "timeout_seconds": 15},
                {"name": "flip", "action": "send_line", "text": ""},
                {
                    "name": "red",
                    "action": "wait_for_idle",
                    "stable_seconds": 0.5,
                    "timeout_seconds": 15,
                },
                {"name": "finish", "action": "send_line", "text": ""},
            ],
        )

    def test_a_colour_only_change_survives_dedup_on_a_real_run(self) -> None:
        from dataclasses import replace

        from termproof.config import VerifierConfig
        from termproof.runner import VerificationRunner

        config = replace(
            VerifierConfig.builtin(),
            evidence=EvidenceConfig(dedup_step_screenshots=True),
        )
        result = VerificationRunner(config=config).run(self._recipe(), out_dir=self.root / "runs")
        self.assertTrue(result.passed, result.steps)

        step_dir = Path(result.artifacts["step_screenshots"])
        texts = {path.read_text(encoding="utf-8") for path in step_dir.glob("*.txt")}
        self.assertEqual(
            1, len(texts), "the fixture is meant to change colour and nothing else"
        )

        manifest = json.loads(
            (step_dir / evidence.STEPS_MANIFEST_NAME).read_text(encoding="utf-8")
        )
        distinct = {entry["screenshot"] for entry in manifest}
        self.assertEqual(
            2,
            len(distinct),
            f"a colour-only change was collapsed into one image: {manifest}",
        )
        fills: set[str] = set()
        for name in distinct:
            fills |= _fills(step_dir / name)
        # The green and the red the fixture paints, resolved by the renderer.
        self.assertIn("#7ee787", fills)
        self.assertIn("#ff7b72", fills)


@unittest.skipUnless(shutil.which("tmux"), "tmux is not installed")
class TmuxSessionGridTest(unittest.TestCase):
    """The tmux backend reports its grid through `capture-pane -e`."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.cast = Path(self._tmp.name) / "session.cast"

    def test_a_step_taken_against_tmux_carries_the_pane_colour(self) -> None:
        from termproof.tmux_session import TmuxBackend

        argv = ["sh", "-c", "printf '\\033[31mred\\033[0m plain\\n'; sleep 1"]
        with TmuxBackend().create_session(argv, self.cast, None, {}, 80, 24) as session:
            self.assertTrue(session.wait_for_text("red", 10.0))
            result = step_result("captured", True, "", session)
        assert result.screen_attributed is not None
        self.assertEqual(["red", "red", "red"], [cell.fg for cell in result.screen_attributed.rows[0][:3]])
        self.assertTrue(result.screen.startswith("red plain"))


@unittest.skipUnless(shutil.which("tmux"), "tmux is not installed")
class TmuxTextEquivalenceTest(unittest.TestCase):
    """The grid-derived text must equal what tmux itself calls the screen.

    `capture_screen` derives `StepResult.screen` from the grid so that the text
    and the image describe one instant. On the pty backend that is free — the
    grid and `screen_text` read the same `pyte.Screen`. On this one it is a
    claim about a parser: the grid is parsed out of `capture-pane -e` while
    `TmuxSession.screen` is `capture-pane` already flattened by tmux.

    That claim was false, and it was a regression rather than a limit. Before
    the grid was carried, a built-in step returned `session.screen`, which is
    correct; deriving it from a parser that only understood CSI turned
    `beforeTXTafter` into `before]8;;url\\TXT]8;;\\after` in both `steps/NN.txt`
    and the screenshot. Working output became corrupted output.

    So this compares the two readings against each other rather than against a
    literal, over content covering every escape family tmux can put in a pane.
    A future gap in the parser fails here instead of appearing in evidence.
    """

    PAYLOADS = {
        "osc 8 hyperlink": r"before\033]8;;http://example.invalid\033\\TXT\033]8;;\033\\after",
        "osc title": r"\033]0;window title\007visible text",
        "sgr colour and attributes": r"\033[31mred\033[0m \033[1mbold\033[0m \033[4munder\033[0m",
        "256 and truecolour": r"\033[38;5;196mx\033[38;2;1;2;3my\033[0m tail",
        "csi cursor moves": r"start\033[1;2H\033[Kmiddle\033[?25lend",
        "charset and two byte escapes": r"a\033(Bb\0337c\0338d",
        "wide characters": r"日本語 wide and ascii",
        "mixed": r"\033[32mok\033[0m \033]8;;http://a.invalid\033\\link\033]8;;\033\\ \033[1mdone\033[0m",
    }

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def test_the_derived_text_matches_the_plain_capture(self) -> None:
        from termproof.tmux_session import TmuxBackend

        for name, payload in self.PAYLOADS.items():
            with self.subTest(payload=name):
                cast = Path(self._tmp.name) / f"{name.replace(' ', '-')}.cast"
                argv = ["sh", "-c", f"printf '{payload}\\nSETTLED\\n'; sleep 2"]
                with TmuxBackend().create_session(argv, cast, None, {}, 80, 24) as session:
                    self.assertTrue(session.wait_for_text("SETTLED", 10.0))
                    plain = session.screen
                    derived = capture_screen(session).screen
                self.assertEqual(plain, derived)
                self.assertNotIn("\x1b", derived)

    def test_a_hyperlink_does_not_put_its_url_on_the_screen(self) -> None:
        """The reported reproducer, asserted against the literal it should be."""
        from termproof.tmux_session import TmuxBackend

        cast = Path(self._tmp.name) / "link.cast"
        argv = [
            "sh",
            "-c",
            r"printf 'before\033]8;;http://example.invalid\033\\TXT\033]8;;\033\\after\n'; sleep 2",
        ]
        with TmuxBackend().create_session(argv, cast, None, {}, 80, 24) as session:
            self.assertTrue(session.wait_for_text("after", 10.0))
            result = step_result("linked", True, "", session)
        self.assertEqual("beforeTXTafter", result.screen.splitlines()[0])
        assert result.screen_attributed is not None
        self.assertEqual(
            "beforeTXTafter", result.screen_attributed.text_lines(trim_right=True)[0]
        )


if __name__ == "__main__":
    unittest.main()
