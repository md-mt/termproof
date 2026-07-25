# Cascading Configuration Model

## Overview

`config.py` implements a 3-layer cascade:

```
BUILTIN_DEFAULTS (hardcoded dict)
  ↓ deep-merged with
~/.config/tui-verifier/config.yaml  (user layer, optional)
  ↓ deep-merged with
.tui-verifier/config.yaml           (project layer, optional)
  ↓ resolved to
VerifierConfig (frozen dataclass with typed fields)
```

Overlay wins at leaf level; dicts merge recursively, non-dicts replace wholesale.

## BUILTIN_DEFAULTS — Canonical Source

In `config.py`:

```python
BUILTIN_DEFAULTS: dict[str, Any] = {
    "steps": { ... 6 entries ... },
    "assertions": { ... 7 entries ... },
    "agent_runners": { "codex": "tui_verifier.agent_driven:CodexCliAgentRunner" },
    "execution_modes": { ... 3 entries ... },
    "reporters": { "markdown": "tui_verifier.builtin_reporters:MarkdownReporter" },
    "screen_renderers": { "svg": "tui_verifier.builtin_renderers:SvgRenderer" },
    "video_backends": { "agg_ffmpeg": "tui_verifier.builtin_video:AggFfmpegBackend" },
    "session_backend": "tui_verifier.builtin_session:PexpectAsciinemaBackend",
    "defaults": {
        "timeout_seconds": 30.0,
        "cols": 100,
        "rows": 30,
        "video_fps": 60,
        "out_dir": ".tui-verifier/runs",
    },
}
```

Every registry key maps to a string of form `"dotted.module:ClassName"`. These are resolved via `runner._import_class(qualname)` which splits on first `":"` and imports the module.

`session_backend` is a single string (not a dict) — only one backend at a time.

### `defaults` Is Currently Modeled but Unused

`VerifierConfig.defaults` is parsed and stored, but **current CLI, runner, and recipe defaults remain hardcoded and do not read it**:

- CLI hardcodes `--out` default `.tui-verifier/runs` and `--video-fps` default `60` at `cli.py:21-24`.
- `VerificationRunner.run()` hardcodes its `out_dir` default `Path(".tui-verifier/runs")` and `video_fps` default `60` at `runner.py:154-163`.
- Recipe fields `timeout_seconds`, `cols`, `rows` hardcode their own defaults at `models.py:31-34`.

The `defaults` dict is modeled and unused — parsed and stored in `VerifierConfig.defaults` but not read by CLI, runner, or recipe defaults. Changing it in a config YAML today does not change CLI/runner fallbacks.

## VerifierConfig Dataclass

```python
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
        return _from_mapping(BUILTIN_DEFAULTS)
```

- Frozen dataclass prevents attribute rebinding (e.g., `config.steps = ...` raises), but the inner dict values remain mutable — `config.steps["extra"] = ...` would mutate the dict. Treat them as read-only by convention.
- `builtin()` constructs from `BUILTIN_DEFAULTS` via `_from_mapping()`.
- `_from_mapping()` coerces: steps/assertions/etc via `dict()`, `session_backend` via `str()`, `GlobalDefaults` coerced with `float()`, `int()`, `str()` as appropriate.

## Cascade Implementation

`load_config(project_path?, user_path?) -> VerifierConfig`:

```python
def load_config(project_path=None, user_path=None) -> VerifierConfig:
    merged = _deep_merge({}, BUILTIN_DEFAULTS)  # deep copy builtin

    user_file = user_path or Path.home() / ".config" / "tui-verifier" / "config.yaml"
    if user_file.exists():
        merged = _deep_merge(merged, _load_yaml(user_file))

    project_file = (project_path or Path.cwd()) / ".tui-verifier" / "config.yaml"
    if project_file.exists():
        merged = _deep_merge(merged, _load_yaml(project_file))

    return _from_mapping(merged)
```

- `user_path` and `project_path` can be overridden by caller.
- Each layer file existence is checked via `Path.exists()` — missing file silently skipped.
- `_load_yaml(path)` requires `pyyaml`; raises `RuntimeError("pyyaml is required...")` if yaml is None (ImportError fallback).
- `_deep_merge(base, overlay)`:

```python
def _deep_merge(base, overlay):
    result = dict(base)
    for key, value in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
```

- Recursive dict merge, leaf values replaced.
- Example: if user config provides `steps: {my_step: ...}`, the existing 6 builtins are preserved and `my_step` is added. If user config provides `session_backend: "custom:Class"`, it replaces the builtin entirely (non-dict leaf).

