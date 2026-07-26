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
        "wait_for_text": "termproof.builtin_steps:WaitForText",
        "wait_for_idle": "termproof.builtin_steps:WaitForIdle",
        "send_text": "termproof.builtin_steps:SendText",
        "send_line": "termproof.builtin_steps:SendLine",
        "press": "termproof.builtin_steps:Press",
        "sleep": "termproof.builtin_steps:Sleep",
    },
    "assertions": {
        "output_contains": "termproof.builtin_assertions:OutputContains",
        "output_not_contains": "termproof.builtin_assertions:OutputNotContains",
        "screen_contains": "termproof.builtin_assertions:ScreenContains",
        "screen_not_contains": "termproof.builtin_assertions:ScreenNotContains",
        "exit_code": "termproof.builtin_assertions:ExitCode",
        "file_exists": "termproof.builtin_assertions:FileExists",
        "file_contains": "termproof.builtin_assertions:FileContains",
    },
    "agent_runners": {
        "codex": "termproof.agent_driven:CodexCliAgentRunner",
    },
    "execution_modes": {
        "scripted_pty": "termproof.builtin_modes:ScriptedPtyMode",
        "scripted_process": "termproof.builtin_modes:ScriptedProcessMode",
        "agent_driven": "termproof.builtin_modes:AgentDrivenMode",
    },
    "reporters": {
        "markdown": "termproof.builtin_reporters:MarkdownReporter",
    },
    "screen_renderers": {
        "svg": "termproof.builtin_renderers:SvgRenderer",
    },
    "video_backends": {
        "agg_ffmpeg": "termproof.builtin_video:AggFfmpegBackend",
    },
    "session_backend": "termproof.builtin_session:PexpectAsciinemaBackend",
    "defaults": {
        "timeout_seconds": 30.0,
        "cols": 100,
        "rows": 30,
        "video_fps": 60,
        "out_dir": ".termproof/runs",
    },
}


# -- config model -----------------------------------------------------------

@dataclass(frozen=True)
class GlobalDefaults:
    timeout_seconds: float = 30.0
    cols: int = 100
    rows: int = 30
    video_fps: int = 60
    out_dir: str = ".termproof/runs"


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

# Compatibility reads are deliberately limited to configuration and plugin
# references. The renamed distribution, import package, and executable expose
# only the TermProof names.
LEGACY_USER_CONFIG_DIR = "tui-verifier"
LEGACY_PROJECT_CONFIG_DIR = ".tui-verifier"
LEGACY_PLUGIN_MODULE_PREFIX = "tui_verifier."
CURRENT_PLUGIN_MODULE_PREFIX = "termproof."


def load_config(
    project_path: Path | None = None,
    user_path: Path | None = None,
    config_path: Path | None = None,
) -> VerifierConfig:
    """Load builtin, migrated user, migrated project, and explicit configuration.

    Normal discovery cascades in this order: builtin, legacy user config,
    TermProof user config, legacy project config, then TermProof project config.
    The newer location wins only for values it provides; legacy files are never
    changed on disk. Passing ``user_path`` loads exactly that user config and
    skips implicit user-location discovery. ``config_path`` is an explicit CLI
    config file and is applied after the normal cascade, so its values win
    without bypassing compatible discovery.
    """
    merged: dict[str, Any] = _deep_merge({}, BUILTIN_DEFAULTS)
    project_root = project_path or Path.cwd()

    if user_path is not None:
        user_files = [user_path]
    else:
        config_home = Path.home() / ".config"
        user_files = [
            config_home / LEGACY_USER_CONFIG_DIR / "config.yaml",
            config_home / "termproof" / "config.yaml",
        ]
    project_files = [
        project_root / LEGACY_PROJECT_CONFIG_DIR / "config.yaml",
        project_root / ".termproof" / "config.yaml",
    ]
    explicit_files = [config_path] if config_path is not None else []

    for config_file in [*user_files, *project_files, *explicit_files]:
        if config_file.exists():
            merged = _deep_merge(merged, _load_yaml(config_file))

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
            out_dir=str(defaults_raw.get("out_dir", ".termproof/runs")),
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
