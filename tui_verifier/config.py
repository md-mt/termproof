from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]


# -- built-in defaults (mirror current hardcoded behavior) ------------------

BUILTIN_DEFAULTS: dict[str, Any] = {
    "steps": {
        "wait_for_text": "tui_verifier.builtin_steps:WaitForText",
        "wait_for_idle": "tui_verifier.builtin_steps:WaitForIdle",
        "send_text": "tui_verifier.builtin_steps:SendText",
        "send_line": "tui_verifier.builtin_steps:SendLine",
        "press": "tui_verifier.builtin_steps:Press",
        "sleep": "tui_verifier.builtin_steps:Sleep",
    },
    "assertions": {
        "output_contains": "tui_verifier.builtin_assertions:OutputContains",
        "output_not_contains": "tui_verifier.builtin_assertions:OutputNotContains",
        "screen_contains": "tui_verifier.builtin_assertions:ScreenContains",
        "screen_not_contains": "tui_verifier.builtin_assertions:ScreenNotContains",
        "exit_code": "tui_verifier.builtin_assertions:ExitCode",
        "file_exists": "tui_verifier.builtin_assertions:FileExists",
        "file_contains": "tui_verifier.builtin_assertions:FileContains",
    },
    "agent_runners": {
        "codex": "tui_verifier.agent_driven:CodexCliAgentRunner",
    },
    "execution_modes": {
        "scripted_pty": "tui_verifier.builtin_modes:ScriptedPtyMode",
        "scripted_process": "tui_verifier.builtin_modes:ScriptedProcessMode",
        "agent_driven": "tui_verifier.builtin_modes:AgentDrivenMode",
    },
    "reporters": {
        "markdown": "tui_verifier.builtin_reporters:MarkdownReporter",
    },
    "screen_renderers": {
        "svg": "tui_verifier.builtin_renderers:SvgRenderer",
    },
    "video_backends": {
        "agg_ffmpeg": "tui_verifier.builtin_video:AggFfmpegBackend",
    },
    "session_backend": "tui_verifier.builtin_session:PexpectAsciinemaBackend",
    "defaults": {
        "timeout_seconds": 30.0,
        "cols": 100,
        "rows": 30,
        "video_fps": 60,
        "out_dir": ".tui-verifier/runs",
    },
}


# -- config model -----------------------------------------------------------

@dataclass(frozen=True)
class GlobalDefaults:
    timeout_seconds: float = 30.0
    cols: int = 100
    rows: int = 30
    video_fps: int = 60
    out_dir: str = ".tui-verifier/runs"


@dataclass(frozen=True)
class VerifierConfig:
    steps: dict[str, str]
    assertions: dict[str, str]
    agent_runners: dict[str, str]
    execution_modes: dict[str, str]
    reporters: dict[str, str]
    screen_renderers: dict[str, str]
    video_backends: dict[str, str]
    session_backend: str
    defaults: GlobalDefaults

    @classmethod
    def builtin(cls) -> "VerifierConfig":
        """Return a config populated entirely from BUILTIN_DEFAULTS."""
        return _from_mapping(BUILTIN_DEFAULTS)


# -- cascading YAML loader --------------------------------------------------

def load_config(
    project_path: Path | None = None,
    user_path: Path | None = None,
) -> VerifierConfig:
    """Cascade: builtin → user → project."""
    merged: dict[str, Any] = _deep_merge({}, BUILTIN_DEFAULTS)

    user_file = user_path or Path.home() / ".config" / "tui-verifier" / "config.yaml"
    if user_file.exists():
        merged = _deep_merge(merged, _load_yaml(user_file))

    project_file = (project_path or Path.cwd()) / ".tui-verifier" / "config.yaml"
    if project_file.exists():
        merged = _deep_merge(merged, _load_yaml(project_file))

    return _from_mapping(merged)


# -- internal helpers --------------------------------------------------------

def _from_mapping(data: dict[str, Any]) -> VerifierConfig:
    defaults_raw = data.get("defaults", {})
    return VerifierConfig(
        steps=dict(data.get("steps", {})),
        assertions=dict(data.get("assertions", {})),
        agent_runners=dict(data.get("agent_runners", {})),
        execution_modes=dict(data.get("execution_modes", {})),
        reporters=dict(data.get("reporters", {})),
        screen_renderers=dict(data.get("screen_renderers", {})),
        video_backends=dict(data.get("video_backends", {})),
        session_backend=str(data.get("session_backend", "")),
        defaults=GlobalDefaults(
            timeout_seconds=float(defaults_raw.get("timeout_seconds", 30.0)),
            cols=int(defaults_raw.get("cols", 100)),
            rows=int(defaults_raw.get("rows", 30)),
            video_fps=int(defaults_raw.get("video_fps", 60)),
            out_dir=str(defaults_raw.get("out_dir", ".tui-verifier/runs")),
        ),
    )


def _load_yaml(path: Path) -> dict[str, Any]:
    if yaml is None:
        raise RuntimeError("pyyaml is required to load config files; install pyyaml>=6.0")
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data if isinstance(data, dict) else {}


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge overlay into base. Overlay keys win at leaf level."""
    result = dict(base)
    for key, value in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
