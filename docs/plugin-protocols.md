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
