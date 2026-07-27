from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from .models import AssertionResult, Recipe, RunResult, StepResult


def load_cached_result(
    cache_dir: Path,
    recipe: Recipe,
    renderer: str,
    renderer_argv: list[str],
    *,
    out_dir: Path,
    screen_renderer: str,
    video_backend: str,
    render_video: bool,
    video_fps: int,
) -> RunResult | None:
    key = _cache_key(
        recipe,
        renderer,
        renderer_argv,
        out_dir=out_dir,
        screen_renderer=screen_renderer,
        video_backend=video_backend,
        render_video=render_video,
        video_fps=video_fps,
    )
    if key is None:
        return None
    path = _cache_path(cache_dir, recipe, renderer)
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("key") != key:
        return None
    result = _result_from_dict(data["result"])
    if not result.passed or not _artifacts_exist(result):
        return None
    return replace(
        result,
        duration_seconds=0.0,
        artifacts={**result.artifacts, "cache": str(path)},
    )


def store_cached_result(
    cache_dir: Path,
    recipe: Recipe,
    renderer: str,
    renderer_argv: list[str],
    result: RunResult,
    *,
    out_dir: Path,
    screen_renderer: str,
    video_backend: str,
    render_video: bool,
    video_fps: int,
) -> None:
    if not result.passed:
        return
    key = _cache_key(
        recipe,
        renderer,
        renderer_argv,
        out_dir=out_dir,
        screen_renderer=screen_renderer,
        video_backend=video_backend,
        render_video=render_video,
        video_fps=video_fps,
    )
    if key is None:
        return
    path = _cache_path(cache_dir, recipe, renderer)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"key": key, "result": result.to_dict()}, indent=2) + "\n",
        encoding="utf-8",
    )


def _cache_key(
    recipe: Recipe,
    renderer: str,
    renderer_argv: list[str],
    *,
    out_dir: Path,
    screen_renderer: str,
    video_backend: str,
    render_video: bool,
    video_fps: int,
) -> str | None:
    if not recipe.source_path:
        return None
    recipe_path = Path(recipe.source_path)
    if not recipe_path.is_file():
        return None
    digest = hashlib.sha256()
    _hash_path(digest, recipe_path)
    for ci_path in sorted(recipe.ci_paths):
        candidate = Path(ci_path)
        path = candidate if candidate.is_absolute() else recipe_path.parent / candidate
        _hash_path(digest, path)
    payload = {
        "renderer": renderer,
        "renderer_argv": renderer_argv,
        "out_dir": str(out_dir),
        "screen_renderer": screen_renderer,
        "render_video": render_video,
        "video_backend": video_backend if render_video else "",
        "video_fps": video_fps if render_video else 0,
    }
    digest.update(json.dumps(payload, sort_keys=True).encode("utf-8"))
    return digest.hexdigest()


def _cache_path(cache_dir: Path, recipe: Recipe, renderer: str) -> Path:
    return cache_dir / _safe(recipe.name) / f"{_safe(renderer)}.json"


def _safe(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in value)
    return safe or "default"


def _hash_path(digest: Any, path: Path) -> None:
    digest.update(str(path).encode("utf-8"))
    if path.is_file():
        digest.update(path.read_bytes())
        return
    if path.is_dir():
        children = sorted(child for child in path.rglob("*") if child.is_file())
        for child in children:
            _hash_path(digest, child)
        return
    digest.update(b"<missing>")


def _result_from_dict(data: dict[str, Any]) -> RunResult:
    return RunResult(
        recipe_name=data["recipe_name"],
        passed=bool(data["passed"]),
        exit_code=data.get("exit_code"),
        duration_seconds=float(data["duration_seconds"]),
        priority=data["priority"],
        execution=data["execution"],
        renderer=data["renderer"],
        score=float(data["score"]),
        steps=[StepResult(**step) for step in data.get("steps", [])],
        assertions=[
            AssertionResult(**assertion)
            for assertion in data.get("assertions", [])
        ],
        artifacts=dict(data.get("artifacts", {})),
    )


def _artifacts_exist(result: RunResult) -> bool:
    for key in ("cast", "screenshot", "screen_text"):
        value = result.artifacts.get(key)
        if value and not Path(value).exists():
            return False
    return True
