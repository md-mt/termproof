from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field, fields, replace
from pathlib import Path
from typing import Any, get_args, get_type_hints

from .attributed import (
    DEFAULT_BG,
    DEFAULT_CELL_H,
    DEFAULT_CELL_W,
    DEFAULT_FG,
    DEFAULT_FONT_PX,
    DEFAULT_PADDING,
    FONT_STACK,
    SvgStyle,
)

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]


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


# Smallest useful rasterised screenshot, in pixels. A PNG is a fixed pixel
# count, so below roughly this a screenshot stops being readable evidence; an
# SVG is resolution independent and needs no floor, which is why this lives
# here rather than in the canonical geometry. Every renderer that turns the
# markup into pixels applies it: ``PngRenderer`` directly, and the two that
# rasterise the SVG at its intrinsic size through ``SvgRenderConfig``'s
# :meth:`~SvgRenderConfig.raster_style`.
RASTER_MIN_WIDTH = 320
RASTER_MIN_HEIGHT = 160


@dataclass(frozen=True)
class SvgRenderConfig:
    """The ``evidence.svg`` YAML section: SVG geometry as a *run* configures it.

    :class:`~termproof.attributed.SvgStyle` is canonical. Every default below is
    the matching ``DEFAULT_*`` constant from :mod:`termproof.attributed`, under
    the name the YAML uses (``char_width`` for ``cell_w``, ``line_height`` for
    ``cell_h``, ``font_size`` for ``font_px``), and :meth:`style` is the one
    place that translates between the two. Nothing here restates a value.

    Reach for this type when a run's YAML or a renderer plugin should be able to
    override the geometry; reach for ``SvgStyle`` when calling
    :func:`~termproof.attributed.screen_svg` directly. They render identically
    when unconfigured, which they did not always do — CHANGELOG.md says what
    moved and how to pin the old values.
    """

    char_width: float = DEFAULT_CELL_W
    line_height: float = DEFAULT_CELL_H
    padding: int = DEFAULT_PADDING
    font_size: int = DEFAULT_FONT_PX
    font_family: str = FONT_STACK
    fg: str = DEFAULT_FG
    bg: str = DEFAULT_BG
    min_width: int = 0
    min_height: int = 0

    def style(self, cols: int, rows: int) -> SvgStyle:
        """Vector geometry for a *cols* x *rows* grid, for an SVG-emitting renderer.

        No canvas floor unless one is asked for: ``min_width``/``min_height``
        default to zero, as they do on ``SvgStyle``, so a three-row screen
        renders a three-row canvas rather than a three-row grid marooned in a
        320x160 field. An SVG is resolution independent — a viewer scales it —
        so a floor buys nothing there and costs the guarantee that the canvas
        is exactly grid plus padding.

        A renderer that turns this into pixels wants :meth:`raster_style`
        instead, where that reasoning does not hold.
        """
        return SvgStyle(
            columns=cols,
            rows=rows,
            cell_w=float(self.char_width),
            cell_h=float(self.line_height),
            font_px=self.font_size,
            padding=self.padding,
            font_family=self.font_family,
            fg=self.fg,
            bg=self.bg,
            min_width=self.min_width,
            min_height=self.min_height,
        )

    def raster_style(self, cols: int, rows: int) -> SvgStyle:
        """:meth:`style`, floored at :data:`RASTER_MIN_WIDTH` x :data:`RASTER_MIN_HEIGHT`.

        For a renderer that rasterises the markup at its intrinsic size —
        ``rsvg-convert`` with no ``-w``/``-h``/``-z`` gives a PNG whose pixel
        dimensions are the SVG's ``width``/``height`` attributes, so the vector
        path's "a viewer will scale it" argument does not reach it. The floor is
        a hard lower bound rather than a default, which is how ``PngRenderer``
        has always applied the same two numbers.
        """
        floored = self.style(cols, rows)
        return replace(
            floored,
            min_width=max(floored.min_width, RASTER_MIN_WIDTH),
            min_height=max(floored.min_height, RASTER_MIN_HEIGHT),
        )


@dataclass(frozen=True)
class PngRenderConfig:
    # ``font_path`` of None keeps PIL's bundled proportional bitmap face.
    # ``font_size`` is only consulted when a font path is given.
    # ``scale`` multiplies the canvas, the padding and the line pitch, but not
    # the glyphs of the default bitmap face, which has one fixed size. Scaling
    # up therefore spreads the same text over a larger image unless
    # ``font_path`` is also set, which is what yields a higher-DPI screenshot.
    #
    # ``fg``/``bg`` are the shared palette's, not this renderer's own: the two
    # screenshot formats of one run should not disagree about what colour the
    # terminal is. ``padding``, ``font_size`` and ``scale`` stay independent —
    # they are raster quantities with no SVG counterpart, since this renderer
    # measures its cell from the PIL face rather than from a cell grid.
    scale: int = 1
    padding: int = 18
    font_size: int = 14
    font_path: str | None = None
    fg: str = DEFAULT_FG
    bg: str = DEFAULT_BG


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
    # ``dedup_step_screenshots`` writes one image per distinct screen instead of
    # one per step, and a steps-manifest.json that maps every step onto the
    # image representing it. Off by default: it changes the artifact layout, so
    # a consumer that globs the step directory has to read the manifest first.
    svg: SvgRenderConfig = SvgRenderConfig()
    png: PngRenderConfig = PngRenderConfig()
    video: VideoConfig = VideoConfig()
    dedup_step_screenshots: bool = False


