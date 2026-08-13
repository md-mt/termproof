# TermProof Framework Architecture Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Refactor termproof from a monolithic CLI tool into a fully configurable framework where each component (step actions, assertion types, agent runners, execution modes, renderers, reporters, session backends) is pluggable via a cascading configuration system.

**Architecture:** Introduce a `VerifierConfig` object loaded from YAML with cascading priority (recipe → project → user → built-in defaults), backed by a plugin registry pattern. Each extension point gets a `Registry[T]` that resolves named plugin references to concrete implementations. Existing recipe JSON files and CLI remain fully backward compatible — all current hardcoded behavior becomes the default plugin set.

**Tech Stack:** Python 3.11+, pyyaml (new dep), setuptools entry points (optional, for pip-installable plugins), existing deps (pexpect, pyte, asciinema)

---

## Architecture Overview

```
                    ┌──────────────────────────┐
                    │    VerifierConfig (YAML)  │
                    │  cascade: recipe → project│
                    │  → user → built-in        │
                    └──────────┬───────────────┘
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                    │
  ┌───────▼──────┐   ┌────────▼────────┐   ┌───────▼──────┐
  │ StepAction   │   │ AssertionType   │   │ AgentRunner  │
  │ Registry     │   │ Registry        │   │ Registry     │
  └──────────────┘   └─────────────────┘   └──────────────┘
          │                    │                    │
  ┌───────▼──────┐   ┌────────▼────────┐   ┌───────▼──────┐
  │ ExecutionMode│   │ Reporter        │   │ ScreenRenderer│
  │ Registry     │   │ Registry        │   │ Registry      │
  └──────────────┘   └─────────────────┘   └──────────────┘
```

Each registry holds named implementations. Recipes reference them by name. The config file maps names to implementations.

## Extension Points (8 total)

| # | Extension Point | Current Hardcoded | Make Pluggable Via |
|---|---|---|---|
| 1 | Step actions | `_run_step()` if/elif chain | `StepAction` protocol + registry |
| 2 | Assertion types | `_evaluate_assertion()` if/elif | `AssertionType` protocol + registry |
| 3 | Agent runners | `CodexCliAgentRunner` only | `AgentRunner` protocol + registry |
| 4 | Execution modes | `scripted` / `agent-driven` | `ExecutionMode` protocol + registry |
| 5 | Reporters | Markdown only | `Reporter` protocol + registry |
| 6 | Screen renderers | SVG only | `ScreenRenderer` protocol + registry |
| 7 | Video backends | agg+ffmpeg | `VideoBackend` protocol + registry |
| 8 | Session/cast backends | pexpect+asciinema | `SessionBackend` protocol |

---

## Phase 1: Foundation — Config System + Step/Action Registry

**Rationale:** Highest ROI. Users can extend verification behavior immediately without touching framework internals. The config system is the backbone everything else plugs into.

### Task 1.1: Add `pyyaml` dependency

**Files:**
- Modify: `pyproject.toml`

Add `pyyaml>=6.0` to dependencies.

### Task 1.2: Create `VerifierConfig` model and loader

**Files:**
- Create: `termproof/config.py`

`VerifierConfig` is a frozen dataclass that holds all plugin registrations and global settings. Cascading load:
1. Built-in defaults (current hardcoded behavior — `BUILTIN_DEFAULTS` constant)
2. `~/.config/termproof/config.yaml` (user-global)
3. `./.termproof/config.yaml` (project-local)
4. Recipe-level overrides (fields in recipe JSON, future)

```python
@dataclass(frozen=True)
class VerifierConfig:
    steps: dict[str, str]        # action_name → fully.qualified.Class
    assertions: dict[str, str]   # assertion_type_name → fully.qualified.Class
    agent_runners: dict[str, str]
    execution_modes: dict[str, str]
    reporters: dict[str, str]
    screen_renderers: dict[str, str]
    video_backends: dict[str, str]
    session_backend: str
    defaults: GlobalDefaults

@dataclass(frozen=True)
class GlobalDefaults:
    timeout_seconds: float = 30.0
    cols: int = 100
    rows: int = 30
    video_fps: int = 60
    out_dir: str = ".termproof/runs"

def load_config(
    project_path: Path | None = None,
    user_path: Path | None = None,
) -> VerifierConfig:
    ...
```

