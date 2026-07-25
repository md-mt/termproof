# End-to-End Execution and Data Flow

## CLI Entry

`cli.main()` (`cli.py`) parses via argparse:

- `run` — `recipes: list[Path]` required, `--out Path(.tui-verifier/runs)`, `--video` flag, `--no-video`, `--video-fps 60` (configurable; 60 is default but not fixed), `--priority`, `--recipe-name` append, `--renderer default`, `--operator-command`, `--config Path` (known bug — treated as project path, not YAML file; see `configuration.md`), `--reporter markdown`, `--screen-renderer svg`, `--video-backend agg_ffmpeg`.
- `list` — `recipes`, `--priority`.
- `init` — `path: Path`, `--name` required, `--command` required, `--non-pty`, `--priority P2`, `--cols 100`, `--rows 30`, `--force`.

Return codes: `run` returns 0 only if results non-empty and all passed; else 1. With no selected recipes, `all([])` is true but CLI returns 1 (source: `cli.py:77-90`). `init` returns 1 on FileExistsError unless --force; 0 otherwise. List always 0.

## `run` Command Flow

```
cli.main()
  → _resolve_config(args)
      if --config: load_config(project_path=resolved --config, user_path=None)
        note: project_path is used as base for project_file = project_path / ".tui-verifier" / "config.yaml"
        so a file path is not loaded; passing a dir works despite help; default user config still loads
        because user_path=None falls back to default at config.py:99-105
      else:        load_config()  # cascade builtin → user → project
  → registry.load_recipes(args.recipes)
      → find_recipe_files() — per input: if dir then rglob("*.recipe.json") sorted else file
      → load_recipe() per file — json load + recipe_from_mapping()
  → registry.select_recipes(recipes, priority, recipe_names)
  → VerificationRunner(agent_runner?, config)
      → builds 7 registries + resolves single session backend from config
      → optional agent_runner from --operator-command (CodexCliAgentRunner with shlex.split(cmd))
  → for recipe in filtered_recipes:
      → for renderer_name, renderer_argv in selected_renderers(recipe, --renderer):
          → runner.run(recipe, out_dir, render_video=--video and not --no-video,
                        video_fps, renderer, renderer_argv,
                        screen_renderer_name, video_backend_name)

          Internal run() steps:
            1. _with_renderer_argv(recipe, renderer_argv)
               — if non-empty, returns replace(recipe, command=replace(command, argv=[*old, *extra]))
            2. new_run_dir(out_dir, recipe.name, renderer)
               — safe_name = alnum + -_ else - ; timestamp = YYYYMMDD-HHMMSS-micro
               — returns out_dir / f"{timestamp}-{safe_name}-{safe_renderer}"
               — mkdir -p
            3. _resolve_execution_mode_name(runnable_recipe)
               - "agent-driven" → "agent_driven"
               - command.pty true → "scripted_pty"  (still launches through session backend; builtin is pexpect+asciinema)
               - else → "scripted_process"          (also launches through session backend; same backend, different wait)
               Only 3 fixed names ever returned.
            4. mode = execution_mode_registry.get(mode_name); mode.execute(self, runnable_recipe, run_dir)
               → (steps, assertions, raw_output, exit_code, screen)
            5. screen_renderer = screen_renderer_registry.get(screen_renderer_name)  # source uses dedicated names, not mode name
               video_backend   = video_backend_registry.get(video_backend_name)
               Earlier pseudo-flow incorrectly used get(name) where prior name is execution mode; fixed to screen_renderer_name/video_backend_name per runner.py:169-185.
            6. render_artifacts(run_dir, render_video, video_fps, steps, cols, rows,
                                screen_renderer, video_backend) → artifacts dict
               Note: render_video && shutil.which("agg") gate at evidence.py:55-60
                     screen renderer receives fixed .svg paths (final.svg, steps/{index:02d}-{safe}.svg)
            7. score_from_assertions(assertions) — 1.0 if no assertions or all passed else passed/total
               passed = all(s.passed) and all(a.passed)
            8. RunResult(...) + write_result_files(run_dir, result)
               — result.json (to_dict with steps/assertions/artifacts)
               — report.md via evidence.render_report()
            9. return RunResult (collected in results list)  # runner.py:154-202 returns RunResult; mode.execute returns the 5-tuple internally

  → BuildInfo.from_command(recipes[0].command.argv) if any recipes
  → reporter = runner.reporter_registry.get(--reporter)
  → report = reporter.generate(results, build_info=build_info)
  → out_dir.mkdir -p; (out_dir / "latest-report.md").write_text(report)
  → print f"{passed}/{len(results)} passed" + report path + per-result VERDICT line
  → return 0 if results non-empty and all passed else 1
```