@dataclass(frozen=True)
class VerifierConfig:
    steps: dict[str, str]
    assertions: dict[str, str]
    agent_runners: dict[str, str]
    execution_modes: dict[str, str]
    reporters: dict[str, str]
    screen_renderers: dict[str, str]
    video_backends: dict[str, str]
    artifact_publishers: dict[str, str]
    session_backend: str
    docker: DockerBackendConfig
    defaults: GlobalDefaults
    evidence: EvidenceConfig

    @classmethod
    def builtin(cls) -> VerifierConfig:
        """Return a config populated entirely from BUILTIN_DEFAULTS."""
        return _from_mapping(BUILTIN_DEFAULTS)


# -- built-in defaults ------------------------------------------------------

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
        "step_screen_contains": "termproof.builtin_assertions:StepScreenContains",
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
        "png_rsvg": "termproof.rsvg:RsvgPngRenderer",
    },
    "video_backends": {
        "agg_ffmpeg": "termproof.builtin_video:AggFfmpegBackend",
        "attributed_rsvg": "termproof.cast_video:RsvgFfmpegBackend",
    },
    "artifact_publishers": {
        "s3": "termproof.evidence_publish:S3ArtifactPublisher",
    },
    "session_backend": "termproof.builtin_session:PexpectBackend",
    "docker": {
        "image": "",
        "workdir": "/workspace",
        "volumes": [{"host": ".", "container": "/workspace"}],
        "env": {},
    },
    "defaults": {
        "idle_cap_seconds": 3.0,
    },
    # Evidence-rendering parameters, read off the dataclasses above rather than
    # restated here. This block is what documents every knob and its default
    # (python/README.md points at it), and a documented default that disagrees
    # with the one a renderer actually applies is worse than no documentation:
    # it is a promise the code does not keep. Deriving it means the two cannot
    # drift. See docs/evidence-quality.md for the researched alternatives.
    "evidence": {
        "svg": asdict(SvgRenderConfig()),
        "png": asdict(PngRenderConfig()),
        "video": asdict(VideoConfig()),
        "dedup_step_screenshots": EvidenceConfig().dedup_step_screenshots,
    },
}


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


# Smallest value each dimensional or rate knob can take. A zero or negative
# size collapses the rendered geometry (or reaches ``ImageFont.truetype`` as a
# negative size), and ``fps: 0`` reaches ffmpeg as ``-vf fps=0``, so these have
# to be refused where the offending key can still be named.
_EVIDENCE_MINIMUMS: dict[str, int] = {
    "evidence.svg.char_width": 1,
    "evidence.svg.line_height": 1,
    "evidence.svg.font_size": 1,
    "evidence.svg.padding": 0,
    "evidence.svg.min_width": 0,
    "evidence.svg.min_height": 0,
    "evidence.png.scale": 1,
    "evidence.png.font_size": 1,
    "evidence.png.padding": 0,
    "evidence.video.fps": 1,
    "evidence.video.fps_cap": 1,
    "evidence.video.font_size": 1,
}


def _check_field_range(label: str, name: str, value: Any) -> None:
    """Reject an out-of-range size or rate, naming the key as the type check does.

    Range only; the type is `_check_field_type`'s job. The message names the
    bound rather than a class of number: ``char_width`` and ``line_height`` take
    a float, so "a positive integer" would be wrong for them, and "positive"
    would be a rule ``char_width: 0.5`` satisfies while still being refused.
    """
    minimum = _EVIDENCE_MINIMUMS.get(f"{label}.{name}")
    if minimum is None or value is None or value >= minimum:
        return
    raise ValueError(f"{label}.{name} must be at least {minimum}, got {value!r}")


def _mapping(raw: Any, label: str) -> dict[str, Any]:
    """Return a config section as a mapping, refusing a scalar or a sequence.

    ``dict(raw)`` alone raises a ``TypeError`` that names neither the section
    nor the key, and callers of ``load_config`` expect a ``ValueError``.
    """
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"{label} must be a mapping, got {raw!r}")
    return dict(raw)


def _section(cls: type, raw: Any, label: str) -> Any:
    """Build a frozen config dataclass from a YAML mapping.

    Unknown keys are rejected rather than ignored: a misspelled rendering knob
    that silently does nothing is indistinguishable from one that had no effect.
    """
    values = _mapping(raw, label)
    hints = get_type_hints(cls)
    known = {field_.name for field_ in fields(cls)}
    unknown = sorted(set(values) - known)
    if unknown:
        raise ValueError(
            f"unknown {label} option(s) {unknown}; known options: {sorted(known)}"
        )
    for name, value in values.items():
        _check_field_type(label, name, hints[name], value)
        _check_field_range(label, name, value)
    return cls(**values)


def _evidence_from_mapping(raw: Any) -> EvidenceConfig:
    values = _mapping(raw, "evidence")
    dedup = values.pop("dedup_step_screenshots", False)
    _check_field_type("evidence", "dedup_step_screenshots", bool, dedup)
    evidence = EvidenceConfig(
        svg=_section(SvgRenderConfig, values.pop("svg", {}), "evidence.svg"),
        png=_section(PngRenderConfig, values.pop("png", {}), "evidence.png"),
        video=_section(VideoConfig, values.pop("video", {}), "evidence.video"),
        dedup_step_screenshots=dedup,
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
        artifact_publishers=dict(data.get("artifact_publishers", {})),
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
