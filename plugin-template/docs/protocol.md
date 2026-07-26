# Protocol compatibility

## Current protocols (TermProof >=0.1.0)

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

Each protocol requires a name class attribute and a single method:

- Step: execute(session, step, index) -> StepResult
- Assertion: evaluate(recipe, assertion, screen, raw_output, exit_code) -> AssertionResult
- Reporter: generate(results, build_info, before_after) -> str
- ScreenRenderer: render(text, output_path, cols, rows) -> None
- VideoBackend: render(cast_path, output_path, fps) -> None
- SessionBackend: create_session(argv, cast_path, cwd, env, cols, rows) -> TerminalSession
- ExecutionMode: execute(runner, recipe, run_dir) -> (steps, assertions, raw_output, exit_code, screen)
- AgentRunner: run(recipe, prompt, run_dir) -> AgentOutcome

## Version policy

- Plugin declares termproof>=0.1.0 in dependencies.
- Breaking protocol changes will be accompanied by major version bump and noted in issue 32.

## Legacy prefix

TermProof understands legacy tui_verifier.*:Class References and remaps them to termproof.*:Class at load time. Plugins registering new names do not need to handle legacy prefix, but should document compatibility >=0.1.0.
