from __future__ import annotations

import json
import shutil
import subprocess
import warnings
from datetime import datetime
from pathlib import Path
from typing import Any

from .agg_bundle import resolve_agg
from .models import RunResult, StepResult
from .screen import render_svg, replay_cast


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
) -> dict[str, str]:
    cast_path = run_dir / "session.cast"
    final_text, cols, rows = replay_cast(cast_path)
    final_txt = run_dir / "final.txt"
    final_svg = run_dir / "final.svg"
    final_txt.write_text(final_text + "\n", encoding="utf-8")
    if screen_renderer is not None:
        screen_renderer.render(final_text, final_svg, cols, rows)
    else:
        render_svg(final_text, final_svg, cols, rows)
    artifacts = {
        "cast": str(cast_path),
        "screenshot": str(final_svg),
        "screen_text": str(final_txt),
    }
    exit_code_path = run_dir / "session.exitcode"
    if exit_code_path.exists():
        artifacts["exit_code_file"] = str(exit_code_path)
    step_dir = _render_step_screens(run_dir, steps or [], cols, rows, screen_renderer)
    if step_dir is not None:
        artifacts["step_screenshots"] = str(step_dir)
    for name in ("agent_prompt.md", "agent_transcript.md", "agent_outcome.json"):
        path = run_dir / name
        if path.exists():
            artifacts[name.removesuffix(".md").removesuffix(".json")] = str(path)
    agg_path = resolve_agg()
    if render_video and agg_path:
        mp4_path = run_dir / "session.mp4"
        if video_backend is not None:
            video_backend.render(cast_path, mp4_path, video_fps)
        else:
            render_mp4(cast_path, mp4_path, video_fps)
        artifacts["video"] = str(mp4_path)
    return artifacts


def _render_step_screens(
    run_dir: Path,
    steps: list[StepResult],
    cols: int,
    rows: int,
    screen_renderer: Any = None,
) -> Path | None:
    if not steps:
        return None
    step_dir = run_dir / "steps"
    step_dir.mkdir(parents=True, exist_ok=True)
    for index, step in enumerate(steps, start=1):
        safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in step.name)
        path_base = step_dir / f"{index:02d}-{safe_name}"
        (path_base.with_suffix(".txt")).write_text(step.screen + "\n", encoding="utf-8")
        if screen_renderer is not None:
            screen_renderer.render(step.screen, path_base.with_suffix(".svg"), cols, rows)
        else:
            render_svg(step.screen, path_base.with_suffix(".svg"), cols, rows)
    return step_dir


def render_mp4(cast_path: Path, mp4_path: Path, fps: int = 60) -> None:
    agg_path = resolve_agg()
    if agg_path is None:
        return
    gif_path = mp4_path.with_suffix(".agg.gif")
    try:
        subprocess.run(
            [
                agg_path,
                "--quiet",
                "--fps-cap",
                str(fps),
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
                "yuv420p",
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


def write_result_files(run_dir: Path, result: RunResult) -> None:
    (run_dir / "result.json").write_text(
        json.dumps(result.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )
    (run_dir / "report.md").write_text(render_report(result), encoding="utf-8")


def render_report(result: RunResult) -> str:
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
        lines.append(f"- {name}: `{path}`")
    lines.extend(["", "## Assertions", ""])
    for assertion in result.assertions:
        mark = "PASS" if assertion.passed else "FAIL"
        lines.append(f"- {mark} `{assertion.name}` - {assertion.detail}")
    lines.extend(["", "## Steps", ""])
    for step in result.steps:
        mark = "PASS" if step.passed else "FAIL"
        lines.append(f"- {mark} `{step.name}` - {step.detail}")
    return "\n".join(lines) + "\n"