## Execution Mode Details

### `_run_pty()` — ScriptedPtyMode

```python
def _run_pty(recipe, run_dir):
    cast_path = run_dir / "session.cast"
    with session_backend.create_session(argv, cast_path, cwd, env, cols, rows) as session:
        for index, step in enumerate(recipe.steps, 1):
            step_result = _run_step(session, index, step)
            steps.append(step_result)
            if not step_result.passed: break
        if recipe.expect_exit_code is not None:
            session.wait_for_exit(recipe.timeout_seconds)
        else:
            session.wait_for_idle(0.5, min(3, recipe.timeout_seconds))
        return steps, session.raw_output, session.exit_code, session.screen
```

- Session context manager cleans up via `close()` + `_collect_exit_code()`. Note: compatible session must also be a context manager because runner uses `with ...create_session(...)` (runner.py:222-229,247-254); otherwise raises. This wait_for_idle vs wait_for_exit branch applies **only to PTY** (runner.py:235-238); process always wait_for_exit (241-260).
- Step loop short-circuits on first failure — remaining steps are not attempted.
- `wait_for_exit` vs `wait_for_idle` decision controlled by `expect_exit_code` in PTY only.

`_run_step(session, index, step)`:

```python
action_name = step["action"]
action = step_registry.get(action_name)  # KeyError → ValueError("unknown step action")
return action.execute(session, step, index)
```

PT̂Y mode dispatches through step registry. Process mode hardcodes `wait_for_text`/`sleep`; agent mode does not dispatch recipe steps.

### `_run_process()` — ScriptedProcessMode (Still Through Session Backend)

```python
def _run_process(recipe, run_dir):
    cast_path = run_dir / "session.cast"
    with session_backend.create_session(...) as session:
        session.wait_for_exit(recipe.timeout_seconds)
        raw_output = session.raw_output
        exit_code = session.exit_code
    screen, _, _ = replay_cast(cast_path)
    steps = _evaluate_output_steps(recipe, screen, raw_output)
    return steps, raw_output, exit_code, screen
```

Note: `command.pty=false` selects `ScriptedProcessMode` but still launches through configured session backend whose builtin is `TerminalSession` → pexpect + asciinema; there is still a PTY at implementation level.

`_evaluate_output_steps()` evaluates recipe steps post-hoc:

- `wait_for_text` → checks `text in screen or text in raw_output`.
- `sleep` → always pass with "not needed for process mode".
- All other actions → fail with `"{action!r} requires command.pty=true"`.

This allows process-mode recipes to declare expectations as steps without needing PTY interaction but only meaningfully for `wait_for_text`/`sleep`.

### `_run_agent_driven()` — AgentDrivenMode

```python
def _run_agent_driven(recipe, run_dir):
    if agent_runner is not None: agent = agent_runner
    else: agent = CodexCliAgentRunner.from_recipe(recipe)
    return AgentDrivenRunner(agent).run(recipe, run_dir)
```

Inside `AgentDrivenRunner.run()`:

1. `build_agent_prompt(recipe)` → formatted prompt with recipe JSON context + instruction to return `{"assertions": {...}, "transcript": "...", "notes": "..."}`.
2. `(run_dir / "agent_prompt.md").write_text(prompt)`.
3. `outcome = agent_runner.run(recipe, prompt, run_dir)` → `AgentOutcome`.
4. `_write_agent_files()` → `agent_transcript.md`, `agent_outcome.json`.
5. `_screen_from_agent_cast()` → if `session.cast` exists, `replay_cast()`; else `CastRecorder(...).output(transcript)` then replay — fallback applies whenever cast does not exist, including custom runners, not just built-in non-recorded path.
6. Single synthetic `StepResult(name="codex-operator", passed=exit_code==0, detail=f"operator exit code {exit_code}", screen=screen)`.
7. `_agent_assertions()` → for each check in `recipe.checks` (or default `["Codex operator completed the verification"]`), look up `outcome.assertions[check]`; also include any extra assertion keys agent returned. Does **not** call `_evaluate_assertions()`; `recipe.assertions` and `expect_exit_code` do not determine its assertions — `_agent_assertions()` uses checks/agent-returned keys, while synthetic operator step requires `exit_code==0`.

`CodexCliAgentRunner.run()` branching:

