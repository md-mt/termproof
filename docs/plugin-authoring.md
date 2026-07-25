# Plugin Authoring Guide

This guide shows how to extend tui-verifier with custom step actions, assertion evaluators, execution modes, renderers, reporters, video backends, and session backends. All examples reflect actual protocol signatures from the source and runtime limitations noted in `extension-points.md`.

## Minimal Principle

- One class per extension point, zero-arg constructor.
- Read per-invocation parameters from the `step`/`assertion`/`recipe` dict at call time.
- Registry key, not class name, controls lookup — `name = "..."` on the class is conventional but lookup uses the YAML key you chose. Equality is not validated, and `AgentRunner`/`SessionBackend` protocols have no `name` field.
- Value in config YAML is `"my_pkg.module:MyClass"`.

## Custom Step Action

Protocol (`builtin_steps.py`):

```python
class StepAction(Protocol):
    name: str
    def execute(self, session: TerminalSession, step: dict[str, Any], index: int) -> StepResult: ...
```

Positioning: steps dispatch through the registry **only in PTY mode** (`command.pty=true`). Process mode hardcodes `wait_for_text`/`sleep`; agent mode does not dispatch recipe steps at all. See `extension-points.md`.

Example: wait for a count of occurrences.

Note: the prior version of this example double-counted by summing `raw_output.count + screen.count`. The same terminal output appears in both representations, so counting both double-counts. The corrected example below checks `screen` first (post-ANSI, de-duplicated view) and only falls back to `raw_output` if needed.

```python
# my_pkg/steps.py
import time
from typing import Any
from tui_verifier.models import StepResult
from tui_verifier.session import TerminalSession

class WaitForCount:
    name = "wait_for_count"

    def execute(self, session: TerminalSession, step: dict[str, Any], index: int) -> StepResult:
        display = step.get("name", f"{index}:{self.name}")
        needle = step["text"]
        expected = int(step.get("count", 1))
        timeout = float(step.get("timeout_seconds", 10))
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            session.read_available(0.05)
            # Check screen rather than raw_output.count + screen.count to avoid double-counting
            haystack = session.screen if needle in session.screen else session.raw_output
            occurrences = haystack.count(needle)
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

Positioning: assertion registry is used only by scripted modes (PTY and process), not by agent checks — agent mode evaluates `recipe.checks` against agent-reported booleans via `_agent_assertions()` at `agent_driven.py:212-225`.

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

## Custom Screen Renderer — Fixed `.svg` Contract

Protocol (`builtin_renderers.py`):

```python
class ScreenRenderer(Protocol):
    name: str
    def render(self, text: str, output_path: Path, cols: int, rows: int) -> None: ...
```

**Important: evidence pipeline always supplies `.svg` paths.** `evidence.render_artifacts()` at `evidence.py:34-43` passes `run_dir/final.svg`, and per-step at `76-83` passes `{index:02d}-{safe}.svg`. It also always reports `screenshot` under that `.svg` path. A renderer using `PIL.Image.save(output_path)` would receive an `.svg` path and produce an invalid file (or mis-detected image type) while artifact metadata still says `.svg`. The prior PNG-via-PIL example is therefore invalid through the current pipeline and has been replaced with an SVG-compatible example.

If you need PNG output, either fork `evidence.py` to pass extension-appropriate paths or provide a custom `evidence.render_artifacts` wrapper.

### Styled SVG example (extension-compatible)

This example respects the fixed `.svg` contract — it writes valid SVG, but with custom styling.

```python
# my_pkg/renderers.py
import html
from pathlib import Path

class StyledSvgRenderer:
    name = "svg_styled"

    def render(self, text: str, output_path: Path, cols: int, rows: int) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        line_height = 20
        char_width = 9
        padding = 18
        width = max(320, cols * char_width + padding * 2)
        height = max(160, rows * line_height + padding * 2)
        visible_lines = text.splitlines()[:rows] or [""]
        parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
            '<rect width="100%" height="100%" fill="#1a1f2e"/>',
            '<style>text{font:14px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;fill:#c8d3f5;white-space:pre}</style>',
        ]
        for index, line in enumerate(visible_lines):
            y = padding + line_height * (index + 1)
            parts.append(f'<text x="{padding}" y="{y}">{html.escape(line)}</text>')
        parts.append("</svg>")
        output_path.write_text("\n".join(parts) + "\n", encoding="utf-8")
