from __future__ import annotations

import math
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, get_args, get_type_hints

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
        "wait_for_regex": "termproof.builtin_steps:WaitForRegex",
    },
    "assertions": {
        "output_contains": "termproof.builtin_assertions:OutputContains",
        "output_not_contains": "termproof.builtin_assertions:OutputNotContains",
        "screen_contains": "termproof.builtin_assertions:ScreenContains",
        "screen_not_contains": "termproof.builtin_assertions:ScreenNotContains",
        "exit_code": "termproof.builtin_assertions:ExitCode",
        "file_exists": "termproof.builtin_assertions:FileExists",
        "file_contains": "termproof.builtin_assertions:FileContains",
        "json_schema": "termproof.builtin_assertions:JsonSchema",
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
        "junit_xml": "termproof.builtin_reporters:JUnitXmlReporter",
    },
    "screen_renderers": {
        "svg": "termproof.builtin_renderers:SvgRenderer",
        "png": "termproof.builtin_renderers:PngRenderer",
    },
    "video_backends": {
        "agg_ffmpeg": "termproof.builtin_video:AggFfmpegBackend",
    },
    "session_backend": "termproof.builtin_session:PexpectAsciinemaBackend",
    "docker": {
        "image": "",
        "workdir": "/workspace",
        "volumes": [{"host": ".", "container": "/workspace"}],
        "env": {},
    },
    "defaults": {
        "idle_cap_seconds": 3.0,
    },
    # Evidence-rendering parameters. Every value here reproduces the behavior
    # that was previously hardcoded in the renderers and the video pipeline, so
    # an unconfigured run is byte-identical to one from before they were
    # extracted.
    "evidence": {
        "svg": {
            "char_width": 9,
            "line_height": 20,
            "padding": 18,
            "font_size": 14,
            "font_family": "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace",
            "fg": "#e6edf3",
            "bg": "#101418",
        },
        "png": {
            "scale": 1,
            "padding": 18,
            "font_size": 14,
            "font_path": None,
            "fg": "#e6edf3",
            "bg": "#101418",
        },
        "video": {
            "fps": 60,
            "fps_cap": None,
            "pix_fmt": "yuv420p",
            "crf": None,
            "preset": None,
            "tune": None,
            "idle_time_limit": None,
            "last_frame_duration": None,
            "theme": None,
            "font_size": None,
            "font_family": None,
        },
    },
}


# -- config model -----------------------------------------------------------

@dataclass(frozen=True)
class GlobalDefaults:
    # Cap for the post-script idle wait in PTY mode. None means wait for
    # quiescence up to the recipe timeout instead of a fixed cap.
    idle_cap_seconds: float | None = 3.0


@dataclass(frozen=True)
class DockerBackendConfig:
    image: str = ""
    workdir: str = "/workspace"
    volumes: list[Any] = field(
        default_factory=lambda: [{"host": ".", "container": "/workspace"}]
    )
    env: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SvgRenderConfig:
    char_width: int = 9
    line_height: int = 20
    padding: int = 18
    font_size: int = 14
    font_family: str = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"
    fg: str = "#e6edf3"
    bg: str = "#101418"


@dataclass(frozen=True)
class PngRenderConfig:
    # ``font_path`` of None keeps PIL's bundled proportional bitmap face.
    # ``font_size`` is only consulted when a font path is given.
    # ``scale`` multiplies the canvas, the padding and the line pitch, but not
    # the glyphs of the default bitmap face, which has one fixed size. Scaling
    # up therefore spreads the same text over a larger image unless
    # ``font_path`` is also set, which is what yields a higher-DPI screenshot.
    scale: int = 1
    padding: int = 18
    font_size: int = 14
    font_path: str | None = None
    fg: str = "#e6edf3"
    bg: str = "#101418"


@dataclass(frozen=True)
class VideoConfig:
    # None means "omit the flag", so the default command line is the one the
    # pipeline built before these were configurable. ``fps_cap`` of None keeps
    # agg's cap tied to the effective output fps, as it was.
    fps: int = 60
    fps_cap: int | None = None
    pix_fmt: str = "yuv420p"
    crf: int | None = None
    preset: str | None = None
    tune: str | None = None
    idle_time_limit: float | None = None
    last_frame_duration: float | None = None
    theme: str | None = None
    font_size: int | None = None
    font_family: str | None = None