- `record_terminal=True` (default): delegates to `_run_recorded()` at `agent_driven.py:51-70`.
  - Builds command list; if `prompt_mode=="arg"` appends prompt; if `"stdin"` writes prompt to file then wraps via `sh -lc "cmd < prompt_path"`.
  - Enters `TerminalSession` with operator command, `wait_for_exit(timeout)`, parses output via `parse_agent_output(raw_output)`.
- `record_terminal=False`: `_run_subprocess()` at `agent_driven.py:87-131` — `subprocess.run()` with merged env, input = prompt (unless arg mode), stdout+stderr merged, timeout handling (returns outcome with `timed_out=True`), FileNotFoundError → exit 127. Recorded mode bypasses? No — recorded mode uses `TerminalSession`; non-recorded uses subprocess and bypasses session backend. Error handling only covers timeout/FileNotFoundError in non-recorded mode.

`parse_agent_output()` — JSON extraction cascade:
- Tries: stripped output, each reversed line, fenced ```json blocks, and raw object scan using `json.JSONDecoder().raw_decode(output[start:])` for each `{` position from end.
- Picks first dict containing `"assertions"` or `"transcript"`; else first dict at all.
- Returns `({}, output, {})` if nothing parsed.

## Assertion Evaluation (Scripted Modes Only)

After steps (PTY/process), `runner._evaluate_assertions()` is called for the two non-agent modes; agent mode already produced assertions via `_agent_assertions()` and never calls `_evaluate_assertions`:

```python
def _evaluate_assertions(recipe, screen, raw_output, exit_code):
    assertions = list(recipe.assertions)
    if recipe.expect_exit_code is not None:
        assertions.append({"type": "exit_code", "value": recipe.expect_exit_code})
    return [_evaluate_assertion(recipe, assertion, screen, raw_output, exit_code) for assertion in assertions]

def _evaluate_assertion(recipe, assertion, screen, raw_output, exit_code):
    kind = assertion["type"]
    evaluator = assertion_registry.get(kind)  # KeyError → ValueError
    return evaluator.evaluate(recipe, assertion, screen, raw_output, exit_code)
```

Note: `expect_exit_code` is injected as implicit `exit_code` assertion in addition to explicit ones — explicitly needs qualification that it does not apply to agent-driven mode.

## Scoring

`models.score_from_assertions(assertions)`:

```python
if not assertions: return 1.0
passed = sum(1 for a in assertions if a.passed)
return 1.0 if passed == len(assertions) else passed / len(assertions)
```

Overall `RunResult.passed = all(step.passed) and all(assertion.passed)`.

## Renderer Selection

`renderer.selected_renderers(recipe, selection)`:

```python
renderers = recipe.renderers or {"default": []}
if selection in ("all", "both"): return [(name, list(argv)) for name, argv in renderers.items()]
if selection in renderers: return [(selection, list(renderers[selection]))]
raise ValueError(f"unknown renderer {selection!r}; available: {available}")
```

Example recipe:

```json
"renderers": { "default": [], "opentui": [], "ink": ["--renderer", "ink"] }
```

- `--renderer default` runs `argv + []` → one `RunResult` with renderer `default`.
- `--renderer all` expands to all three entries in mapping order, including distinct `default` and `opentui` runs with identical argv when their argv lists are equal — e.g., declares `default`, `opentui`, `ink` but mapped as shown; `selected_renderers` returns all three, including default and opentui with identical argv. Earlier doc claimed `--renderer all` creates 2 runs — actual is all 3.
- `_with_renderer_argv()` handles the argv extension via `dataclasses.replace`.

Note: `VerificationRunner.run()` returns `RunResult`; `ExecutionMode.execute()` internally returns the 5-item tuple `(steps, assertions, raw_output, exit_code, screen)` — earlier data-flow diagram said `VerificationRunner.run` returns the five-item tuple; corrected.

## CLI `list` and `init`

- `list`: `load_recipes`, `select_recipes(priority)`, prints `f"{name}\t{priority}\t{execution}\t{description}"` per recipe.
- `init`: `scaffold.write_recipe_pack(path, name, target_command, pty, priority, cols, rows, force)` — details in extension-points and plugin-authoring.

## Data Structure Flow

```
Recipe files (.recipe.json)
  → recipe_from_mapping() → Recipe
  → VerificationRunner.run() → RunResult
    internally: ExecutionMode.execute() → (Steps, Assertions, RawOutput, ExitCode, Screen)
  → render_artifacts() → Artifacts dict (fixed .svg contract, agg gate)
  → RunResult.to_dict() → result.json
  → render_report() → report.md
  → MarkdownReporter.generate() → latest-report.md
```
