# Extension Points, Registries, and Protocols

Every behavior in tui-verifier is a pluggable registry entry. Registries are built once per `VerificationRunner` instance from `VerifierConfig`. No decorators, no entry-points file scanning — just `module:ClassName` strings resolved via `importlib.import_module`.

## Registry Mechanism

`registry.Registry[T]` (generic):

```python
class Registry(Generic[T]):
    def __init__(self): self._factories: dict[str, Callable[[], T]] = {}
    def register(self, name: str, factory: Callable[[], T]) -> None: ...
    def get(self, name: str) -> T:  # raises KeyError with available list
    def names(self) -> list[str]:   # sorted
```

Builder in `runner.py` for each registry:

```python
def _build_step_registry(config: VerifierConfig) -> Registry[Any]:
    registry: Registry[Any] = Registry()
    for name, qualname in config.steps.items():
        cls = _import_class(qualname)
        registry.register(name, lambda c=cls: c())
    return registry

def _import_class(qualname: str) -> type:
    if ":" not in qualname:
        raise ValueError(f"expected 'module.path:ClassName', got {qualname!r}")
    module_name, class_name = qualname.split(":", 1)
    module = importlib.import_module(module_name)
    return getattr(module, class_name)
```

All factories are zero-arg constructors. If you need parameters, read them from the `step`/`assertion`/`recipe` dict at call time, not construction time.

## Config Dictionary → Registry

`config.BUILTIN_DEFAULTS` is the canonical source:

```python
BUILTIN_DEFAULTS = {
  "steps": {
    "wait_for_text": "tui_verifier.builtin_steps:WaitForText",
    "wait_for_idle": "tui_verifier.builtin_steps:WaitForIdle",
    "send_text":     "tui_verifier.builtin_steps:SendText",
    "send_line":     "tui_verifier.builtin_steps:SendLine",
    "press":         "tui_verifier.builtin_steps:Press",
    "sleep":         "tui_verifier.builtin_steps:Sleep",
  },
  "assertions": {
    "output_contains":     "tui_verifier.builtin_assertions:OutputContains",
    "output_not_contains": "tui_verifier.builtin_assertions:OutputNotContains",
    "screen_contains":     "tui_verifier.builtin_assertions:ScreenContains",
    "screen_not_contains": "tui_verifier.builtin_assertions:ScreenNotContains",
    "exit_code":           "tui_verifier.builtin_assertions:ExitCode",
    "file_exists":         "tui_verifier.builtin_assertions:FileExists",
    "file_contains":       "tui_verifier.builtin_assertions:FileContains",
  },
  "agent_runners": {
    "codex": "tui_verifier.agent_driven:CodexCliAgentRunner",
  },
  "execution_modes": {
    "scripted_pty":     "tui_verifier.builtin_modes:ScriptedPtyMode",
    "scripted_process": "tui_verifier.builtin_modes:ScriptedProcessMode",
    "agent_driven":     "tui_verifier.builtin_modes:AgentDrivenMode",
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
```

These 8 keys define the extension surface:

| Key | Registry Built | CLI Controls |
| --- | --- | --- |
| `steps` | StepAction | recipe `steps[].action` |
| `assertions` | Assertion evaluator | recipe `assertions[].type` |
| `agent_runners` | AgentRunner | `recipe.operator` / `--operator-command` |
| `execution_modes` | ExecutionMode | `recipe.execution` + `command.pty` → mode name |
| `reporters` | Reporter | `--reporter` |
| `screen_renderers` | ScreenRenderer | `--screen-renderer` |
| `video_backends` | VideoBackend | `--video-backend` |
| `session_backend` | SessionBackend (single, not map) | config only |

## Protocols (Exact Signatures)

All protocols are `typing.Protocol` and live next to their builtins.

### StepAction (`builtin_steps.py`)

```python
class StepAction(Protocol):
    name: str
    def execute(self, session: TerminalSession, step: dict[str, Any], index: int) -> StepResult: ...
```

Built-ins:
- `WaitForText` — `step["text"]`, optional `timeout_seconds` (default 10), `name` for display. Delegates to `session.wait_for_text()`.
- `WaitForIdle` — `stable_seconds=0.5`, `timeout_seconds=10`, delegates to `session.wait_for_idle()`.
- `SendText` — `step["text"]` → `session.send_text()`.
- `SendLine` — `step.get("text","")` → `session.send_line()` (adds `\r`).
- `Press` — `step["key"]` → `session.press()`; supports `ctrl-` prefix and KEYS dict (`enter→\r`, `escape→\x1b`, `tab→\t`, `backspace→\x7f`, `up→\x1b[A`, `down→\x1b[B`, `right→\x1b[C`, `left→\x1b[D`).
- `Sleep` — `step.get("seconds",1)` → `time.sleep()` + `read_available(0)`.

### AssertionType (`builtin_assertions.py`)

```python
class AssertionType(Protocol):
    name: str
    def evaluate(self, recipe: Recipe, assertion: dict[str, Any],
                 screen: str, raw_output: str, exit_code: int | None) -> AssertionResult: ...
```