Config YAML format:
```yaml
# .termproof/config.yaml
steps:
  wait_for_text: termproof.builtin_steps:WaitForText
  wait_for_idle: termproof.builtin_steps:WaitForIdle
  send_text: termproof.builtin_steps:SendText
  send_line: termproof.builtin_steps:SendLine
  press: termproof.builtin_steps:Press
  sleep: termproof.builtin_steps:Sleep
  my_custom_action: my_package.steps:CustomAction

assertions:
  output_contains: termproof.builtin_assertions:OutputContains
  output_not_contains: termproof.builtin_assertions:OutputNotContains
  screen_contains: termproof.builtin_assertions:ScreenContains
  screen_not_contains: termproof.builtin_assertions:ScreenNotContains
  exit_code: termproof.builtin_assertions:ExitCode
  file_exists: termproof.builtin_assertions:FileExists
  file_contains: termproof.builtin_assertions:FileContains

defaults:
  timeout_seconds: 30
  cols: 100
  rows: 30
```

### Task 1.3: Create generic `Registry[T]` class

**Files:**
- Create: `termproof/registry.py` (extend existing)

Add a generic registry:
```python
class Registry(Generic[T]):
    def register(self, name: str, factory: Callable[[], T]) -> None: ...
    def get(self, name: str) -> T: ...
    def names(self) -> list[str]: ...
```

### Task 1.4: Create `StepAction` protocol and built-in implementations

**Files:**
- Create: `termproof/builtin_steps.py`
- Modify: `termproof/runner.py` (extract step logic)

Extract each step action into its own class implementing a protocol:

```python
class StepAction(Protocol):
    name: str  # class-level identifier

    def execute(
        self,
        session: TerminalSession,
        step: dict[str, Any],
        index: int,
    ) -> StepResult:
        ...
```

Six built-in implementations: `WaitForText`, `WaitForIdle`, `SendText`, `SendLine`, `Press`, `Sleep`.

The `VerificationRunner._run_step()` method becomes:
```python
def _run_step(self, session, index, step):
    action_name = step["action"]
    action = self.config.step_registry.get(action_name)
    return action.execute(session, step, index)
```

### Task 1.5: Create `AssertionType` protocol and built-in implementations

**Files:**
- Create: `termproof/builtin_assertions.py`
- Modify: `termproof/runner.py` (extract assertion logic)

Same pattern. Seven built-in implementations.

### Task 1.6: Wire config into CLI and runner

**Files:**
- Modify: `termproof/cli.py`
- Modify: `termproof/runner.py`

- `VerificationRunner` accepts optional `VerifierConfig` (defaults to `load_config()`)
- CLI loads config early and passes it down
- CLI gets new `--config` flag to point to an explicit config file

### Task 1.7: Update tests for config integration

**Files:**
- Modify: `tests/test_runner.py`
- Modify: `tests/test_stack_design.py`

Ensure existing tests pass with the new config-wired runner. Add tests for config loading, cascading, and custom step/assertion registration.

---

## Phase 2: Reporter + Screen Renderer Plugins

### Task 2.1: Create `Reporter` protocol and registry

**Files:**
- Create: `termproof/builtin_reporters.py`
- Modify: `termproof/report.py` (extract to class)

```python
class Reporter(Protocol):
    name: str

    def generate(
        self,
        results: list[RunResult],
        build_info: BuildInfo | None = None,
        before_after: BeforeAfterResult | None = None,
    ) -> str:
        ...
```

Built-in: `MarkdownReporter`. Future: `JunitReporter`, `JsonReporter`, `GitHubSummaryReporter`.

### Task 2.2: Create `ScreenRenderer` protocol and registry

**Files:**
- Create: `termproof/builtin_renderers.py`
- Modify: `termproof/screen.py` and `termproof/evidence.py`

```python
class ScreenRenderer(Protocol):
    name: str

    def render(
        self,
        text: str,
        output_path: Path,
        cols: int,
        rows: int,
    ) -> None:
        ...
```

Built-in: `SvgRenderer` (current behavior). Future: `PngRenderer` (via Cairo/Pillow), `HtmlRenderer`, `AnsiRenderer`.

### Task 2.3: Wire reporters and renderers into CLI and runner

- `--reporter` CLI flag (default: `markdown`)
- `--screen-renderer` CLI flag (default: `svg`)
- Config-driven resolution

---

## Phase 3: Agent Runner + Execution Mode Plugins

### Task 3.1: Create `ExecutionMode` strategy pattern

**Files:**
- Modify: `termproof/runner.py` (extract execution dispatch)
- Create: `termproof/builtin_modes.py`

```python
class ExecutionMode(Protocol):
    name: str

    def execute(
        self,
        runner: VerificationRunner,
        recipe: Recipe,
        run_dir: Path,
    ) -> tuple[list[StepResult], list[AssertionResult], str, int | None, str]:
        ...
```

Built-in: `ScriptedPtyMode`, `ScriptedProcessMode`, `AgentDrivenMode`.

### Task 3.2: Generalize `AgentRunner` registry

**Files:**
- Modify: `termproof/agent_driven.py`

