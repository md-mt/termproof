from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from xml.etree import ElementTree

from termproof.attributed import attributed_screen_from_ansi_text
from termproof.config import SvgRenderConfig
from termproof.rsvg import RsvgPngRenderer


class _RecordingRunner:
    """Stands in for ``rsvg-convert``, capturing what it was handed."""

    def __init__(self, exit_code: int = 0) -> None:
        self.exit_code = exit_code
        self.calls: list[tuple[str, list[str], int]] = []
        self.svg = ""

    def __call__(self, executable: str, args: list[str], timeout: int) -> None:
        self.calls.append((executable, args, timeout))
        self.svg = Path(args[-1]).read_text(encoding="utf-8")
        if self.exit_code != 0:
            raise subprocess.CalledProcessError(self.exit_code, [executable, *args])
        Path(args[args.index("--output") + 1]).write_bytes(b"\x89PNG")


class RsvgPngRendererTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.runner = _RecordingRunner()

    def _renderer(self, **kwargs: object) -> RsvgPngRenderer:
        return RsvgPngRenderer(rsvg_path="/fake/rsvg-convert", runner=self.runner, **kwargs)  # type: ignore[arg-type]

    def test_it_rasterizes_through_the_runner(self) -> None:
        out = self.tmp / "shot.png"
        self._renderer().render("hello", out, 80, 24)
        self.assertEqual(1, len(self.runner.calls))
        executable, args, timeout = self.runner.calls[0]
        self.assertEqual("/fake/rsvg-convert", executable)
        self.assertEqual(["--output", str(out)], args[:2])
        self.assertEqual(30, timeout)
        self.assertEqual(b"\x89PNG", out.read_bytes())

    def test_the_svg_it_hands_over_is_the_attributed_one(self) -> None:
        self._renderer().render("\x1b[31mred", self.tmp / "shot.png", 80, 24)
        self.assertIn('fill="#ff7b72"', self.runner.svg)
        ElementTree.fromstring(self.runner.svg)

    def test_render_attributed_keeps_attributes_a_text_round_trip_would_lose(self) -> None:
        screen = attributed_screen_from_ansi_text("\x1b[1;4mbold", columns=80, rows=24)
        self._renderer().render_attributed(screen, self.tmp / "shot.png", 80, 24)
        self.assertIn('font-weight="700"', self.runner.svg)
        self.assertIn("underline", self.runner.svg)

    def test_configured_geometry_reaches_the_svg(self) -> None:
        renderer = self._renderer(config=SvgRenderConfig(bg="#ff0000"))
        renderer.render("x", self.tmp / "shot.png", 80, 24)
        self.assertIn('fill="#ff0000"', self.runner.svg)

    def test_the_scratch_svg_is_removed_afterwards(self) -> None:
        self._renderer().render("x", self.tmp / "shot.png", 80, 24)
        scratch = Path(self.runner.calls[0][1][-1])
        self.assertFalse(scratch.exists())

    def test_the_scratch_svg_is_removed_even_when_the_tool_fails(self) -> None:
        self.runner.exit_code = 1
        with self.assertRaises(subprocess.CalledProcessError):
            self._renderer().render("x", self.tmp / "shot.png", 80, 24)
        self.assertFalse(Path(self.runner.calls[0][1][-1]).exists())

    def test_a_missing_rasterizer_says_so_and_names_the_alternative(self) -> None:
        renderer = RsvgPngRenderer(runner=self.runner)
        renderer.rsvg_path = None
        with mock.patch("shutil.which", return_value=None):
            with self.assertRaises(RuntimeError) as raised:
                renderer.render("x", self.tmp / "shot.png", 80, 24)
        self.assertIn("rsvg-convert", str(raised.exception))
        self.assertIn("'png' renderer", str(raised.exception))

    def test_a_configured_path_wins_over_path_lookup(self) -> None:
        with mock.patch("shutil.which", return_value="/usr/bin/rsvg-convert"):
            self.assertEqual("/fake/rsvg-convert", self._renderer().resolve_rsvg())

    def test_output_directories_are_created(self) -> None:
        out = self.tmp / "nested" / "deeper" / "shot.png"
        self._renderer().render("x", out, 80, 24)
        self.assertTrue(out.is_file())

    def test_it_advertises_itself_as_a_png_renderer(self) -> None:
        self.assertEqual("png_rsvg", RsvgPngRenderer.name)
        self.assertEqual("png", RsvgPngRenderer.extension)


class RunToolTest(unittest.TestCase):
    def test_a_successful_command_returns_quietly(self) -> None:
        from termproof.rsvg import run_tool

        run_tool("/bin/sh", ["-c", "exit 0"], 10)

    def test_a_failing_command_raises_with_the_captured_stderr(self) -> None:
        from termproof.rsvg import run_tool

        with self.assertRaises(subprocess.CalledProcessError) as raised:
            run_tool("/bin/sh", ["-c", "echo boom >&2; exit 3"], 10)
        self.assertEqual(3, raised.exception.returncode)
        self.assertIn("boom", raised.exception.stderr)

    def test_undecodable_stderr_does_not_become_the_error(self) -> None:
        from termproof.rsvg import run_tool

        with self.assertRaises(subprocess.CalledProcessError) as raised:
            run_tool("/bin/sh", ["-c", "printf '\\xff\\xfe' >&2; exit 1"], 10)
        self.assertEqual(1, raised.exception.returncode)


if __name__ == "__main__":
    unittest.main()
