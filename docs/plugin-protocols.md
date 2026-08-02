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
