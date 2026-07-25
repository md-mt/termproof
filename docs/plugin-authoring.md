# Plugin Authoring Guide

This guide shows how to extend tui-verifier with custom step actions, assertion evaluators, execution modes, renderers, reporters, video backends, and session backends. All examples reflect actual protocol signatures from the source.

## Minimal Principle

- One class per extension point, zero-arg constructor.
- Read per-invocation parameters from the `step`/`assertion`/`recipe` dict at call time.
- Class attribute `name` matches the config key.
- Value in config YAML is `"my_pkg.module:MyClass"`.

## Custom Step Action

Protocol (`builtin_steps.py`):

```python
class StepAction(Protocol):
    name: str
    def execute(self, session: TerminalSession, step: dict[str, Any], index: int) -> StepResult: ...
```

Example: wait for a count of occurrences.

```python
# my_pkg/steps.py
from tui_verifier.models import StepResult
from tui_verifier.session import TerminalSession
from typing import Any

class WaitForCount:
    name = "wait_for_count"

    def execute(self, session: TerminalSession, step: dict[str, Any], index: int) -> StepResult:
        display = step.get("name", f"{index}:{self.name}")
        needle = step["text"]
        expected = int(step.get("count", 1))
        timeout = float(step.get("timeout_seconds", 10))
        deadline_stable = __import__("time").monotonic() + timeout
        while __import__("time").monotonic() < deadline_stable:
            session.read_available(0.05)
            occurrences = session.raw_output.count(needle) + session.screen.count(needle)
            if occurrences >= expected:
                return StepResult(display, True, f"found {occurrences} occurrences of {needle!r}", session.screen)
            if not session.is_alive():
                break
        return StepResult(display, False, f"timed out waiting for {expected}x {needle!r}", session.screen)
```

Register in `.tui-verifier/config.yaml`:

```yaml
steps:
  wait_for_count: "my_pkg.steps:WaitForCount"
```

Use in recipe:

```json
{ "action": "wait_for_count", "text": "READY", "count": 2, "timeout_seconds": 15 }
```

Context: `TerminalSession` exposes `raw_output` (str), `screen` (property), `is_alive()`, `read_available(timeout)`, `send_text`, `send_line`, `press`, etc. `session.screen` is post-ANSI, pyte-rendered.

## Custom Assertion

Protocol (`builtin_assertions.py`):

```python
class AssertionType(Protocol):
    name: str
    def evaluate(self, recipe: Recipe, assertion: dict[str, Any],
                 screen: str, raw_output: str, exit_code: int | None) -> AssertionResult: ...
```

Example: regex match on screen.

```python
# my_pkg/assertions.py
import re
from pathlib import Path
from typing import Any
from tui_verifier.models import AssertionResult, Recipe

class ScreenMatchesRegex:
    name = "screen_matches"

    def evaluate(self, recipe: Recipe, assertion: dict[str, Any],
                 screen: str, raw_output: str, exit_code: int | None) -> AssertionResult:
        pattern = assertion["value"]  # e.g., r"Score:\s+\d+"
        matched = re.search(pattern, screen) is not None
        return AssertionResult(
            assertion.get("name", self.name),
            matched,
            f"{'matched' if matched else 'did not match'} regex {pattern!r}",
        )
```

Config:

```yaml
assertions:
  screen_matches: "my_pkg.assertions:ScreenMatchesRegex"
```

Recipe:

```json
{ "type": "screen_matches", "value": "Score:\\s+\\d+" }
```

Notes:

- Path resolution helper in real code: `_recipe_path(recipe, path)` — absolute passthrough, relative against `recipe.command.cwd or "."`. Replicate that pattern for file-based assertions.
- Existing builtins raise detail as human-readable string; keep same convention.

## Custom Screen Renderer

Protocol (`builtin_renderers.py`):

```python
class ScreenRenderer(Protocol):
    name: str
    def render(self, text: str, output_path: Path, cols: int, rows: int) -> None: ...
```

Example: PNG via PIL (illustrative — not bundled).

```python
# my_pkg/renderers.py
from pathlib import Path

class PngRenderer:
    name = "png"

    def render(self, text: str, output_path: Path, cols: int, rows: int) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            raise RuntimeError("Pillow is required for png renderer")
        # Simplified: fixed-size canvas, monospace font
        line_height = 18
        char_width = 8
        width = max(320, cols * char_width + 36)
        height = max(160, rows * line_height + 36)
        img = Image.new("RGB", (width, height), "#101418")
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("Menlo.ttc", 14)
        except OSError:
            font = ImageFont.load_default()
        for i, line in enumerate(text.splitlines()[:rows]):
            draw.text((18, 18 + i * line_height), line, fill="#e6edf3", font=font)
        img.save(output_path)
```

Config:

```yaml
screen_renderers:
  png: "my_pkg.renderers:PngRenderer"
```

CLI:

```bash
tui-verify run recipes/ --screen-renderer png
```

`render_artifacts()` in `evidence.py` receives `screen_renderer` and calls `render()` for final + each step. If `None`, it falls back to `screen.render_svg()`.

## Custom Reporter

