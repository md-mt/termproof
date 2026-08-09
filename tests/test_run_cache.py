from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from termproof.config import (
    EvidenceConfig,
    PngRenderConfig,
    SvgRenderConfig,
    VideoConfig,
)
from termproof.models import RunResult, load_recipe
from termproof.run_cache import load_cached_result, store_cached_result


class RunCacheTest(unittest.TestCase):
    def test_load_cached_result_returns_last_passing_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            recipe_path = _write_recipe(root, "cached")
            recipe = load_recipe(recipe_path)
            screenshot = root / "run" / "final.svg"
            screenshot.parent.mkdir()
            screenshot.write_text("<svg/>\n", encoding="utf-8")
            result = _result("cached", screenshot)

            store_cached_result(
                root / "cache",
                recipe,
                "default",
                [],
                result,
                out_dir=root / "runs",
                screen_renderer="svg",
                video_backend="agg_ffmpeg",
                render_video=False,
                video_fps=60,
            )
            cached = load_cached_result(
                root / "cache",
                recipe,
                "default",
                [],
                out_dir=root / "runs",
                screen_renderer="svg",
                video_backend="agg_ffmpeg",
                render_video=False,
                video_fps=60,
            )

            self.assertIsNotNone(cached)
            self.assertEqual("cached", cached.recipe_name)
            self.assertEqual(0.0, cached.duration_seconds)
            self.assertIn("cache", cached.artifacts)

    def test_recipe_file_change_invalidates_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            recipe_path = _write_recipe(root, "cached")
            recipe = load_recipe(recipe_path)
            screenshot = root / "run" / "final.svg"
            screenshot.parent.mkdir()
            screenshot.write_text("<svg/>\n", encoding="utf-8")
            result = _result("cached", screenshot)

            store_cached_result(
                root / "cache",
                recipe,
                "default",
                [],
                result,
                out_dir=root / "runs",
                screen_renderer="svg",
                video_backend="agg_ffmpeg",
                render_video=False,
                video_fps=60,
            )
            recipe_path.write_text(
                recipe_path.read_text(encoding="utf-8") + "\n",
                encoding="utf-8",
            )

            cached = load_cached_result(
                root / "cache",
                recipe,
                "default",
                [],
                out_dir=root / "runs",
                screen_renderer="svg",
                video_backend="agg_ffmpeg",
                render_video=False,
                video_fps=60,
            )

            self.assertIsNone(cached)

    def test_ci_path_change_invalidates_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "fixture.txt"
            fixture.write_text("before\n", encoding="utf-8")
            recipe_path = _write_recipe(root, "cached", ci_paths=["fixture.txt"])
            recipe = load_recipe(recipe_path)
            screenshot = root / "run" / "final.svg"
            screenshot.parent.mkdir()
            screenshot.write_text("<svg/>\n", encoding="utf-8")
            result = _result("cached", screenshot)

            store_cached_result(
                root / "cache",
                recipe,
                "default",
                [],
                result,
                out_dir=root / "runs",
                screen_renderer="svg",
                video_backend="agg_ffmpeg",
                render_video=False,
                video_fps=60,
            )
            fixture.write_text("after\n", encoding="utf-8")

            cached = load_cached_result(
                root / "cache",
                recipe,
                "default",
                [],
                out_dir=root / "runs",
                screen_renderer="svg",
                video_backend="agg_ffmpeg",
                render_video=False,
                video_fps=60,
            )

            self.assertIsNone(cached)


class EvidenceConfigCacheKeyTest(unittest.TestCase):
    """A rendering knob changes the artifacts, so it must invalidate the cache.

    Otherwise ``--skip-unchanged`` replays a stored pass whose screenshots were
    rendered with the old settings, and the new configuration silently does
    nothing.
    """

    def _roundtrip(
        self,
        stored: EvidenceConfig,
        loaded: EvidenceConfig,
        *,
        render_video: bool = False,
    ) -> RunResult | None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            recipe = load_recipe(_write_recipe(root, "cached"))
            screenshot = root / "run" / "final.svg"
            screenshot.parent.mkdir()
            screenshot.write_text("<svg/>\n", encoding="utf-8")

            common = dict(
                out_dir=root / "runs",
                screen_renderer="svg",
                video_backend="agg_ffmpeg",
                render_video=render_video,
                video_fps=60,
            )
            store_cached_result(
                root / "cache",
                recipe,
                "default",
                [],
                _result("cached", screenshot),
                evidence=stored,
                **common,
            )
            return load_cached_result(
                root / "cache",
                recipe,
                "default",
                [],
                evidence=loaded,
                **common,
            )

    def test_unchanged_evidence_config_still_hits_the_cache(self) -> None:
        self.assertIsNotNone(
            self._roundtrip(EvidenceConfig(), EvidenceConfig())
        )

    def test_changed_screenshot_colour_invalidates_the_cache(self) -> None:
        for render_video in (False, True):
            with self.subTest(render_video=render_video):
                self.assertIsNone(
                    self._roundtrip(
                        EvidenceConfig(),
                        EvidenceConfig(svg=SvgRenderConfig(fg="#ff0000")),
                        render_video=render_video,
                    )
                )

    def test_changed_screenshot_scale_invalidates_the_cache(self) -> None:
        for render_video in (False, True):
            with self.subTest(render_video=render_video):
                self.assertIsNone(
                    self._roundtrip(
                        EvidenceConfig(),
                        EvidenceConfig(png=PngRenderConfig(scale=2)),
                        render_video=render_video,
                    )
                )

    def test_changed_video_setting_invalidates_the_cache(self) -> None:
        self.assertIsNone(
            self._roundtrip(
                EvidenceConfig(),
                EvidenceConfig(video=VideoConfig(crf=20)),
                render_video=True,
            )
        )

    def test_changed_video_setting_still_hits_the_cache_without_video(self) -> None:
        """A run that renders no video cannot produce a different artifact for it.

        ``video_backend`` and ``video_fps`` are already excluded from the key for
        exactly this reason, so the video knobs must drop out with them rather
        than busting every screenshot-only cache entry.
        """
        self.assertIsNotNone(
            self._roundtrip(
                EvidenceConfig(),
                EvidenceConfig(video=VideoConfig(crf=20, fps=30)),
                render_video=False,
            )
        )

    def test_changed_step_dedup_invalidates_the_cache(self) -> None:
        """Dedup changes which step screenshots exist, video or not."""
        for render_video in (False, True):
            with self.subTest(render_video=render_video):
                self.assertIsNone(
                    self._roundtrip(
                        EvidenceConfig(),
                        EvidenceConfig(dedup_step_screenshots=True),
                        render_video=render_video,
                    )
                )


def _write_recipe(root: Path, name: str, ci_paths: list[str] | None = None) -> Path:
    path = root / f"{name}.recipe.json"
    ci_paths_json = ""
    if ci_paths is not None:
        quoted = ", ".join(f'"{ci_path}"' for ci_path in ci_paths)
        ci_paths_json = f',\n  "ci_paths": [{quoted}]'
    path.write_text(
        f"""{{
  "name": "{name}",
  "command": {{"argv": ["python3", "-c", "print('ok')"], "pty": false}}{ci_paths_json}
}}
""",
        encoding="utf-8",
    )
    return path


def _result(name: str, screenshot: Path) -> RunResult:
    return RunResult(
        recipe_name=name,
        passed=True,
        exit_code=0,
        duration_seconds=1.0,
        priority="P2",
        execution="scripted",
        renderer="default",
        score=1.0,
        steps=[],
        assertions=[],
        artifacts={"screenshot": str(screenshot)},
    )


if __name__ == "__main__":
    unittest.main()
