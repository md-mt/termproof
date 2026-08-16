from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image, ImageDraw, ImageFont

from termproof import evidence
from termproof.attributed import AttributedScreen, attributed_screen_from_ansi_text
from termproof.builtin_renderers import PngRenderer, SvgRenderer
from termproof.builtin_video import AggFfmpegBackend
from termproof.config import (
    EvidenceConfig,
    PngRenderConfig,
    SvgRenderConfig,
    VerifierConfig,
    VideoConfig,
)
from termproof.models import StepResult
from termproof.screen import render_svg, replay_cast_attributed

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "examples" / "artifacts"
_FILL = re.compile(r'fill="(#[0-9a-fA-F]{6})"')


def _builtin_evidence() -> EvidenceConfig:
    return VerifierConfig.builtin().evidence


class CorpusByteIdentityTest(unittest.TestCase):
    """The renderer's output is pinned to the checked-in corpus.

    This gate began as the acceptance test for moving the rendering parameters
    into config: the extracted defaults had to reproduce the pre-configuration
    screenshots byte for byte. Attributed rendering deliberately changed the
    markup shape -- one ``<text>`` per cell rather than one per line -- so the
    corpus was regenerated and the gate's purpose changed with it. It now pins
    the renderer's output to those files: any change to the geometry, the
    palette, the escaping or the defaults has to be accompanied by a
    regenerated corpus, which puts the new bytes in the diff where a reviewer
    can see them.

    Each pair is rendered through the same path ``evidence.render_artifacts``
    uses for that artifact -- ``final.svg`` from the attributed replay of the
    cast, step screenshots from their recorded screen text. Pinning a path the
    pipeline does not use would gate nothing.
    """

    def _rendered_pairs(self) -> list[tuple[AttributedScreen, int, int, Path]]:
        pairs: list[tuple[AttributedScreen, int, int, Path]] = []
        for cast_path in sorted(ARTIFACTS.rglob("session.cast")):
            run_dir = cast_path.parent
            final_svg = run_dir / "final.svg"
            if not final_svg.exists():
                continue
            screen, cols, rows = replay_cast_attributed(cast_path)
            pairs.append((screen, cols, rows, final_svg))
            for step_txt in sorted((run_dir / "steps").glob("*.txt")):
                step_svg = step_txt.with_suffix(".svg")
                if step_svg.exists():
                    text = step_txt.read_text(encoding="utf-8").removesuffix("\n")
                    pairs.append(
                        (
                            attributed_screen_from_ansi_text(text, columns=cols, rows=rows),
                            cols,
                            rows,
                            step_svg,
                        )
                    )
        return pairs

    def test_corpus_is_present(self) -> None:
        """Guard the guard: an empty corpus would make the gate vacuous."""
        self.assertGreater(len(self._rendered_pairs()), 100)

    def test_default_svg_renderer_reproduces_example_corpus_byte_for_byte(self) -> None:
        renderer = SvgRenderer.from_config(_builtin_evidence())
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "candidate.svg"
            for screen, cols, rows, expected in self._rendered_pairs():
                renderer.render_attributed(screen, output, cols, rows)
                self.assertEqual(
                    expected.read_bytes(),
                    output.read_bytes(),
                    f"default config no longer reproduces {expected.relative_to(ROOT)}",
                )

    def test_the_corpus_still_holds_a_screen_that_is_not_monochrome(self) -> None:
        """A corpus of only-grey screens could not catch a fall back to plain text.

        `examples/colorstress` is the entry that carries colour; without it the
        byte-identity gate above would pass just as happily against a renderer
        that had thrown every attribute away.
        """
        fills = set()
        for screen, _, _, expected in self._rendered_pairs():
            if "colour-stress" in expected.parent.name:
                fills.update(_FILL.findall(expected.read_text(encoding="utf-8")))
        self.assertGreater(len(fills), 20, "the colour-stress corpus entry is missing or monochrome")

    def test_screen_render_svg_is_a_wrapper_over_the_renderer(self) -> None:
        """``screen.render_svg`` delegates; it must not regrow into a second copy."""
        renderer = SvgRenderer.from_config(_builtin_evidence())
        with tempfile.TemporaryDirectory() as tmp:
            from_function = Path(tmp) / "function.svg"
            from_renderer = Path(tmp) / "renderer.svg"
            for text, cols, rows in (("plain", 80, 24), ("\x1b[31mred\x1b[0m", 100, 30)):
                render_svg(text, from_function, cols, rows)
                renderer.render(text, from_renderer, cols, rows)
                self.assertEqual(from_function.read_bytes(), from_renderer.read_bytes())