Protocol (`builtin_reporters.py`):

```python
class Reporter(Protocol):
    name: str
    def generate(self, results: list[RunResult],
                 build_info: BuildInfo | None = None,
                 before_after: BeforeAfterResult | None = None) -> str: ...
```

Example: JSON summary reporter.

```python
# my_pkg/reporters.py
import json
from tui_verifier.before_after import BeforeAfterResult
from tui_verifier.build_info import BuildInfo
from tui_verifier.models import RunResult

class JsonReporter:
    name = "json"

    def generate(self, results: list[RunResult],
                 build_info: BuildInfo | None = None,
                 before_after: BeforeAfterResult | None = None) -> str:
        payload = {
            "passed": sum(1 for r in results if r.passed),
            "total": len(results),
            "results": [r.to_dict() for r in results],
            "build_info": build_info.to_dict() if build_info else None,
        }
        return json.dumps(payload, indent=2) + "\n"
```

Config + CLI:

```yaml
reporters:
  json: "my_pkg.reporters:JsonReporter"
```

```bash
tui-verify run recipes/ --reporter json
```

## Custom Session Backend

Protocol (`builtin_session.py`):

```python
class SessionBackend(Protocol):
    def create_session(self, argv: list[str], cast_path: Path,
                       cwd: str | None, env: dict[str, str],
                       cols: int, rows: int) -> TerminalSession: ...
```

Example: replace pexpect with alternative but still return `TerminalSession` subtype or compatible interface (must provide `raw_output`, `screen`, `exit_code`, `wait_for_text`, `wait_for_idle`, `wait_for_exit`, `read_available`, `is_alive`, `send_text`, `send_line`, `press`, etc.). Minimal wrapper:

```python
# my_pkg/session.py
from pathlib import Path
from tui_verifier.session import TerminalSession

class MySessionBackend:
    def create_session(self, argv: list[str], cast_path: Path,
                       cwd: str | None, env: dict[str, str],
                       cols: int, rows: int) -> TerminalSession:
        # For example inject extra env, then delegate:
        # actual customization would subclass TerminalSession
        return TerminalSession(argv, cast_path, cwd, env, cols, rows)
```

Config (single value, not dict):

```yaml
session_backend: "my_pkg.session:MySessionBackend"
```

No CLI flag — only config.

## Custom Video Backend

Protocol (`builtin_video.py`):

```python
class VideoBackend(Protocol):
    name: str
    def render(self, cast_path: Path, output_path: Path, fps: int) -> None: ...
```

Example: no-op backend for CI without ffmpeg.

```python
# my_pkg/video.py
from pathlib import Path

class NoopVideoBackend:
    name = "noop"

    def render(self, cast_path: Path, output_path: Path, fps: int) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("# video disabled\n")
```

Config:

```yaml
video_backends:
  noop: "my_pkg.video:NoopVideoBackend"
```

```bash
tui-verify run recipes/ --video --video-backend noop
```

Note: `render_artifacts()` already guards `render_video` with `shutil.which("agg")` — if `agg` missing, video step is skipped even if backend exists. Use custom backend only when `agg` is present but you want different encoding, or create session backend that does not require `agg`.

## Custom Execution Mode

Protocol (`builtin_modes.py`):

```python
class ExecutionMode(Protocol):
    name: str
    def execute(self, runner: Any, recipe: Recipe, run_dir: Path
               ) -> tuple[list[StepResult], list[AssertionResult], str, int | None, str]: ...
```

Example: mode that ignores timeout and always passes steps.

```python
# my_pkg/modes.py
from pathlib import Path
from typing import Any
from tui_verifier.models import Recipe, StepResult, AssertionResult

class LenientPtyMode:
    name = "lenient_pty"

    def execute(self, runner: Any, recipe: Recipe, run_dir: Path):
        steps, raw_output, exit_code, screen = runner._run_pty(recipe, run_dir)
        # don't evaluate assertions — mark all assertions pass
        assertions = [AssertionResult("lenient", True, "lenient mode skips assertions")]
        return steps, assertions, raw_output, exit_code, screen
```

Config:

```yaml
execution_modes:
  lenient_pty: "my_pkg.modes:LenientPtyMode"
```

But note `_resolve_execution_mode_name()` only returns 3 names currently — `agent_driven`, `scripted_pty`, `scripted_process`. To use custom name you would need to set `execution` field to a value that maps? As currently implemented, mapping is hardcoded. So custom execution mode names require either (a) overriding `execution` of recipe to custom value and also monkey-patching `_resolve_execution_mode_name` logic via fork, or (b) adding extra logic to `load_config` mapping to override the three built-in keys. The config maps name → qualname, but resolver still only returns one of three names. To actually use custom execution mode named `lenient_pty`, you would need to either:

- Replace `scripted_pty` key in config with your custom class: `execution_modes: {scripted_pty: "my_pkg.modes:LenientPtyMode"}` — then every PTY recipe uses lenient mode.
- Or fork `runner._resolve_execution_mode_name` — this is a current limitation.

Documenting accurately: custom execution modes override built-in mode names, rather than introduce new recipe `execution` values (unless resolver extended).

