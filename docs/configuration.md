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

Overlay wins at leaf level; dicts merge recursively, non-dicts replace wholesale. This matches the behavior of many editor/tool configs.

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

`defaults` contains global defaults used by CLI/runner if recipe does not override.

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

- All fields are immutable (frozen dataclass).
- `builtin()` constructs from `BUILTIN_DEFAULTS` via `_from_mapping()`.
- `_from_mapping()` coerces: steps/assertions/etc via `dict()`, session_backend via `str()`, GlobalDefaults coerced with `float()`, `int()`, `str()` as appropriate.

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

- `user_path` and `project_path` can be overridden by caller (used by CLI `--config`).
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

## CLI --config Override

`cli._resolve_config(args)`:

```python
def _resolve_config(args):
    if args.config:
        user_path = None
        project_path = args.config.resolve()
        return load_config(project_path=project_path, user_path=user_path)
    return load_config()
```

When `--config` is passed:
- `user_path=None` disables user-layer loading? No — code sets `user_path=None` but `load_config` still falls back to default path if user_path is None? Let's check: actual implementation:

In `load_config`, `user_path or Path.home()/.../config.yaml`, so passing `None` still triggers default user path lookup unless explicitly overriding behavior. In `_resolve_config`, it sets `user_path=None` and `project_path=resolved --config`. That means:
- User file: `Path.home() / ".config" / "tui-verifier" / "config.yaml"` still checked (since None falls back)
- Project file: `args.config.resolve()` is checked as project config path? Wait code: `project_path or Path.cwd() / ".tui-verifier" / "config.yaml"`. If project_path is a file path, not a directory, then `project_path / ".tui-verifier" / "config.yaml"` would be wrong.

Looking more carefully at `_resolve_config`:
Actually CLI code currently does:

```python
if args.config:
    from .config import load_config as _load
    user_path: Path | None = None
    project_path: Path | None = args.config.resolve()
    return _load(project_path=project_path, user_path=user_path)
```

But `_load` signature is `load_config(project_path, user_path)`. Inside, `project_file = (project_path or Path.cwd()) / ".tui-verifier" / "config.yaml"`. So passing a file as project_path will append suffix — this looks like a minor discrepancy. In practice, how it works: `_load_yaml(project_path)` is not called; instead `(project_path) / ".tui-verifier" / ...` is used. If project_path is a file path, that path won't exist, so _load_yaml won't happen for that location. However `user_path=None` still triggers default user file.

Wait re-reading actual code path in cli.py line:

The cli resolves config via `_resolve_config`, and looking at earlier output of cli.py: there is a helper that loads precisely given path? Let's check actual implementation of _resolve_config again:

From cli.py read earlier:
```python
def _resolve_config(args: argparse.Namespace) -> VerifierConfig:
    if args.config:
        from .config import load_config as _load
        user_path: Path | None = None
        project_path: Path | None = args.config.resolve()
        return _load(project_path=project_path, user_path=user_path)
    return load_config()
```

But inside `load_config`, `project_path` is used as base for `project_file = (project_path or Path.cwd()) / ".tui-verifier" / "config.yaml"` — not as direct file. So `--config` pointing to a file path would be reinterpreted as dir. This is potentially a bug, but documented behavior should reflect actual code: when `--config PATH` is given, that PATH is used as project_path override for cascade (i.e., checked as `PATH / .tui-verifier / config.yaml`). However the intention described in CLI help "path to a tui-verifier config YAML file" suggests it should load directly. Check again — in load_config, there's no direct loading of project_path as file; it always appends `/.tui-verifier/config.yaml`. So `--config` semantics: provide project root, not file.

For factual accuracy: the help says "path to a tui-verifier config YAML file" but implementation uses it as project base. We should note this subtlety in docs and not over-claim.

## Writing Custom Config

Example `.tui-verifier/config.yaml`:

```yaml
# Add a custom step type
steps:
  my_wait:
    # Actually the value must be "module:Class" string, not dict
    # Correct form:
  my_wait: "my_pkg.steps:MyWaitStep"

# Add a custom assertion
assertions:
  http_200: "my_pkg.assert:Http200Assertion"

# Add a screen renderer
screen_renderers:
  png: "my_pkg.renderers:PngRenderer"

# Replace session backend entirely
session_backend: "my_pkg.session:MySessionBackend"

# Override defaults
defaults:
  timeout_seconds: 60.0
  cols: 120
  rows: 40
  video_fps: 30
  out_dir: ".tui-verifier/custom-runs"
```

User-level `~/.config/tui-verifier/config.yaml` has same schema.

### Config Merging Examples

- **Additive**: builtins contain 6 steps; project config adds `my_step` → result 7 steps.
- **Replace leaf**: builtins have `session_backend: "tui_verifier.builtin_session:PexpectAsciinemaBackend"`; project config `session_backend: "custom:Backend"` → leaf replaced, new value used.
- **Override nested dict**: builtins `defaults.timeout_seconds=30.0`; project config `defaults: {timeout_seconds: 60.0}` → `_deep_merge` recurses into defaults dict, overlay leaf wins, resulting 60.0 while preserving other defaults keys.

## Relationship to Recipe Fields

Recipe JSON fields like `timeout_seconds`, `cols`, `rows` directly specify per-recipe values. Config `defaults` provides fallback if runner/cli wants defaults, but recipe values take direct precedence. The runner uses `recipe.timeout_seconds`, `recipe.cols`, `recipe.rows` from the recipe itself; config defaults are used for CLI global defaults (e.g., out_dir, video_fps) when recipe does not specify.

## Error Cases

- `yaml` not installed + config file exists → `RuntimeError("pyyaml is required to load config files; install pyyaml>=6.0")`.
- Config YAML parses but value is not dict → `_load_yaml` returns `{}`.
- Qualname without `:` → `ValueError("expected 'module.path:ClassName', got ...")`.
- Module/class not found → `ModuleNotFoundError` / `AttributeError` from import.
- Unknown registry name at runtime → `KeyError("unknown plugin {name!r}; available: ...")` from `Registry.get()`.