@dataclass(frozen=True)
class EvidenceConfig:
    svg: SvgRenderConfig = SvgRenderConfig()
    png: PngRenderConfig = PngRenderConfig()
    video: VideoConfig = VideoConfig()


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
    docker: DockerBackendConfig
    defaults: GlobalDefaults
    evidence: EvidenceConfig

    @classmethod
    def builtin(cls) -> VerifierConfig:
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

def _parse_idle_cap_seconds(value: Any) -> float | None:
    """Parse ``idle_cap_seconds``, rejecting non-finite or negative values.

    A negative or NaN/Inf value would silently eliminate idle waiting (a
    ``min()`` cap of ``-1`` or ``nan`` never waits), so config loading must
    refuse it instead of degrading behavior invisibly.
    """
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"idle_cap_seconds must be a finite nonnegative number, got {value!r}"
        ) from error
    if not math.isfinite(parsed) or parsed < 0:
        raise ValueError(
            f"idle_cap_seconds must be a finite nonnegative number, got {value!r}"
        )
    return parsed


def _check_field_type(label: str, name: str, hint: Any, value: Any) -> None:
    """Reject a value whose type its field cannot honor.

    A quoted number or a stray mapping loads happily and then fails deep inside
    a renderer, in an error that no longer names the option that was wrong.
    """
    declared = get_args(hint) or (hint,)
    accepted = (*declared, int) if float in declared else declared
    if isinstance(value, accepted) and not (
        isinstance(value, bool) and bool not in declared
    ):
        return
    names = " or ".join(
        "null" if arg is type(None) else arg.__name__ for arg in declared
    )
    raise ValueError(f"{label}.{name} must be {names}, got {value!r}")


def _section(cls: type, raw: Any, label: str) -> Any:
    """Build a frozen config dataclass from a YAML mapping.

    Unknown keys are rejected rather than ignored: a misspelled rendering knob
    that silently does nothing is indistinguishable from one that had no effect.
    """
    values = dict(raw or {})
    hints = get_type_hints(cls)
    known = {field_.name for field_ in fields(cls)}
    unknown = sorted(set(values) - known)
    if unknown:
        raise ValueError(
            f"unknown {label} option(s) {unknown}; known options: {sorted(known)}"
        )
    for name, value in values.items():
        _check_field_type(label, name, hints[name], value)
    return cls(**values)


def _evidence_from_mapping(raw: Any) -> EvidenceConfig:
    values = dict(raw or {})
    evidence = EvidenceConfig(
        svg=_section(SvgRenderConfig, values.pop("svg", {}), "evidence.svg"),
        png=_section(PngRenderConfig, values.pop("png", {}), "evidence.png"),
        video=_section(VideoConfig, values.pop("video", {}), "evidence.video"),
    )
    if values:
        raise ValueError(f"unknown evidence option(s) {sorted(values)}")
    return evidence


def _from_mapping(data: dict[str, Any]) -> VerifierConfig:
    defaults_raw = data.get("defaults", {})
    docker_raw = data.get("docker", {})
    docker_volumes = docker_raw.get("volumes", [{"host": ".", "container": "/workspace"}])
    return VerifierConfig(
        steps=dict(data.get("steps", {})),
        assertions=dict(data.get("assertions", {})),
        agent_runners=dict(data.get("agent_runners", {})),
        execution_modes=dict(data.get("execution_modes", {})),
        reporters=dict(data.get("reporters", {})),
        screen_renderers=dict(data.get("screen_renderers", {})),
        video_backends=dict(data.get("video_backends", {})),
        session_backend=str(data.get("session_backend", "")),
        docker=DockerBackendConfig(
            image=str(docker_raw.get("image", "")),
            workdir=str(docker_raw.get("workdir", "/workspace")),
            volumes=list(docker_volumes) if isinstance(docker_volumes, list) else [],
            env={
                str(key): str(value)
                for key, value in dict(docker_raw.get("env", {})).items()
            },
        ),
        defaults=GlobalDefaults(
            idle_cap_seconds=_parse_idle_cap_seconds(
                defaults_raw.get("idle_cap_seconds", 3.0)
            ),
        ),
        evidence=_evidence_from_mapping(data.get("evidence", {})),
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
