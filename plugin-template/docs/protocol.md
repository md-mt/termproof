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

Assertions receive only the final state of the run. The following are **NOT**
available at assertion evaluation time and must not be relied upon:

- **Run directory** — no filesystem path to the current run's artifacts
- **Elapsed time / duration** — `RunResult.duration_seconds` is computed after
  assertions complete; it cannot be read during evaluation
- **result.json** — written after assertions finish; scanning for it will find
  stale prior runs at best, nothing at worst
- **Accumulated raw output** — assertion receives the final raw output, not
  the incremental stream

Plugin authors should not attempt filesystem-based workarounds. To enforce
timing constraints, use TermProof core features (e.g. recipe-level
`timeout_seconds`). For counting and content checks, the `screen` and
`raw_output` strings are the correct inputs.

## Version and deprecation policy

- Plugin declares `termproof>=0.2.1` in dependencies when using the stable `termproof.protocols` imports.
- Additive changes are allowed when existing plugins keep working without source changes.
- Breaking protocol changes require a major version bump and migration guide.
- Deprecated protocol behavior remains available for at least one minor release after documentation.

## Legacy prefix

TermProof understands legacy tui_verifier.*:Class References and remaps them to termproof.*:Class at load time. Plugins registering new names do not need to handle legacy prefix, but should document compatibility >=0.1.0.