## CLI `--config` — Known Bug

CLI help advertises `cli.py:29-30`:

```
--config PATH  path to a tui-verifier config YAML file
```

Current `_resolve_config` at `cli.py:116-123` does:

```python
if args.config:
    project_path = args.config.resolve()
    return load_config(project_path=project_path, user_path=None)
```

And `load_config` then computes `project_file = (project_path) / ".tui-verifier" / "config.yaml"` and checks its existence. It does **not** load the file supplied directly. Additionally, `user_path=None` falls back to the default `~/.config/tui-verifier/config.yaml` at `config.py:99-105`, so the default user config still loads even when `--config` is given.

Net effect:

- Passing a YAML file path to `--config` is a bug: the file is not loaded; the code looks for `<given-path>/.tui-verifier/config.yaml` instead.
- Passing a project directory works despite the help text (because `dir/.tui-verifier/config.yaml` is the expected layout).
- The default user-layer file at `~/.config/tui-verifier/config.yaml` still participates even with `--config`.

## Writing Custom Config

Example `.tui-verifier/config.yaml`:

```yaml
# Add a custom step type (qualname, not nested dict)
steps:
  my_wait_step: "my_pkg.steps:MyWaitStep"

# Add a custom assertion
assertions:
  http_200: "my_pkg.assert:Http200Assertion"

# Add a screen renderer (but note fixed .svg contract in evidence.py —
# custom renderers receive .svg output paths; see evidence-pipeline.md)
screen_renderers:
  svg_styled: "my_pkg.renderers:StyledSvgRenderer"

# Replace session backend entirely
session_backend: "my_pkg.session:MySessionBackend"
```

User-level `~/.config/tui-verifier/config.yaml` has same schema. Note `defaults` and registry overrides via YAML are modeled but runtime defaults for CLI/runner currently remain hardcoded — see "defaults is currently unused" above.

### Config Merging Examples

- **Additive**: builtins contain 6 steps; project config adds `my_step` → result 7 steps.
- **Replace leaf**: builtins have `session_backend: "tui_verifier.builtin_session:PexpectAsciinemaBackend"`; project config `session_backend: "custom:Backend"` → leaf replaced, new value used.
- **Override nested dict**: builtins `defaults.timeout_seconds=30.0`; project config `defaults: {timeout_seconds: 60.0}` → `_deep_merge` recurses into defaults dict, overlay leaf wins, resulting 60.0 while preserving other defaults keys. Note this override is stored but not consumed by current runner/CLI defaults.

## Relationship to Recipe Fields

Recipe JSON fields like `timeout_seconds`, `cols`, `rows` directly specify per-recipe values with their own hardcoded defaults at `models.py:31-34,82-108`, independent of CLI/runner `out_dir`/`video_fps` defaults. CLI/runner `out_dir`/`video_fps` defaults (`.tui-verifier/runs`, `60`) and recipe-level `timeout_seconds`/`cols`/`rows` geometry defaults are independent hardcoded values — there is no recipe-vs-CLI precedence; `config.defaults` does not currently participate as an intermediate fallback.

## Evidence Pipeline Fixed `.svg` Contract

`evidence.py:34-43,76-83` always supplies `.svg` paths to the screen renderer:

```python
final_svg = run_dir / "final.svg"
screen_renderer.render(final_text, final_svg, cols, rows)  # or render_svg as fallback
```

And `steps/` rendering uses `{index:02d}-{safe}.svg`. Artifact metadata also records the `.svg` path. A renderer that calls `PIL.Image.save(output_path)` will receive an `.svg` path, not `.png`, so the advertised generic PNG flow is invalid — custom renderers must write valid content for the given `.svg` path or the pipeline must be changed. See `evidence-pipeline.md`.

## Error Cases

- `yaml` not installed + config file exists → `RuntimeError("pyyaml is required to load config files; install pyyaml>=6.0")`.
- Config YAML parses but value is not dict → `_load_yaml` returns `{}`.
- Qualname without `:` → `ValueError("expected 'module.path:ClassName', got ...")` from `_import_class`.
- Module/class not found → `ModuleNotFoundError` / `AttributeError` from import.
- Unknown registry name at runtime → `Registry.get()` raises `KeyError("unknown plugin {name!r}; available: ...")` from `registry.py:24-31`. Runner wraps unknown step/assertion names as `ValueError("unknown step action: ...")` / `ValueError("unknown assertion type: ...")` at `runner.py:268-273,320-325`.