```

Config:

```yaml
screen_renderers:
  svg_styled: "my_pkg.renderers:StyledSvgRenderer"
```

CLI:

```bash
tui-verify run recipes/ --screen-renderer svg_styled
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

## Custom Session Backend — Context Manager Required

Protocol (`builtin_session.py`):

```python
class SessionBackend(Protocol):
    def create_session(self, argv: list[str], cast_path: Path,
                       cwd: str | None, env: dict[str, str],
                       cols: int, rows: int) -> TerminalSession: ...
```

Compatibility: a session object returned by `create_session` must be a **context manager** because `runner.py:222-229,247-254` uses `with ...create_session(...) as session:`. So subclass `TerminalSession` (which already implements `__enter__`/`__exit__`) or provide an object implementing both `__enter__` and `__exit__` plus `raw_output`, `screen`, `exit_code`, `wait_for_text`, `wait_for_idle`, `wait_for_exit`, `read_available`, `is_alive`, `send_text`, `send_line`, `press`, `close`, and `raw_output`.

Additionally, non-recorded agent mode at `agent_driven.py:87-131` bypasses the session backend entirely (uses `subprocess.run`), so custom backends have no effect when `record_terminal=False`.

Example: minimal delegation backend:

```python
# my_pkg/session.py
from pathlib import Path
from tui_verifier.session import TerminalSession

class MySessionBackend:
    def create_session(self, argv: list[str], cast_path: Path,
                       cwd: str | None, env: dict[str, str],
                       cols: int, rows: int) -> TerminalSession:
        # For example inject extra env, then delegate:
        merged_env = {**env, "MY_INJECTED": "1"}
        return TerminalSession(argv, cast_path, cwd, merged_env, cols, rows)
```

Config (single value, not dict):

```yaml
session_backend: "my_pkg.session:MySessionBackend"
```

No CLI flag — only config.

## Custom Video Backend — Gated on `agg`

Protocol (`builtin_video.py`):

```python
class VideoBackend(Protocol):
    name: str
    def render(self, cast_path: Path, output_path: Path, fps: int) -> None: ...
```

Important guard at `evidence.py:55-60`:

```python
if render_video and shutil.which("agg"):
    # backend invoked here
```

A video backend only runs when `--video` is set **and** `agg` binary is on PATH. A custom session backend cannot avoid the guard — it lives in `render_artifacts()` before any video backend call and is independent of session backend. Only forking `evidence.py` or installing `agg` fixes it.

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
tui-verify run recipes/ --video --video-backend noop  # still requires agg on PATH
```

## Custom Execution Mode — Only Fixed Keys Work

Protocol (`builtin_modes.py`):

```python
class ExecutionMode(Protocol):
    name: str
    def execute(self, runner: Any, recipe: Recipe, run_dir: Path
               ) -> tuple[list[StepResult], list[AssertionResult], str, int | None, str]: ...
```

Execution resolver at `runner.py:128-134` only returns 3 fixed names:

```python
def _resolve_execution_mode_name(recipe: Recipe) -> str:
    if recipe.execution == "agent-driven":
        return "agent_driven"
    if recipe.command.pty:
        return "scripted_pty"
    return "scripted_process"
```

So adding a new execution mode name like `lenient_pty` to the config YAML parses but is never returned by the resolver. To actually use a custom execution mode, you must **replace** one of the fixed keys:

```yaml
# Replace PTY execution with lenient variant — every PTY recipe uses lenient mode
execution_modes:
  scripted_pty: "my_pkg.modes:LenientPtyMode"
```

If you need a brand-new execution name, you must fork `runner._resolve_execution_mode_name` — this is a current limitation.

Example: lenient PTY mode that skips assertions:

```python
# my_pkg/modes.py
from pathlib import Path
from typing import Any
from tui_verifier.models import Recipe, StepResult, AssertionResult