Register `CodexCliAgentRunner` as the built-in. Allow config to register alternative agent runners (e.g., Claude Code, custom shell script).

---

## Phase 4: Session + Video + Cast Backends

### Task 4.1: Create `SessionBackend` protocol

**Files:**
- Create: `termproof/builtin_session.py`
- Modify: `termproof/session.py`

```python
class SessionBackend(Protocol):
    def create_session(
        self,
        argv: list[str],
        cast_path: Path,
        cwd: str | None,
        env: dict[str, str],
        cols: int,
        rows: int,
    ) -> TerminalSession:
        ...
```

Built-in: `PexpectAsciinemaBackend` (current behavior using pexpect+asciinema). Future: `ScriptBackend` (wraps `script(1)`), `TmuxBackend`.

### Task 4.2: Create `VideoBackend` protocol

**Files:**
- Create: `termproof/builtin_video.py`
- Modify: `termproof/evidence.py`

```python
class VideoBackend(Protocol):
    name: str

    def render(
        self,
        cast_path: Path,
        output_path: Path,
        fps: int,
    ) -> None:
        ...
```

Built-in: `AggFfmpegBackend` (current agg+ffmpeg behavior). Future: `SvgTermBackend`, `VhsBackend`.

### Task 4.3: Wire session and video backends into config

---

## Backward Compatibility Guarantees

1. **All existing recipe JSON files continue to work unchanged.** The built-in defaults exactly mirror current behavior.
2. **CLI interface unchanged.** `termproof run recipes/` works identically. New flags are additive.
3. **No config file required.** If no config file exists, everything defaults to current behavior.
4. **Python API unchanged.** `VerificationRunner()` with no args uses built-in defaults.

## Files That Change

```
termproof/
├── config.py              NEW — VerifierConfig, load_config(), cascading loader
├── registry.py            MODIFY — add generic Registry[T]
├── builtin_steps.py       NEW — step action classes
├── builtin_assertions.py  NEW — assertion type classes
├── builtin_reporters.py   NEW — reporter classes
├── builtin_renderers.py   NEW — screen renderer classes
├── builtin_modes.py       NEW — execution mode classes
├── builtin_session.py     NEW — session backend class
├── builtin_video.py       NEW — video backend class
├── runner.py              MODIFY — use registries instead of if/elif
├── cli.py                 MODIFY — load config, pass to runner, new flags
├── models.py              MODIFY — minor (Recipe gains optional config fields)
├── __init__.py            MODIFY — export new public API
└── (session, screen, cast, evidence, report, agent_driven, scaffold, before_after, build_info)
                           MINOR — extracted logic moves to builtin_*.py

tests/
├── test_config.py         NEW — config loading, cascading, defaults
├── test_registry.py       NEW — registry get/register/fallback
├── test_runner.py         MODIFY — config integration
├── test_stack_design.py   MODIFY — extended
└── (others)               NO CHANGE — existing tests pass as-is

pyproject.toml             MODIFY — add pyyaml dep
```

## Risks and Tradeoffs

| Risk | Mitigation |
|---|---|
| Over-abstraction | Each protocol is justified by at least one concrete use case beyond the built-in |
| Plugin discovery complexity | Phase 1 uses simple `module:Class` strings in YAML; entry points optional later |
| Config fatigue | Sensible defaults, no config file needed for basic use |
| Performance impact of registry lookup | Registries are populated once at startup, lookup is O(1) dict access |

## Open Questions

1. **Entry points vs YAML strings?** Phase 1 uses YAML `module:Class` strings for simplicity. Python entry points (`termproof.plugins`) can be added as an alternative discovery mechanism in a later phase.

2. **Should recipes gain a `config` field?** Defer to a later phase. Currently all config is external to recipes, keeping the recipe format stable.

3. **Does `TerminalSession` stay or get abstracted?** Phase 4 abstracts it. For phases 1-3, `TerminalSession` remains the concrete session type passed to step actions and assertion evaluators — only the backend that creates it gets abstracted later.

---

## Verification Strategy

After each phase:
1. `pytest tests/ -v` — all existing tests pass
2. New phase-specific tests pass
3. Manual smoke test: `uv run termproof run examples/generic/generic_tui.recipe.json --video`
4. Manual config test: create a `.termproof/config.yaml` that registers a custom step action, verify it loads and executes

---

## Implementation Order Summary

| Phase | What | Complexity | Risk |
|---|---|---|---|
| 1 | Config system + step/assertion registry | Medium | Low — core architectural decision |
| 2 | Reporter + screen renderer plugins | Low | Low — isolated subsystems |
| 3 | Agent runner + execution mode plugins | Medium | Medium — touches core runner dispatch |
| 4 | Session + video + cast backends | High | Medium — deep OS integration points |