Built-ins:
- `output_contains` / `output_not_contains` — substring in `raw_output`.
- `screen_contains` / `screen_not_contains` — substring in `screen`.
- `exit_code` — `assertion["value"] == exit_code`.
- `file_exists` — `Path(...).exists()`, path resolved via `_recipe_path(recipe, path)` (absolute passthrough, relative against `command.cwd or "."`).
- `file_contains` — reads file, checks `assertion["value"]` in contents; path key is `assertion["path"]`.

### ExecutionMode (`builtin_modes.py`)

```python
class ExecutionMode(Protocol):
    name: str
    def execute(self, runner: Any, recipe: Recipe, run_dir: Path
               ) -> tuple[list[StepResult], list[AssertionResult], str, int | None, str]: ...
```

- `ScriptedPtyMode` (`scripted_pty`) — calls `runner._run_pty()` + `_evaluate_assertions()`.
- `ScriptedProcessMode` (`scripted_process`) — calls `runner._run_process()` + `_evaluate_assertions()`.
- `AgentDrivenMode` (`agent_driven`) — calls `runner._run_agent_driven()`.

Mode name is resolved by `_resolve_execution_mode_name(recipe)`:
`agent-driven` → `agent_driven`; `command.pty=True` → `scripted_pty`; else → `scripted_process`.

### AgentRunner (`agent_driven.py`)

```python
class AgentRunner(Protocol):
    def run(self, recipe: Recipe, prompt: str, run_dir: Path) -> AgentOutcome: ...

@dataclass(frozen=True)
class AgentOutcome:
    assertions: dict[str, bool]
    transcript: str
    raw_output: str
    exit_code: int | None
    metadata: dict[str, Any] = field(default_factory=dict)
```

`CodexCliAgentRunner` — fields: `command=["codex","exec"]`, `timeout_seconds=180`, `prompt_mode="stdin"` (`"stdin"` or `"arg"`), `cwd?`, `env={}`, `record_terminal=True`. `from_recipe()` reads `recipe.operator` dict. Recorded mode wraps via `TerminalSession`; non-recorded mode via `subprocess.run`. Handles timeout and FileNotFoundError.

`AgentDrivenRunner` is the adapter between execution mode and AgentRunner — builds prompt, runs agent, writes files, derives screen/assertions.

### ScreenRenderer (`builtin_renderers.py`)

```python
class ScreenRenderer(Protocol):
    name: str
    def render(self, text: str, output_path: Path, cols: int, rows: int) -> None: ...
```

`SvgRenderer` — minimal SVG: background `#101418`, mono text `#e6edf3`, `line_height=20`, `char_width=9`, `padding=18`, `width=max(320, cols*9+36)`, `height=max(160, rows*20+36)`.

### Reporter (`builtin_reporters.py`)

```python
class Reporter(Protocol):
    name: str
    def generate(self, results: list[RunResult],
                 build_info: BuildInfo | None = None,
                 before_after: BeforeAfterResult | None = None) -> str: ...
```

`MarkdownReporter` — generates table + per-result `<details>`.

### VideoBackend (`builtin_video.py`)

```python
class VideoBackend(Protocol):
    name: str
    def render(self, cast_path: Path, output_path: Path, fps: int) -> None: ...
```

`AggFfmpegBackend` — delegates to `evidence.render_mp4()`.

### SessionBackend (`builtin_session.py`)

```python
class SessionBackend(Protocol):
    def create_session(self, argv: list[str], cast_path: Path,
                       cwd: str | None, env: dict[str, str],
                       cols: int, rows: int) -> TerminalSession: ...
```

`PexpectAsciinemaBackend` — `return TerminalSession(argv, cast_path, cwd, env, cols, rows)`.

## How to Extend

In `.tui-verifier/config.yaml` (project) or `~/.config/tui-verifier/config.yaml` (user):

```yaml
steps:
  my_custom_step: "my_package.steps:MyStep"
assertions:
  my_check: "my_package.assertions:MyCheck"
screen_renderers:
  png: "my_package.renderers:PngRenderer"
session_backend: "my_package.session:MySessionBackend"
```

The value must be `"dotted.module.path:ClassName"`. The runner imports it at startup and will raise `ValueError` if `":"` is missing, or `AttributeError`/`ModuleNotFoundError` if import fails. Registry `get()` raises `KeyError` with sorted available names listing when name unknown.

## Recipe-Level Extensibility

- `renderers` field in recipe (`{name: [extra_argv...]}`) — `renderer.py:selected_renderers()` expands `--renderer all`/`both` to all; named renderer to single; `renderers.default` may be empty list.
- `CommandSpec` — `argv`, `cwd`, `env` (dict merged over os.environ with TERM default), `pty` bool.
- `operator` dict in recipe — arbitrary mapping read by `CodexCliAgentRunner.from_recipe()` (`command`, `timeout_seconds`, `prompt_mode`, `cwd`, `env`, `record_terminal`).
- `checks` list — human-readable check names for agent-driven mode; used by `build_agent_prompt()` and `_agent_assertions()`.
- `expect_exit_code` — if not None, runner calls `wait_for_exit()`; else `wait_for_idle(0.5, min(3, timeout))`. Both PTY and process modes honor it.