class LenientPtyMode:
    name = "lenient_pty"  # name here is conventional; the YAML key is what the resolver uses

    def execute(self, runner: Any, recipe: Recipe, run_dir: Path):
        steps, raw_output, exit_code, screen = runner._run_pty(recipe, run_dir)
        assertions = [AssertionResult("lenient", True, "lenient mode skips assertions")]
        return steps, assertions, raw_output, exit_code, screen
```

Config (must override a fixed key to be wired):

```yaml
execution_modes:
  scripted_pty: "my_pkg.modes:LenientPtyMode"
```

## Custom Agent Runner — Programmatic Path Is the Truthful One

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

Important limitations:

- `agent_runner_registry` (`runner.py:94-99,150`) is built from config `agent_runners` but **never read** by `_run_agent_driven()`. Config-only replacement has no effect today.
- The prior docs used an `EchoAgent` with `recipe.operator` hardcoded to `Codex` and a recipe line containing duplicate `command` keys (invalid JSON). The `EchoAgent` check semantics were also wrong — when `recipe.checks` is empty, `AgentDrivenRunner` at `agent_driven.py:212-225` uses default check `"Codex operator completed the verification"`, so an `EchoAgentRunner` returning `{"default check": True}` would not satisfy that check.

**Truthful programmatic path:**

```python
# my_pkg/agent.py
from pathlib import Path
from tui_verifier.agent_driven import AgentOutcome
from tui_verifier.models import Recipe

class EchoAgentRunner:
    """Always-passing agent that returns all checks True."""

    def run(self, recipe: Recipe, prompt: str, run_dir: Path) -> AgentOutcome:
        # Default check used by runner when recipe.checks is empty
        checks = recipe.checks or ["Codex operator completed the verification"]
        return AgentOutcome(
            assertions={check: True for check in checks},
            transcript=f"Echo: {prompt[:200]}",
            raw_output='{"assertions": {'
                       + ", ".join(f'"{c}": true' for c in checks)
                       + '}, "transcript": "echo"}',
            exit_code=0,
            metadata={"agent": "echo"},
        )
```

Usage — programmatic injection (the only currently wired path for custom Python runners):

```python
from tui_verifier.config import VerifierConfig
from tui_verifier.runner import VerificationRunner
from my_pkg.agent import EchoAgentRunner

config = VerifierConfig.builtin()
runner = VerificationRunner(agent_runner=EchoAgentRunner(), config=config)
# Explicitly use agent-driven execution via recipe's execution field:
# recipe.execution = "agent-driven"
result = runner.run(recipe, out_dir=Path(".tui-verifier/runs"), render_video=False)
```

Alternatively via CLI `--operator-command`, which creates `CodexCliAgentRunner` with that command (not your custom class). Custom `AgentRunner` via config alone won't execute without Python-level injection or future runner change.

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

Note: process mode evaluates steps via `_evaluate_output_steps()` — only `wait_for_text` and `sleep` do anything meaningful; other actions return failure requiring PTY.

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
- `Registry.get()` raises `KeyError` with available sorted names — Runner wraps unknown step/assertion as `ValueError("unknown step action")` / `ValueError("unknown assertion type")`.
- `session_backend` is single string — replacing it replaces whole backend; you cannot have multiple session backends concurrently (runner resolves one).
- Session backend must be a context manager (`__enter__`/`__exit__`) because runner uses `with ...create_session(...)`.
- Non-recorded agent mode (`record_terminal=False`) bypasses session backend — it calls `subprocess.run` directly.
- Video backend only called if `render_video True` and `shutil.which("agg")` passes in `render_artifacts()` at `evidence.py:55-60`. Without `agg`, video rendering silently skipped regardless of backend config unless you patch that guard too.
- Execution resolver only emits 3 fixed names — new execution mode names require replacing `scripted_pty`/`scripted_process`/`agent_driven` or patching `runner._resolve_execution_mode_name`.
- `agent_runner_registry` is built but unused — custom Python runner requires programmatic `VerificationRunner(agent_runner=...)`, not just config YAML.
- Screen renderer receives fixed `.svg` paths from `evidence.py` — PNG-style examples are invalid unless pipeline changed.
