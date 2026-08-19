"""Rendering the artifacts a finished run produced.

Driven by a completed :class:`~termproof.models.RunResult`, whose step list the
recipe fixed before the run started. A caller that decides what to capture
*while* running — branching on what the screen shows — wants
:mod:`termproof.collector` instead; see :ref:`collector-versus-evidence` there
for what each writes and why they are not layered on one another.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import warnings
from datetime import datetime
from pathlib import Path
from typing import Any

from .agg_bundle import resolve_agg
from .attributed import AttributedScreen, attributed_screen_from_ansi_text
from .config import EvidenceConfig, SvgRenderConfig, VideoConfig
from .models import RunResult, StepResult
from .screen import replay_cast_both

STEPS_MANIFEST_NAME = "steps-manifest.json"


def new_run_dir(base_dir: Path, recipe_name: str, renderer: str = "default") -> Path:
    safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in recipe_name)
    safe_renderer = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in renderer)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    return base_dir / f"{timestamp}-{safe_name}-{safe_renderer}"


def render_artifacts(
    run_dir: Path,
    render_video: bool,
    video_fps: int = 60,
    steps: list[StepResult] | None = None,
    cols: int | None = None,
    rows: int | None = None,
    screen_renderer: Any = None,
    video_backend: Any = None,
    evidence_config: EvidenceConfig | None = None,
) -> dict[str, str]:
    evidence_config = evidence_config or EvidenceConfig()
    cast_path = run_dir / "session.cast"
    final_text, final_screen, cols, rows = replay_cast_both(cast_path)
    final_txt = run_dir / "final.txt"
    screenshot_ext = _screen_extension(screen_renderer)
    final_screenshot = run_dir / f"final.{screenshot_ext}"
    final_txt.write_text(final_text + "\n", encoding="utf-8")
    _render_screen(
        final_text,
        final_screenshot,
        cols,
        rows,
        screen_renderer,
        evidence_config.svg,
        # Straight off the emulator, so the screenshot keeps colour that a
        # round-trip through `final.txt` would already have thrown away.
        screen=final_screen,
    )
    artifacts = {
        "cast": str(cast_path),
        "screenshot": str(final_screenshot),
        "screen_text": str(final_txt),
    }
    exit_code_path = run_dir / "session.exitcode"
    if exit_code_path.exists():
        artifacts["exit_code_file"] = str(exit_code_path)
    step_dir = _render_step_screens(
        run_dir,
        steps or [],
        cols,
        rows,
        screen_renderer,
        screenshot_ext,
        evidence_config,
    )
    if step_dir is not None:
        artifacts["step_screenshots"] = str(step_dir)
        manifest_path = step_dir / STEPS_MANIFEST_NAME
        if manifest_path.exists():
            artifacts["step_manifest"] = str(manifest_path)
    for name in ("agent_prompt.md", "agent_transcript.md", "agent_outcome.json"):
        path = run_dir / name
        if path.exists():
            artifacts[name.removesuffix(".md").removesuffix(".json")] = str(path)
    if render_video:
        mp4_path = run_dir / "session.mp4"
        from .builtin_video import AggFfmpegBackend

        if video_backend is not None and not isinstance(video_backend, AggFfmpegBackend):
            video_backend.render(cast_path, mp4_path, video_fps)
            artifacts["video"] = str(mp4_path)
        else:
            missing = _missing_video_tools()
            if missing:
                warnings.warn(
                    "video evidence was requested (--video) but "
                    f"{' and '.join(missing)} could not be resolved; skipping video. "
                    "Install the missing tool(s) or use a platform wheel that bundles agg.",
                    stacklevel=2,
                )
            else:
                if video_backend is not None:
                    video_backend.render(cast_path, mp4_path, video_fps)
                else:
                    render_mp4(cast_path, mp4_path, video_fps, evidence_config.video)
                artifacts["video"] = str(mp4_path)
    return artifacts


def _missing_video_tools() -> list[str]:
    missing = []
    if not resolve_agg():
        missing.append("agg")
    if _resolve_ffmpeg() is None:
        missing.append("ffmpeg")
    return missing


def _resolve_ffmpeg() -> str | None:
    try:
        return find_ffmpeg()
    except Exception:
        return None


def _render_screen(
    text: str,
    output_path: Path,
    cols: int,
    rows: int,
    screen_renderer: Any,
    svg_config: SvgRenderConfig,
    screen: AttributedScreen | None = None,
) -> None:
    if screen_renderer is None:
        from .builtin_renderers import SvgRenderer

        screen_renderer = SvgRenderer(svg_config)
    # A renderer that can take a grid gets one, so nothing is lost re-parsing
    # text. Third-party renderers written against the text-only protocol keep
    # working untouched.
    render_attributed = getattr(screen_renderer, "render_attributed", None)
    if screen is not None and render_attributed is not None:
        render_attributed(screen, output_path, cols, rows)
    else:
        screen_renderer.render(text, output_path, cols, rows)


def _render_step_screens(
    run_dir: Path,
    steps: list[StepResult],
    cols: int,
    rows: int,
    screen_renderer: Any = None,
    screenshot_ext: str = "svg",
    evidence_config: EvidenceConfig | None = None,
) -> Path | None:
    if not steps:
        return None
    config = evidence_config or EvidenceConfig()
    dedup = config.dedup_step_screenshots
    step_dir = run_dir / "steps"
    step_dir.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, Any]] = []
    previous_fingerprint: str | None = None
    previous_screenshot = ""
    for index, step in enumerate(steps, start=1):
        safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in step.name)
        path_base = step_dir / f"{index:02d}-{safe_name}"
        (path_base.with_suffix(".txt")).write_text(step.screen + "\n", encoding="utf-8")
        screenshot_path = path_base.with_suffix(f".{screenshot_ext}")
        # Fingerprint the grid the screenshot is rendered from, not the text.
        # Two steps then share an image exactly when the image would be
        # identical — a colour-only change is a change, which comparing
        # `step.screen` as a string cannot express.
        #
        # `step.screen_attributed` is the grid the session reported at the
        # moment of the step, and is what makes that distinction reachable: a
        # grid rebuilt from `step.screen` can only be as colourful as the text,
        # which for a flattened screen is not at all. Sessions that report no
        # grid still land on the fallback, and still get their screenshot.
        screen = step.screen_attributed or attributed_screen_from_ansi_text(
            step.screen, columns=cols, rows=rows
        )
        fingerprint = screen.render_fingerprint()
        unchanged = dedup and fingerprint == previous_fingerprint
        if unchanged:
            # The step still happened and still has a screen; the manifest says
            # which already-written image represents it. Not dropped (that would
            # lose the step) and not symlinked (links do not survive artifact
            # upload).
            screenshot_name = previous_screenshot
        else:
            _render_screen(
                step.screen,
                screenshot_path,
                cols,
                rows,
                screen_renderer,
                config.svg,
                screen=screen,
            )
            screenshot_name = screenshot_path.name
        manifest.append(
            {
                "step": path_base.name,
                "screenshot": screenshot_name,
                "unchanged_from_previous": unchanged,
            }
        )
        previous_fingerprint = fingerprint
        previous_screenshot = screenshot_name
    if dedup:
        (step_dir / STEPS_MANIFEST_NAME).write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
    return step_dir


def _screen_extension(screen_renderer: Any = None) -> str:
    if screen_renderer is None:
        return "svg"
    extension = str(getattr(screen_renderer, "extension", "svg")).lstrip(".")
    return extension or "svg"


def _optional_flags(pairs: tuple[tuple[str, Any], ...]) -> list[str]:
    """Expand ``(flag, value)`` pairs, omitting any whose value is None."""
    flags: list[str] = []
    for flag, value in pairs:
        if value is not None:
            flags.extend([flag, str(value)])
    return flags


def render_mp4(
    cast_path: Path,
    mp4_path: Path,
    fps: int = 60,
    config: VideoConfig | None = None,
) -> None:
    config = config or VideoConfig()
    agg_path = resolve_agg()
    if agg_path is None:
        return
    gif_path = mp4_path.with_suffix(".agg.gif")
    fps_cap = fps if config.fps_cap is None else config.fps_cap
    try:
        subprocess.run(
            [
                agg_path,
                "--quiet",
                "--fps-cap",
                str(fps_cap),
                *_optional_flags(
                    (
                        ("--idle-time-limit", config.idle_time_limit),
                        ("--last-frame-duration", config.last_frame_duration),
                        ("--theme", config.theme),
                        ("--font-size", config.font_size),
                        ("--font-family", config.font_family),
                    )
                ),
                str(cast_path),
                str(gif_path),
            ],
            check=True,
        )
        ffmpeg = find_ffmpeg()
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-loglevel",
                "error",
                "-i",
                str(gif_path),
                "-vf",
                f"fps={fps},scale=trunc(iw/2)*2:trunc(ih/2)*2",
                "-pix_fmt",
                config.pix_fmt,
                *_optional_flags(
                    (
                        ("-crf", config.crf),
                        ("-preset", config.preset),
                        ("-tune", config.tune),
                    )
                ),
                "-movflags",
                "+faststart",
                str(mp4_path),
            ],
            check=True,
        )
    finally:
        gif_path.unlink(missing_ok=True)


def find_ffmpeg() -> str:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        return ffmpeg
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def write_result_files(
    run_dir: Path,
    result: RunResult,
    video_base_url: str | None = None,
) -> None:
    (run_dir / "result.json").write_text(
        json.dumps(result.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )
    report_text = render_report(result, video_base_url=video_base_url)
    (run_dir / "report.md").write_text(report_text, encoding="utf-8")
    # Also persist hosted artifact mapping when video_base_url is set
    if video_base_url and result.artifacts.get("video"):
        hosted = _hosted_video_url(result.artifacts["video"], run_dir, video_base_url)
        if hosted:
            hosted_map = run_dir / "hosted-artifacts.json"
            hosted_map.write_text(
                json.dumps({"video": hosted, "source_video": result.artifacts["video"]}, indent=2) + "\n",
                encoding="utf-8",
            )


def _hosted_video_url(video_path: str, run_dir: Path, base_url: str) -> str | None:
    """Map a local video path to a hosted URL relative to ``run_dir`` parent."""
    try:
        # run_dir is like .termproof/ci/2026...-recipe-default
        # hosted key should be like {prefix}/{relative_to_out}
        out_root = run_dir.parent
        rel = (
            Path(video_path).relative_to(out_root).as_posix()
            if Path(video_path).is_absolute()
            else Path(video_path).as_posix()
        )
        # If path is absolute-style (.termproof/ci/...), strip leading out_root-ish prefix
        # Fallback: use just the filename path under run_dir
        if rel.startswith(".termproof/"):
            # try to make it relative to out_root
            try:
                rel = Path(video_path).relative_to(out_root).as_posix()
            except ValueError:
                rel = Path(video_path).name
        else:
            try:
                rel = Path(video_path).relative_to(out_root).as_posix()
            except ValueError:
                rel = f"{run_dir.name}/{Path(video_path).name}"
        base = base_url.rstrip("/")
        from urllib.parse import quote as _quote

        return f"{base}/{_quote(rel, safe='/._-~')}"
    except Exception:
        return None


def render_report(result: RunResult, video_base_url: str | None = None) -> str:
    verdict = "PASS" if result.passed else "FAIL"
    lines = [
        f"# TUI Verification - {verdict}",
        "",
        f"- Recipe: `{result.recipe_name}`",
        f"- Renderer: `{result.renderer}`",
        f"- Priority: `{result.priority}`",
        f"- Execution: `{result.execution}`",
        f"- Score: `{result.score:.2f}`",
        f"- Exit code: `{result.exit_code}`",
        f"- Duration: `{result.duration_seconds:.2f}s`",
        "",
        "## Artifacts",
        "",
    ]
    for name, path in result.artifacts.items():
        display_path = path
        if video_base_url and name == "video":
            try:
                run_dir = Path(path).parent
                hosted = _hosted_video_url(path, run_dir, video_base_url)
                if hosted:
                    display_path = hosted
            except Exception:
                pass
        lines.append(f"- {name}: `{display_path}`")
    lines.extend(["", "## Assertions", ""])
    for assertion in result.assertions:
        mark = "PASS" if assertion.passed else "FAIL"
        lines.append(f"- {mark} `{assertion.name}` - {assertion.detail}")
    lines.extend(["", "## Steps", ""])
    for step in result.steps:
        mark = "PASS" if step.passed else "FAIL"
        lines.append(f"- {mark} `{step.name}` - {step.detail}")
    return "\n".join(lines) + "\n"
