# Plugin protocol stability

TermProof exposes stable plugin protocols from `termproof.protocols`.

## Stable protocols

| Protocol | Required method |
| --- | --- |
| `StepAction` | `execute(session, step, index) -> StepResult` |
| `AssertionType` | `evaluate(recipe, assertion, screen, raw_output, exit_code) -> AssertionResult` |
| `ExecutionMode` | `execute(runner, recipe, run_dir) -> tuple[list[StepResult], list[AssertionResult], str, int | None, str]` |
| `Reporter` | `generate(results, build_info=None, before_after=None) -> str` |
| `ScreenRenderer` | `render(text, output_path, cols, rows) -> None` |
| `VideoBackend` | `render(cast_path, output_path, fps) -> None` |
| `AgentRunner` | `run(recipe, prompt, run_dir) -> AgentOutcome` |
| `SessionBackend` | `create_session(argv, cast_path, cwd, env, cols, rows) -> TerminalSession` |

`StepAction`, `AssertionType`, `ExecutionMode`, `Reporter`, `ScreenRenderer`, and `VideoBackend` also require a `name: str` class attribute. `AgentRunner` and `SessionBackend` are selected by config keys and do not require a `name`.

`ScreenRenderer` plugins can optionally set `extension = "png"` (or another file extension) so evidence artifacts use that screenshot filename suffix.

### Optional: `render_attributed`

`render` receives the screen as a string, which cannot express colour, bold or
reverse video. A `ScreenRenderer` may additionally define:

```python
def render_attributed(
    self,
    screen: AttributedScreen,
    output_path: Path,
    cols: int,
    rows: int,
) -> None: ...
```

`AttributedScreen` (from `termproof.attributed`) is a per-cell grid: every
`AttributedCell` carries its glyph plus `fg`, `bg`, `bold`, `dim`, `italic`,
`underline`, `strikethrough`, `reverse` and `width`. Colours are either the
literal `"default"`, a pyte colour name such as `"red"`, or a bare `RRGGBB`
hex string; `attributed.cell_colors(cell, style)` resolves one to concrete CSS
colours, applying reverse video.

When the method is present and the pipeline has a grid to offer, TermProof calls
it in preference to `render`, so nothing is lost re-parsing text that the
terminal emulator already parsed. This is additive: a renderer that defines only
`render` keeps working unchanged and keeps receiving the screen as text. Both
builtin `svg` and `png_rsvg` implement it; `png` does not.

`ScreenRenderer` and `VideoBackend` plugins can optionally define a
`from_config(cls, evidence: EvidenceConfig) -> Self` classmethod. When it is
present TermProof calls it instead of the zero-argument constructor, so the
plugin can read the `evidence` config block (see the Configuration section of
the README). Plugins without it keep being constructed with no arguments.
`EvidenceConfig`, and the narrower `SvgRenderConfig`, `PngRenderConfig`, and
`VideoConfig` its sections hold, are exported from `termproof.protocols`
alongside the protocols themselves.

## ExecutionMode runner surface

An `ExecutionMode.execute` implementation receives a `VerificationRunner` and
should only call its stable public methods rather than any underscore-prefixed
internals:

| Method | Purpose |
| --- | --- |
| `run_pty(recipe, run_dir) -> tuple[list[StepResult], str, int | None, str]` | Run scripted steps interactively over a PTY session. |
| `run_process(recipe, run_dir) -> tuple[list[StepResult], str, int | None, str]` | Run the command to completion, then replay the cast. |
| `run_agent_driven(recipe, run_dir) -> tuple[list[StepResult], list[AssertionResult], str, int | None, str]` | Delegate execution to the configured agent runner. |
| `evaluate_assertions(recipe, screen, raw_output, exit_code) -> list[AssertionResult]` | Evaluate a recipe's assertions against captured output. |

The former private methods (`_run_pty`, `_run_process`, `_run_agent_driven`,
`_evaluate_assertions`) remain as deprecated aliases that delegate to the public
methods, but new execution modes should use the public surface above.

## Import policy

New plugins should import protocols from `termproof.protocols`:

```python
from termproof.protocols import StepAction, AssertionType, Reporter
```

The older import locations, such as `termproof.builtin_steps.StepAction`, remain compatibility re-exports.

## Version and deprecation policy

- The signatures above are stable for TermProof `0.x` and `1.x`.
- Additive changes are allowed when existing plugins keep working without source changes.
- Breaking protocol changes require a major version bump and a migration guide.
- Deprecated protocol behavior must stay available for at least one minor release after the deprecation is documented.
- Legacy `tui_verifier.*:Class` config references are still remapped to `termproof.*:Class`.