class PngDefaultsTest(unittest.TestCase):
    def _legacy_png(self, text: str, output_path: Path, cols: int, rows: int) -> None:
        """The PNG renderer exactly as it was before the parameters moved to config."""
        font = ImageFont.load_default()
        bbox = font.getbbox("M")
        char_width = max(9, bbox[2] - bbox[0])
        line_height = max(18, bbox[3] - bbox[1] + 6)
        padding = 18
        width = max(320, cols * char_width + padding * 2)
        height = max(160, rows * line_height + padding * 2)
        image = Image.new("RGB", (int(width), int(height)), "#101418")
        draw = ImageDraw.Draw(image)
        for index, line in enumerate(text.splitlines()[:rows] or [""]):
            y = padding + line_height * index
            draw.text((padding, y), line[:cols], font=font, fill="#e6edf3")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(output_path, format="PNG")

    def test_default_png_renderer_is_byte_identical_to_the_previous_literals(self) -> None:
        text = "hello png\nsecond line with a much longer body of text\n\ttab"
        with tempfile.TemporaryDirectory() as tmp:
            legacy = Path(tmp) / "legacy.png"
            current = Path(tmp) / "current.png"
            self._legacy_png(text, legacy, 80, 24)
            PngRenderer.from_config(_builtin_evidence()).render(text, current, 80, 24)
            self.assertEqual(legacy.read_bytes(), current.read_bytes())

    def test_font_path_loads_a_truetype_face_at_the_scaled_size(self) -> None:
        config = PngRenderConfig(font_path="/fonts/mono.ttf", font_size=10, scale=2)
        with mock.patch.object(
            ImageFont, "truetype", return_value=ImageFont.load_default()
        ) as truetype:
            with tempfile.TemporaryDirectory() as tmp:
                output = Path(tmp) / "ttf.png"
                PngRenderer(config).render("hello", output, 80, 24)
                self.assertTrue(output.exists())
        truetype.assert_called_once_with("/fonts/mono.ttf", 20)

    def test_missing_font_path_surfaces_instead_of_silently_falling_back(self) -> None:
        config = PngRenderConfig(font_path="/no/such/font.ttf")
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(OSError):
                PngRenderer(config).render("hello", Path(tmp) / "x.png", 80, 24)

    def test_scale_enlarges_the_canvas(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            single = Path(tmp) / "1x.png"
            double = Path(tmp) / "2x.png"
            PngRenderer().render("hello", single, 80, 24)
            PngRenderer(PngRenderConfig(scale=2)).render("hello", double, 80, 24)
            with Image.open(single) as small, Image.open(double) as large:
                self.assertEqual(
                    (small.width * 2, small.height * 2), large.size
                )

    def test_colours_reach_the_image(self) -> None:
        config = PngRenderConfig(bg="#ff0000")
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "red.png"
            PngRenderer(config).render("", output, 80, 24)
            with Image.open(output) as image:
                self.assertEqual((255, 0, 0), image.convert("RGB").getpixel((0, 0)))


class VideoCommandTest(unittest.TestCase):
    def _commands(self, config: VideoConfig | None, fps: int = 60) -> list[list[str]]:
        with mock.patch.object(evidence, "resolve_agg", return_value="/bin/agg"), \
             mock.patch.object(evidence, "find_ffmpeg", return_value="/bin/ffmpeg"), \
             mock.patch.object(evidence.subprocess, "run") as run:
            evidence.render_mp4(Path("in.cast"), Path("out.mp4"), fps, config)
        return [call.args[0] for call in run.call_args_list]

    def test_default_config_builds_the_previous_command_lines(self) -> None:
        agg_cmd, ffmpeg_cmd = self._commands(_builtin_evidence().video)
        self.assertEqual(
            ["/bin/agg", "--quiet", "--fps-cap", "60", "in.cast", "out.agg.gif"],
            agg_cmd,
        )
        self.assertEqual(
            [
                "/bin/ffmpeg", "-y", "-loglevel", "error", "-i", "out.agg.gif",
                "-vf", "fps=60,scale=trunc(iw/2)*2:trunc(ih/2)*2",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart", "out.mp4",
            ],
            ffmpeg_cmd,
        )

    def test_fps_cap_defaults_to_the_effective_fps(self) -> None:
        agg_cmd, _ = self._commands(VideoConfig(), fps=24)
        self.assertEqual(["--fps-cap", "24"], agg_cmd[2:4])

    def test_configured_flags_are_appended_in_order(self) -> None:
        config = VideoConfig(
            fps_cap=24,
            pix_fmt="yuv444p",
            crf=20,
            preset="slow",
            tune="stillimage",
            idle_time_limit=0.5,
            last_frame_duration=1.5,
            theme="asciinema",
            font_size=16,
            font_family="DejaVu Sans Mono",
        )
        agg_cmd, ffmpeg_cmd = self._commands(config)
        self.assertEqual(
            [
                "/bin/agg", "--quiet", "--fps-cap", "24",
                "--idle-time-limit", "0.5", "--last-frame-duration", "1.5",
                "--theme", "asciinema", "--font-size", "16",
                "--font-family", "DejaVu Sans Mono",
                "in.cast", "out.agg.gif",
            ],
            agg_cmd,
        )
        self.assertEqual(
            ["-pix_fmt", "yuv444p", "-crf", "20", "-preset", "slow", "-tune", "stillimage"],
            ffmpeg_cmd[8:16],
        )

    def test_backend_forwards_its_configured_video_settings(self) -> None:
        backend = AggFfmpegBackend.from_config(
            EvidenceConfig(video=VideoConfig(pix_fmt="yuv444p"))
        )
        with mock.patch.object(evidence, "render_mp4") as render_mp4:
            backend.render(Path("in.cast"), Path("out.mp4"), 30)
        render_mp4.assert_called_once_with(
            Path("in.cast"), Path("out.mp4"), 30, backend.config
        )


class StepScreenScopeTest(unittest.TestCase):
    """The step-screen path must honour the same configuration as the final one."""

    STEPS = [
        StepResult("wait for prompt", True, "", "screen one"),
        StepResult("apply change", True, "", "screen two"),
    ]

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def test_step_screens_use_the_configured_svg_settings(self) -> None:
        run_dir = Path(self._tmp.name)
        config = EvidenceConfig(svg=SvgRenderConfig(bg="#ff0000"))
        evidence._render_step_screens(run_dir, self.STEPS, 80, 24, None, "svg", config)
        written = sorted((run_dir / "steps").glob("*.svg"))
        self.assertEqual(2, len(written))
        for path in written:
            self.assertIn("#ff0000", path.read_text(encoding="utf-8"))

    def test_render_artifacts_threads_config_to_final_and_step_screens(self) -> None:
        run_dir = Path(self._tmp.name) / "run"
        run_dir.mkdir()
        (run_dir / "session.cast").write_text(
            json.dumps({"version": 2, "width": 80, "height": 24}) + "\n",
            encoding="utf-8",
        )
        evidence.render_artifacts(
            run_dir,
            render_video=False,
            steps=list(self.STEPS),
            evidence_config=EvidenceConfig(svg=SvgRenderConfig(bg="#ff0000")),
        )
        rendered = [run_dir / "final.svg", *sorted((run_dir / "steps").glob("*.svg"))]
        self.assertEqual(3, len(rendered))
        for path in rendered:
            self.assertIn("#ff0000", path.read_text(encoding="utf-8"))


class RendererProtocolCompatibilityTest(unittest.TestCase):
    """`render_attributed` is optional; the text-only protocol still works.

    `tests/test_runner.py` pins that a renderer with no `from_config` is still
    *constructed*. This pins the other half: one with no `render_attributed` is
    still *called*, through `render`, even though the pipeline now has a grid to
    offer. A third-party renderer written against the published protocol must
    not need editing for this release.
    """

    class TextOnlyRenderer:
        name = "text_only"
        extension = "svg"

        def __init__(self) -> None:
            self.calls: list[str] = []

        def render(self, text: str, output_path: Path, cols: int, rows: int) -> None:
            self.calls.append(text)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(text, encoding="utf-8")

    class AttributedRenderer(TextOnlyRenderer):
        name = "attributed"

        def render_attributed(
            self, screen: AttributedScreen, output_path: Path, cols: int, rows: int
        ) -> None:
            self.calls.append("attributed")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(screen.to_text(trim_right=True), encoding="utf-8")

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.output = Path(self._tmp.name) / "shot.svg"
        self.screen = attributed_screen_from_ansi_text("\x1b[31mred\x1b[0m", columns=80, rows=24)

    def test_a_text_only_renderer_is_called_with_the_text(self) -> None:
        renderer = self.TextOnlyRenderer()
        evidence._render_screen(
            "red", self.output, 80, 24, renderer, SvgRenderConfig(), screen=self.screen
        )
        self.assertEqual(["red"], renderer.calls)
        self.assertEqual("red", self.output.read_text(encoding="utf-8"))

    def test_a_renderer_that_takes_a_grid_is_given_one(self) -> None:
        renderer = self.AttributedRenderer()
        evidence._render_screen(
            "red", self.output, 80, 24, renderer, SvgRenderConfig(), screen=self.screen
        )
        self.assertEqual(["attributed"], renderer.calls)

    def test_a_grid_capable_renderer_falls_back_when_there_is_no_grid(self) -> None:
        renderer = self.AttributedRenderer()
        evidence._render_screen(
            "red", self.output, 80, 24, renderer, SvgRenderConfig(), screen=None
        )
        self.assertEqual(["red"], renderer.calls)

    def test_a_text_only_renderer_survives_the_whole_pipeline(self) -> None:
        run_dir = Path(self._tmp.name) / "run"
        run_dir.mkdir()
        (run_dir / "session.cast").write_text(
            json.dumps({"version": 2, "width": 80, "height": 24}) + "\n", encoding="utf-8"
        )
        renderer = self.TextOnlyRenderer()
        artifacts = evidence.render_artifacts(
            run_dir,
            render_video=False,
            steps=[StepResult("only step", True, "", "hello")],
            screen_renderer=renderer,
        )
        self.assertTrue(Path(artifacts["screenshot"]).exists())
        self.assertEqual("hello", (run_dir / "steps" / "01-only-step.svg").read_text(encoding="utf-8"))


class StepScreenshotDedupTest(unittest.TestCase):
    STEPS = [
        StepResult("wait for prompt", True, "", "screen one"),
        StepResult("propose change", True, "", "screen one"),
        StepResult("apply change", True, "", "screen two"),
    ]

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def _render(self, config: EvidenceConfig) -> Path:
        run_dir = Path(self._tmp.name)
        evidence._render_step_screens(
            run_dir, self.STEPS, 80, 24, SvgRenderer(), "svg", config
        )
        return run_dir / "steps"

    def _run_dir_with_cast(self) -> Path:
        run_dir = Path(self._tmp.name) / "run"
        run_dir.mkdir()
        (run_dir / "session.cast").write_text(
            json.dumps({"version": 2, "width": 80, "height": 24}) + "\n",
            encoding="utf-8",
        )
        return run_dir

    def test_dedup_off_writes_every_screenshot_and_no_manifest(self) -> None:
        step_dir = self._render(EvidenceConfig())
        self.assertEqual(3, len(list(step_dir.glob("*.svg"))))
        self.assertFalse((step_dir / evidence.STEPS_MANIFEST_NAME).exists())

    def test_dedup_on_skips_the_repeat_image_but_keeps_every_step(self) -> None:
        step_dir = self._render(EvidenceConfig(dedup_step_screenshots=True))
        written = sorted(path.name for path in step_dir.glob("*.svg"))
        self.assertEqual(["01-wait-for-prompt.svg", "03-apply-change.svg"], written)
        # The step that produced no new image still has its own screen text.
        self.assertEqual(3, len(list(step_dir.glob("*.txt"))))

    def test_dedup_manifest_records_every_step(self) -> None:
        step_dir = self._render(EvidenceConfig(dedup_step_screenshots=True))
        manifest = json.loads(
            (step_dir / evidence.STEPS_MANIFEST_NAME).read_text(encoding="utf-8")
        )
        self.assertEqual(
            [
                {
                    "step": "01-wait-for-prompt",
                    "screenshot": "01-wait-for-prompt.svg",
                    "unchanged_from_previous": False,
                },
                {
                    "step": "02-propose-change",
                    "screenshot": "01-wait-for-prompt.svg",
                    "unchanged_from_previous": True,
                },
                {
                    "step": "03-apply-change",
                    "screenshot": "03-apply-change.svg",
                    "unchanged_from_previous": False,
                },
            ],
            manifest,
        )

    def _dedup_step_dir(self, steps: list[StepResult]) -> Path:
        run_dir = Path(self._tmp.name)
        evidence._render_step_screens(
            run_dir,
            steps,
            80,
            24,
            SvgRenderer(),
            "svg",
            EvidenceConfig(dedup_step_screenshots=True),
        )
        return run_dir / "steps"

    def test_a_colour_only_change_is_not_treated_as_unchanged(self) -> None:
        """Same text, different colour: two images, not one reused.

        Comparing `step.screen` as a string cannot see this, which is why dedup
        fingerprints the grid the screenshot is rendered from.

        Coverage of `_render_step_screens` as a helper, NOT of the shipped
        pipeline. The SGR escapes below are injected by hand; `StepResult.screen`
        is `session.screen`, which is pyte's already-flattened `display` and
        never contains an escape. So this branch of the fingerprint cannot fire
        on a real run today. It is worth keeping because it pins the behaviour
        the moment `StepResult` starts carrying a grid --- see
        `test_a_real_step_screen_carries_no_escapes` below, which is what pins
        the present-day reality.
        """
        step_dir = self._dedup_step_dir(
            [
                StepResult("idle", True, "", "\x1b[32mstatus\x1b[0m"),
                StepResult("failed", True, "", "\x1b[31mstatus\x1b[0m"),
            ]
        )
        written = sorted(step_dir.glob("*.svg"))
        self.assertEqual(2, len(written))
        self.assertIn("#7ee787", written[0].read_text(encoding="utf-8"))
        self.assertIn("#ff7b72", written[1].read_text(encoding="utf-8"))

    def test_identically_styled_screens_still_dedup(self) -> None:
        """Helper coverage, on the same terms as the test above."""
        step_dir = self._dedup_step_dir(
            [
                StepResult("first", True, "", "\x1b[31msame\x1b[0m"),
                StepResult("second", True, "", "\x1b[31msame\x1b[0m"),
            ]
        )
        self.assertEqual(1, len(list(step_dir.glob("*.svg"))))

    def test_a_real_step_screen_carries_no_escapes(self) -> None:
        """The present-day limit, pinned so the two tests above cannot mislead.

        A step screenshot is rendered from `StepResult.screen`, which the runner
        fills from `session.screen` -> `screen_text` -> pyte's `display`. That is
        already flattened, so no colour reaches a step image however colourful
        the session was. `final.svg` is unaffected: it renders from the
        attributed replay of the cast.

        When `StepResult` grows a grid, this test is the one that should fail.
        """
        import pyte

        from termproof.screen import screen_text

        screen = pyte.Screen(20, 2)
        pyte.Stream(screen).feed("\x1b[31mred\x1b[0m \x1b[1mbold\x1b[0m")
        text = screen_text(screen)
        self.assertEqual("red bold", text)
        self.assertNotIn("\x1b", text)

        step_dir = self._dedup_step_dir([StepResult("only", True, "", text)])
        rendered = next(iter(step_dir.glob("*.svg"))).read_text(encoding="utf-8")
        defaults = SvgRenderConfig()
        self.assertEqual({defaults.bg, defaults.fg}, set(_FILL.findall(rendered)))

    def test_dedup_compares_against_the_previous_step_only(self) -> None:
        """A screen that reappears after a different one is rendered again."""
        steps = [
            StepResult("a", True, "", "one"),
            StepResult("b", True, "", "two"),
            StepResult("c", True, "", "one"),
        ]
        run_dir = Path(self._tmp.name)
        evidence._render_step_screens(
            run_dir,
            steps,
            80,
            24,
            SvgRenderer(),
            "svg",
            EvidenceConfig(dedup_step_screenshots=True),
        )
        self.assertEqual(3, len(list((run_dir / "steps").glob("*.svg"))))

    def test_manifest_is_published_as_an_artifact_when_dedup_is_on(self) -> None:
        artifacts = evidence.render_artifacts(
            self._run_dir_with_cast(),
            render_video=False,
            steps=list(self.STEPS),
            evidence_config=EvidenceConfig(dedup_step_screenshots=True),
        )
        self.assertIn("step_manifest", artifacts)

    def test_no_manifest_artifact_by_default(self) -> None:
        artifacts = evidence.render_artifacts(
            self._run_dir_with_cast(), render_video=False, steps=list(self.STEPS)
        )
        self.assertNotIn("step_manifest", artifacts)


if __name__ == "__main__":
    unittest.main()
