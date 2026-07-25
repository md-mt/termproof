# Extension Points, Registries, and Protocols

`VerificationRunner` builds **7 `Registry` objects** plus a **separately resolved single session backend** from `VerifierConfig` (8 extension families total). Runtime wiring is mode-specific: step registry only in PTY mode, assertion registry only in scripted modes, `agent_runner_registry` has no runtime selector (programmatic `VerificationRunner(agent_runner=...)` bypasses it), execution mode resolver returns only 3 fixed keys, session backend is bypassed by both built-in Codex paths, video backend gated on `agg` binary. See mode-specific sections below — do not blanket claim every behavior is pluggable.

> Source: `runner.py:145-152` builds 7 registries (`step`, `assertion`, `reporter`, `screen_renderer`, `execution_mode`, `agent_runner`, `video_backend`); `runner.py:110-112,152` resolves session backend as a singleton via `_resolve_session_backend()`.

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

Extension surface — 7 registries plus session backend:

| Key | Kind | Built | CLI Controls |
| --- | --- | --- | --- |
| `steps` | Registry | StepAction | recipe `steps[].action` |
| `assertions` | Registry | Assertion evaluator | recipe `assertions[].type` |
| `agent_runners` | Registry (see limitation below) | AgentRunner | programmatic `VerificationRunner(agent_runner=...)` only |
| `execution_modes` | Registry (fixed 3 names) | ExecutionMode | `recipe.execution` + `command.pty` → one of 3 fixed keys |
| `reporters` | Registry | Reporter | `--reporter` |
| `screen_renderers` | Registry | ScreenRenderer | `--screen-renderer` |
| `video_backends` | Registry | VideoBackend | `--video-backend` |
| `session_backend` | Single (not a Registry) | SessionBackend | config only (`session_backend` string) |

Note `defaults` is modeled and unused by CLI/runner — see `configuration.md`. No decorators, no entry-points file scanning — just `module:ClassName` strings resolved via `importlib.import_module`.

## Runtime Wiring — Mode-Specific Limitations (Important)

Do not blanket claim every behavior is pluggable. The actual runtime wiring is mode-specific:

### Step registry

- **PTY mode** (`command.pty=true`, `runner.py:230-273`) — `step_registry.get(action_name)` is called per step inside `_run_pty()`.
- **Process mode** (`command.pty=false`, `runner.py:275-295`) — does **not** dispatch through the step registry. `_evaluate_output_steps()` hardcodes: `wait_for_text` (checks `text in screen or raw_output`), `sleep` (always pass), everything else fails with `"{action!r} requires command.pty=true"`.
- **Agent mode** (`execution=agent-driven`, `agent_driven.py:143-157`) — does **not** execute recipe `steps` at all. `AgentDrivenRunner.run()` creates a single synthetic `codex-operator` StepResult.

### Assertion registry

- **Scripted PTY and process modes** — used via `_evaluate_assertions()` / `_evaluate_assertion()` at `runner.py:297-325` and `builtin_modes.py:23-66`. Each `assertion.type` is resolved through `assertion_registry`.
- **Agent mode** — does **not** use the assertion registry. `_agent_assertions()` at `agent_driven.py:212-225` evaluates `recipe.checks` (or default check) against `AgentOutcome.assertions` returned by the agent.

### Agent runner registry

- `runner.py:94-99` builds `_build_agent_runner_registry()` from `config.agent_runners`, and `runner.py:150` stores it as `agent_runner_registry`.
- It is **never read** during execution. `VerificationRunner._run_agent_driven()` at `runner.py:204-213` uses either the explicitly injected `self.agent_runner` or `CodexCliAgentRunner.from_recipe(recipe)` — it does not consult `agent_runner_registry`.
- Custom `AgentRunner` via config alone does not execute; programmatic `VerificationRunner(agent_runner=...)` is the working path.

### Execution registry — Only 3 Fixed Names

`_resolve_execution_mode_name()` at `runner.py:128-134`:

```python
def _resolve_execution_mode_name(recipe):
    if recipe.execution == "agent-driven":
        return "agent_driven"
    if recipe.command.pty:
        return "scripted_pty"
    return "scripted_process"
```

And `runner.py:169-170` then does `execution_mode_registry.get(mode_name)`. Only those 3 keys exist in the builtin config. Supplying a new execution_modes key (e.g., `my_mode`) is parsed but never returned by the resolver — you must override one of the 3 fixed keys (e.g., replace `scripted_pty` mapping) or change `runner.py` to route new names.

### Video backend — Gated on `agg`

`evidence.py:55-60`:

```python
if render_video and shutil.which("agg"):
    mp4_path = run_dir / "session.mp4"
    if video_backend is not None:
        video_backend.render(cast_path, mp4_path, video_fps)
    else:
        render_mp4(cast_path, mp4_path, video_fps)
```

A custom video backend only runs when `--video` is set **and** `agg` binary is on PATH. Custom session backend cannot avoid that guard — the check lives in `render_artifacts()` before any backend call and is independent of session backend.

### Session backend — Bypassed by Both Built-in Codex Paths

