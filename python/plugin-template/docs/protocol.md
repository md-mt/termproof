# Protocol compatibility

## Stable protocols (TermProof >=0.2.1)

| Extension point | Config key | Example qualname |
|-----------------|------------|-------------------|
| Step | steps | my_plugin.steps:WaitForRegex |
| Assertion | assertions | my_plugin.assertions:ScreenCount |
| Reporter | reporters | my_plugin.reporters:JsonSummaryReporter |
| Screen renderer | screen_renderers | my_plugin.renderers:PngRenderer |
| Video backend | video_backends | my_plugin.video:CustomBackend |
| Session backend | session_backend | my_plugin.session:DockerBackend |
| Execution mode | execution_modes | my_plugin.modes:MyMode |
| Agent runner | agent_runners | my_plugin.agents:MyRunner |
| Artifact publisher | artifact_publishers | my_plugin.publishers:MyStore |

Import protocols from `termproof.protocols`. Older module locations still re-export the same protocol objects for compatibility.

Most protocols require a `name` class attribute and a single method:

- Step: execute(session, step, index) -> StepResult
- Assertion: evaluate(recipe, assertion, screen, raw_output, exit_code) -> AssertionResult
- Step-aware assertion: evaluate(recipe, assertion, screen, raw_output, exit_code, *, steps=None) -> AssertionResult
- Reporter: generate(results, build_info, before_after) -> str
- ScreenRenderer: render(text, output_path, cols, rows) -> None
- VideoBackend: render(cast_path, output_path, fps) -> None
- SessionBackend: create_session(argv, cast_path, cwd, env, cols, rows) -> TerminalSession
- ExecutionMode: execute(runner, recipe, run_dir) -> (steps, assertions, raw_output, exit_code, screen)
- AgentRunner: run(recipe, prompt, run_dir) -> AgentOutcome
- ArtifactPublisher: publish(source, key) -> PublishedArtifact

AgentRunner and SessionBackend are selected by config keys and do not require a `name`.

## Publishing evidence

An ArtifactPublisher decides where evidence goes after a run. `key` is the
destination-relative identifier the caller has chosen, so a publisher maps that
key onto its own namespace instead of inventing a layout.

`PublishedArtifact(source, key, url="", published=True, detail="")` is a record
rather than a bare URL because reports link evidence by local path: rewriting
those links needs `source` and `url` together, which is what
`termproof.evidence_publish.url_map_from_published` builds. A publisher reports
`published=False` when it did not transfer the bytes, and an empty `url` when it
did but cannot name a public address for them; neither has to raise.

Deployment settings (bucket, endpoint, public base URL, dry-run) arrive through
an optional `from_target(cls, target)` classmethod rather than from
`.termproof/config.yaml`, since that file is checked in. Publishers without it
are constructed with no arguments. A publisher that takes a target has to honour
`dry_run`: name the URL the artifact would get, report `published=False`, and
move nothing.

Publishers compose, because a publisher is just an object returning results: a
wrapper that tries one store, falls back to another and records the degradation
in `detail` is a plain implementation of the same protocol. TermProof does not
ship one.

## Context availability for assertions

Available at assertion evaluation time:

- **Final screen** and **final raw output** — the `screen` and `raw_output`
  arguments
- **Exit code** — `None` when the target had not exited
- **The recipe** — including `command.cwd`, which is what the file assertions
  resolve their relative paths against
- **Per-step screens** — the `steps` argument, one `StepResult` per step that
  ran, in order, each carrying the screen captured after that step, as plain
  text. Opt in by declaring the parameter (see below).

The following are **NOT** available and must not be relied upon:

- **Run directory** — no filesystem path to the current run's artifacts
- **Elapsed time / duration** — `RunResult.duration_seconds` is computed after
  assertions complete; it cannot be read during evaluation
- **result.json** — written after assertions finish; scanning for it will find
  stale prior runs at best, nothing at worst
- **Accumulated raw output** — assertion receives the final raw output, not
  the incremental stream
- **Attributes on the final screen** — the `screen` argument is flattened text,
  and there is no attributed form of it available to an assertion. Per-step
  screens are the exception: `StepResult.screen_attributed` carries the grid
  when the session reported one, and is `None` when it did not, so an assertion
  that reads it must handle both

Plugin authors should not attempt filesystem-based workarounds. To enforce
timing constraints, use TermProof core features (e.g. recipe-level
`timeout_seconds`).

### Opting into per-step screens

An assertion whose subject is a state the target passes through and then leaves
— a dialog that was dismissed, a screen that was shown mid-flow — cannot read it
off the final screen. Declare a `steps` parameter and TermProof passes the
per-step screens:

```python
def evaluate(
    self, recipe, assertion, screen, raw_output, exit_code, *, steps=None
) -> AssertionResult:
    match = next((s for s in steps or [] if s.name == assertion["step"]), None)
```

Rules worth knowing:

- **Declaring `steps` is the whole opt-in.** An assertion that does not declare
  it is called with the original five arguments, exactly as before, and needs no
  source change.
- **`**kwargs` alone does not opt in.** An assertion that forwards unrecognised
  arguments to another assertion would otherwise pass `steps` into one that
  cannot accept it.
- **Give `steps` a default of `None`.** Then the same assertion also runs on a
  TermProof that predates the argument.
- **`None` is not the same as `[]`.** `None` means the execution mode supplied
  no per-step screens — report that rather than treating it as a run with no
  steps. The built-in scripted modes always supply them; the agent-driven mode
  produces its assertions from the agent's own report and does not go through
  the assertion registry at all.
- **`StepResult.name` is what `step` matches**: the recipe step's `name` when it
  sets one, and `"<index>:<action>"` when it does not.
- Steps after a failing step do not run, so they are absent from the list.

`StepScreenMatches` in `src/termproof_my_plugin/step_assertions.py` is a worked
example; `ScreenCount` in `src/termproof_my_plugin/assertions.py` is deliberately
left on the original signature to show the two coexisting in one plugin.

## Version and deprecation policy

- Plugin declares `termproof>=0.2.1` in dependencies when using the stable `termproof.protocols` imports.
- Additive changes are allowed when existing plugins keep working without source changes.
- Breaking protocol changes require a major version bump and migration guide.
- Deprecated protocol behavior remains available for at least one minor release after documentation.

## Legacy prefix

TermProof understands legacy tui_verifier.*:Class References and remaps them to termproof.*:Class at load time. Plugins registering new names do not need to handle legacy prefix, but should document compatibility >=0.1.0.