## Custom Agent Runner

Protocol (`agent_driven.py`):

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

Example: echo agent that always passes.

```python
# my_pkg/agent.py
from pathlib import Path
from tui_verifier.agent_driven import AgentOutcome
from tui_verifier.models import Recipe

class EchoAgentRunner:
    def run(self, recipe: Recipe, prompt: str, run_dir: Path) -> AgentOutcome:
        checks = recipe.checks or ["default check"]
        return AgentOutcome(
            assertions={check: True for check in checks},
            transcript=f"Echo: {prompt[:200]}",
            raw_output=f'{{"assertions": {{{", ".join(f'"{c}": true' for c in checks)}}}, "transcript": "echo"}}',
            exit_code=0,
            metadata={"agent": "echo"},
        )
```

Config:

```yaml
agent_runners:
  echo: "my_pkg.agent:EchoAgentRunner"
```

Then in recipe:

```json
{ "execution": "agent-driven", "operator": { "command": ["echo-agent"], "command": ["echo"] }, ... }
```

Wait — actual `from_recipe` method reads `recipe.operator` dict for `CodexCliAgentRunner`. For generic `AgentRunner`, resolution is via `VerificationRunner.agent_runner_registry.get(name)` — name originates from `recipe.operator.command`? Let's trace: in `VerificationRunner._run_agent_driven()`, it either uses `self.agent_runner` (if `--operator-command` supplied) or `CodexCliAgentRunner.from_recipe(recipe)`. The agent_runner_registry is built but not currently used by execution mode? Indeed `_build_agent_runner_registry` builds it, but `_run_agent_driven` does not consult it — it goes directly to Codex cli runner. The registry exists for future custom operator `command` selection but current code path bypasses it. Custom agent runner can still be used by injecting via CLI `--operator-command` (which creates Codex runner with that command) or by constructing `VerificationRunner` programmatically:

```python
from tui_verifier.config import VerifierConfig
from tui_verifier.runner import VerificationRunner
from my_pkg.agent import EchoAgentRunner

config = VerifierConfig.builtin()
runner = VerificationRunner(agent_runner=EchoAgentRunner(), config=config)
```

Python API allows arbitrary `AgentRunner`; registry-based selection from config is a reserved slot that currently not wired to execution mode beyond builtin `codex` key.

For factual accuracy: agent_runners registry entries are loadable but execution path currently hard-codes `CodexCliAgentRunner`. Custom `AgentRunner` via config alone won't execute without Python-level injection or future runner change.

## Recipe-Level Examples

### Minimal PTY Recipe

```json
{
  "name": "my-tui-main-flow",
  "description": "Open dashboard and export.",
  "priority": "P0",
  "execution": "scripted",
  "renderers": { "default": [] },
  "command": { "argv": ["my-tui"], "pty": true },
  "timeout_seconds": 30,
  "cols": 100,
  "rows": 30,
  "steps": [
    { "name": "wait for prompt", "action": "wait_for_text", "text": "my-tui>", "timeout_seconds": 5 },
    { "name": "open dashboard", "action": "send_line", "text": "open dashboard" },
    { "name": "wait for dashboard", "action": "wait_for_text", "text": "DASHBOARD READY", "timeout_seconds": 10 }
  ],
  "assertions": [
    { "type": "output_contains", "value": "DASHBOARD READY" }
  ],
  "expect_exit_code": 0
}
```

### Non-PTY Process Recipe

```json
{
  "name": "my-tui-help",
  "priority": "P0",
  "execution": "scripted",
  "command": { "argv": ["my-tui", "--help"], "pty": false },
  "steps": [
    { "action": "wait_for_text", "text": "Usage:", "timeout_seconds": 5 }
  ],
  "assertions": [
    { "type": "output_contains", "value": "Usage:" }
  ],
  "expect_exit_code": 0
}
```

### Multi-Renderer Recipe (from README)

```json
{
  "renderers": { "opentui": [], "ink": ["--renderer", "ink"] }
}
```

`--renderer all` expands to runs against both argv variants via `_with_renderer_argv()`.

### File Assertions

```json
{
  "assertions": [
    { "type": "file_exists", "value": "output/report.json" },
    { "type": "file_contains", "path": "output/report.json", "value": "PASS" }
  ]
}
```

`_recipe_path` resolves relative path against `command.cwd or "."`.

## Common Pitfalls

- Step factory must be zero-arg — don't put config in `__init__`, read from `step` dict in `execute()`.
- Assertion factory must be zero-arg — read `assertion` dict in `evaluate()`.
- Qualname format is `"module:Class"` with colon, not dot. `_import_class` checks for colon and raises `ValueError` otherwise.
- `Registry.get()` raises `KeyError` with available sorted names — handle in caller if you want custom error.
- `session_backend` is single string — replacing it replaces whole backend; you cannot have multiple session backends concurrently (runner resolves one).
- Video backend only called if `render_video True` and `shutil.which("agg")` passes in `render_artifacts()`. Without `agg`, video rendering silently skipped regardless of backend config unless you patch that guard too.