`CodexCliAgentRunner._run_recorded()` at `agent_driven.py:51-70` directly constructs `TerminalSession(...)` (not `session_backend.create_session(...)`), so it bypasses the configured `config.session_backend`. `_run_subprocess()` at `agent_driven.py:88-131` (used when `record_terminal=False`) calls `subprocess.run()` directly and also bypasses it. Both built-in Codex paths bypass `config.session_backend`. Explicit `TimeoutExpired`/`FileNotFoundError` conversion exists only in the non-recorded subprocess path.

### Wait / Idle vs Exit Scope

- In `_run_pty()` at `runner.py:235-238`: `wait_for_exit` vs `wait_for_idle` branch applies **only** in PTY mode. If `expect_exit_code` is not None, wait_for_exit; else `wait_for_idle(0.5, min(3, timeout))`.
- In `_run_process()` at `runner.py:241-260`: always `wait_for_exit`; there is no idle branch.

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

Note: these dispatch through the registry only in PTY mode — see "Step registry" above.

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

Used only by scripted modes (PTY + process), not agent mode — see above.

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

Mode name is resolved by `_resolve_execution_mode_name(recipe)` returning only those 3 fixed keys — see execution registry limitation above.

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

`CodexCliAgentRunner` — fields: `command=["codex","exec"]`, `timeout_seconds=180`, `prompt_mode="stdin"` (`"stdin"` or `"arg"`), `cwd?`, `env={}`, `record_terminal=True`. `from_recipe()` reads `recipe.operator` dict. Recorded mode wraps via `TerminalSession`; non-recorded mode via `subprocess.run`. Timeout returns `timed_out=True` metadata; `FileNotFoundError` → exit 127.

`AgentDrivenRunner` is the adapter between execution mode and AgentRunner — builds prompt, runs agent, writes files, derives screen/assertions.

### ScreenRenderer (`builtin_renderers.py`)

```python
class ScreenRenderer(Protocol):
    name: str
    def render(self, text: str, output_path: Path, cols: int, rows: int) -> None: ...
```

`SvgRenderer` — minimal SVG: background `#101418`, mono text `#e6edf3`, `line_height=20`, `char_width=9`, `padding=18`, `width=max(320, cols*9+36)`, `height=max(160, rows*20+36)`.

> Contract: `evidence.py:34-43,76-83` always supplies `.svg` paths (`final.svg`, `steps/{index:02d}-{safe}.svg`). A renderer writing PNG bytes to an `.svg` path will produce invalid output but artifact metadata still reports `.svg`. Document the fixed `.svg` contract or change source — PNG-style renderer examples are invalid via current pipeline.

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

`AggFfmpegBackend` — delegates to `evidence.render_mp4()`. Only invoked when `render_video and shutil.which("agg")` — see gate above.

### SessionBackend (`builtin_session.py`)

```python
class SessionBackend(Protocol):
    def create_session(self, argv: list[str], cast_path: Path,
                       cwd: str | None, env: dict[str, str],
                       cols: int, rows: int) -> TerminalSession: ...
```

Under the hood, the object returned by `create_session()` must support context manager protocol (`__enter__`/`__exit__`) because `runner.py:222-229,247-254` uses `with ...create_session(...) as session:`. The session backend itself (the object with `create_session` method) need not be a context manager — only the session object it returns must be. Otherwise `_run_pty` / `_run_process` raise. Recorded agent mode at `agent_driven.py:56-85` directly constructs `TerminalSession` (bypassing configured backend), while non-recorded mode at `agent_driven.py:87-131` bypasses via subprocess.

`PexpectAsciinemaBackend` — `return TerminalSession(argv, cast_path, cwd, env, cols, rows)`.

## How to Extend (Honest)

In `.tui-verifier/config.yaml` (project) or `~/.config/tui-verifier/config.yaml` (user):

```yaml
steps:
  my_custom_step: "my_package.steps:MyStep"
assertions:
  my_check: "my_package.assertions:MyCheck"
screen_renderers:
  svg_styled: "my_package.renderers:StyledSvgRenderer"
session_backend: "my_package.session:MySessionBackend"
```

The value must be `"dotted.module.path:ClassName"`. The runner imports it at startup and will raise `ValueError` if `":"` is missing, or `AttributeError`/`ModuleNotFoundError` if import fails. Registry `get()` raises `KeyError` with sorted available names listing when name unknown. Runner wraps unknown step/assertion names as `ValueError("unknown step action")` / `ValueError("unknown assertion type")`.

## Recipe-Level Extensibility

- `renderers` field in recipe (`{name: [extra_argv...]}`) — `renderer.py:selected_renderers()` expands `--renderer all`/`both` to all; named renderer to single; `renderers.default` may be empty list.
- `CommandSpec` — `argv`, `cwd`, `env` (dict merged over os.environ with TERM default), `pty` bool.
- `operator` dict in recipe — arbitrary mapping read by `CodexCliAgentRunner.from_recipe()` (`command`, `timeout_seconds`, `prompt_mode`, `cwd`, `env`, `record_terminal`).
- `checks` list — human-readable check names for agent-driven mode; used by `build_agent_prompt()` and `_agent_assertions()`.
- `expect_exit_code` — if not None, PTY mode calls `wait_for_exit()`; else `wait_for_idle(0.5, min(3, timeout))`. Process mode always `wait_for_exit` regardless of `expect_exit_code`.
