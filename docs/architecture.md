# Architecture and Component Boundaries

## Component Map

```
┌─────────────────────────────────────────────────────────────────┐
│ CLI (cli.py) — argparse, 3 subcommands: run / list / init       │
├─────────────────────────────────────────────────────────────────┤
│ Config (config.py) — BUILTIN_DEFAULTS + VerifierConfig + cascade│
├─────────────────────────────────────────────────────────────────┤
│ Registry (registry.py) — generic Registry[T] + recipe discovery │
├─────────────────────────────────────────────────────────────────┤
│ Runner (runner.py) — VerificationRunner orchestrator            │
│  ├─ builds 7 registries from VerifierConfig                    │
│  ├─ resolves session backend                                    │
│  ├─ maps recipe → execution mode                                │
│  └─ coordinates evidence rendering + result writing              │
├─────────────────────────────────────────────────────────────────┤
│ Execution Modes (builtin_modes.py) — 3 built-ins               │
│  ├─ ScriptedPtyMode  (command.pty=true)                         │
│  ├─ ScriptedProcessMode (command.pty=false)                    │
│  └─ AgentDrivenMode  (execution=agent-driven)                  │
├─────────────────────────────────────────────────────────────────┤
│ Session Layer                                                   │
│  ├─ Session Backend (builtin_session.py) → TerminalSession      │
│  ├─ TerminalSession (session.py) — pexpect + asciinema rec      │
│  ├─ CastRecorder (cast.py) — minimal cast writer, agent mode   │
│  └─ Screen (screen.py) — replay_cast(), render_svg()            │
├─────────────────────────────────────────────────────────────────┤
│ Step Actions (builtin_steps.py) — 6 built-ins                  │
│  └─ each executes against TerminalSession, returns StepResult  │
├─────────────────────────────────────────────────────────────────┤
│ Assertions (builtin_assertions.py) — 7 built-ins               │
│  └─ each evaluates (screen, raw_output, exit_code) → AssertionResult│
├─────────────────────────────────────────────────────────────────┤
│ Agent-Driven (agent_driven.py)                                  │
│  ├─ AgentRunner protocol + CodexCliAgentRunner                  │
│  └─ AgentDrivenRunner — prompt building, output parsing         │
├─────────────────────────────────────────────────────────────────┤
│ Evidence Pipeline (evidence.py)                                 │
│  ├─ new_run_dir() — timestamped run directory                   │
│  ├─ render_artifacts() — final + per-step SVG/TXT + optional MP4│
│  ├─ render_mp4() — agg + ffmpeg                                 │
│  └─ write_result_files() + render_report()                     │
├─────────────────────────────────────────────────────────────────┤
│ Reporting & Rendering                                           │
│  ├─ builtin_renderers.py — SvgRenderer                          │
│  ├─ builtin_reporters.py — MarkdownReporter + ReportGenerator   │
│  ├─ builtin_video.py — AggFfmpegBackend                         │
│  ├─ renderer.py — selected_renderers() (recipe renderers × CLI)  │
│  ├─ report.py — ReportGenerator (legacy re-export)             │
│  └─ build_info.py — BuildInfo provenance                        │
├─────────────────────────────────────────────────────────────────┤
│ Scaffolding (scaffold.py) — recipe pack creation                │
│ Deltas (before_after.py) — behavior diff                        │
└─────────────────────────────────────────────────────────────────┘
```

## Module-by-Module Boundaries

### `models.py`
Immutable dataclasses only (frozen=True):
- `CommandSpec(argv, cwd?, env={}, pty=True)` — what to launch
- `Recipe` — full recipe with `command`, `steps`, `assertions`, `renderers`, `checks`, `operator`, timeout/cols/rows, etc.
- `StepResult(name, passed, detail, screen)`
- `AssertionResult(name, passed, detail)`
- `RunResult(recipe_name, passed, exit_code, duration_seconds, priority, execution, renderer, score, steps, assertions, artifacts)` + `to_dict()`
- Helpers: `recipe_from_mapping()`, `load_recipe()`, `score_from_assertions()`, `_normalize_renderers()`

No I/O except `load_recipe()` reading JSON.

### `registry.py`
- `Registry[T]` — stores `Callable[[], T]` factories, `register(name, factory)`, `get(name)→T` (raises `KeyError` with available list), `names()→list[str]`.
- `find_recipe_files(paths)` — if path is dir, `rglob("*.recipe.json")` sorted; else literal file.
- `load_recipes(paths)` → list[Recipe]
- `select_recipes(recipes, priority?, names?)` — filters.

No config awareness; pure discovery.

### `session.py`
- `TerminalSession(argv, cast_path, cwd, env, cols, rows)` — context manager.
  - `__enter__` builds asciinema command via `asciinema_rec_command()` + `recorded_command()`, spawns via `pexpect.spawn()` with `dimensions=(rows, cols)`, `encoding="utf-8"`.
  - `KEYS` mapping for `enter`, `escape`, `tab`, `backspace`, `up`, `down`, `left`, `right`.
  - Methods: `send_text()`, `send_line(text+"\r")`, `press(key)` (handles `ctrl-` prefix), `send_eof()`, `set_echo()`, `wait_for_text(text, timeout)` polls `read_available(0.05)`, `wait_for_idle(stable, timeout)` tracks screen stability, `wait_for_exit(timeout)` polls until dead, `read_available()`, `is_alive()`, `close()`, `_collect_exit_code()` (checks recorded `.exitcode` file first, then pexpect exitstatus/signalstatus), `_read_recorded_exit_code()`.
- `asciinema_rec_command()` — checks `shutil.which("asciinema")`, raises if missing.
- `recorded_command()` — wraps target via `shlex.join` + stores exit code to `exit_code_path` via `printf`.

Responsibilities: launch + I/O + exit code only. Rendering lives in `screen.py` / `evidence.py`.

### `cast.py`
- `CastRecorder(path, cols, rows, command)` — context manager that writes JSON header then `[timestamp, kind, data]` lines. Methods `output(data)` → kind `"o"`, `input(data)` → kind `"i"`. Used by `agent_driven.py` when operator cast path does not exist from `TerminalSession`.

### `screen.py`
- `replay_cast(cast_path)` → `(text, cols, rows)` — reads header, creates `pyte.Screen(cols, rows)`, feeds all `"o"` events via `pyte.Stream`, returns `screen_text(screen)` + dims.
- `screen_text(screen)` — `"\n".join(display.rstrip())`, trims trailing empty lines.
- `render_svg(text, output_path, cols, rows)` — emits minimal SVG with monospace text, `line_height=20`, `char_width=9`, `padding=18`, background `#101418`, foreground `#e6edf3`.

### `config.py`
See `configuration.md` for full cascade; summary:
- `BUILTIN_DEFAULTS` — canonical mapping of every registry entry to `module:ClassName`.
- `GlobalDefaults(timeout_seconds, cols, rows, video_fps, out_dir)`
- `VerifierConfig(steps, assertions, agent_runners, execution_modes, reporters, screen_renderers, video_backends, session_backend, defaults)` — `builtin()` classmethod returns from `BUILTIN_DEFAULTS`.
- `load_config(project_path?, user_path?)` — deep merge builtin → user YAML → project YAML.
- `_from_mapping()`, `_load_yaml()`, `_deep_merge()` helpers.

### `runner.py`
The central orchestrator.

- Registry builders: `_build_step_registry()`, `_build_assertion_registry()`, `_build_reporter_registry()`, `_build_renderer_registry()`, `_build_execution_mode_registry()`, `_build_agent_runner_registry()`, `_build_video_backend_registry()` — each iterates config mapping, imports via `_import_class(qualname)` which requires `":"` separator, uses `importlib.import_module`.
- `_resolve_session_backend()` — imports `config.session_backend`.
- `_resolve_execution_mode_name(recipe)`:
  - `execution == "agent-driven"` → `"agent_driven"`
  - `command.pty == True` → `"scripted_pty"`
  - otherwise → `"scripted_process"`
- `VerificationRunner.__init__(agent_runner?, config?)`:
  - `config or VerifierConfig.builtin()`
  - Builds all 7 registries + resolves session backend.
- `run(recipe, out_dir, render_video, video_fps, renderer, renderer_argv, screen_renderer_name, video_backend_name)`:
  1. `_with_renderer_argv()` — if renderer_argv non-empty, replaces `recipe.command` with `replace(..., argv=[*old, *extra])`.
  2. `new_run_dir(out_dir, recipe.name, renderer)` → mkdir.
  3. Resolve execution mode, `mode = execution_mode_registry.get(name)`, `mode.execute(self, runnable_recipe, run_dir)` → `steps, assertions, raw_output, exit_code, screen`.
  4. `screen_renderer_registry.get`, `video_backend_registry.get`, `render_artifacts()` → artifacts dict.
  5. `score_from_assertions()` + pass/fail: `all(step.passed) and all(assertion.passed)`.
  6. `RunResult(...)`, `write_result_files()`, return.
- `_run_agent_driven()`, `_run_pty()`, `_run_process()`, `_run_step()`, `_evaluate_output_steps()`, `_evaluate_assertions()`, `_evaluate_assertion()` — see execution-flow doc.

### `builtin_modes.py`
Protocol `ExecutionMode(name, execute(runner, recipe, run_dir)→tuple)` + 3 implementations:
- `ScriptedPtyMode` — delegates to `runner._run_pty()` + `_evaluate_assertions()`.
- `ScriptedProcessMode` — delegates to `runner._run_process()` + `_evaluate_assertions()`.
- `AgentDrivenMode` — delegates to `runner._run_agent_driven()`.

### `builtin_steps.py`
Protocol `StepAction(name, execute(session, step, index)→StepResult)` + 6 impls:
- `WaitForText` — `step["text"]`, `timeout_seconds=10` default, `session.wait_for_text()`.
- `WaitForIdle` — `stable_seconds=0.5`, `timeout_seconds=10`, `session.wait_for_idle()`.
- `SendText` — `session.send_text(step["text"])`, always pass.
- `SendLine` — `session.send_line(step.get("text",""))`.
- `Press` — `session.press(step["key"])`.
- `Sleep` — `time.sleep(step.get("seconds",1))` + `read_available(0)`.

### `builtin_assertions.py`
Protocol `AssertionType(name, evaluate(recipe, assertion, screen, raw_output, exit_code)→AssertionResult)`.
- Helper `_contains(name, haystack, needle, should_contain, custom_detail?)` → AssertionResult.
- `_recipe_path(recipe, path)` — absolute passthrough, relative resolved against `recipe.command.cwd or "."`.
- `OutputContains`, `OutputNotContains` — operate on `raw_output`.
- `ScreenContains`, `ScreenNotContains` — operate on `screen`.
- `ExitCode` — `exit_code == value`.
- `FileExists` — `path.exists()`, detail = str(path).
- `FileContains` — reads file if exists, `_contains(file_text, value, True)`.

### `agent_driven.py`
- `AgentOutcome(assertions, transcript, raw_output, exit_code, metadata)` frozen.
- `AgentRunner` protocol: `run(recipe, prompt, run_dir)→AgentOutcome`.
- `CodexCliAgentRunner(command=["codex","exec"], timeout_seconds=180, prompt_mode="stdin", cwd?, env={}, record_terminal=True)`:
  - `from_recipe(cls, recipe)` — reads `recipe.operator` dict: `command`, `timeout_seconds`, `prompt_mode`, `cwd`, `env`, `record_terminal`.
  - `run(recipe, prompt, run_dir)`:
    - if `record_terminal`: `_run_recorded()` — builds command, if `prompt_mode == "arg"` appends prompt, if `"stdin"` writes `agent_prompt.md` then wraps command via `sh -lc "... < prompt_path"`. Enters `TerminalSession` with that command, `wait_for_exit(timeout_seconds)`, `parse_agent_output(raw_output)`.
    - else: `_run_subprocess()` — subprocess.run with env merge, handles TimeoutExpired → `_timeout_output()`, FileNotFoundError → exit 127.
- `AgentDrivenRunner(agent_runner).run(recipe, run_dir)` → orchestrates: `build_agent_prompt(recipe)` writes `agent_prompt.md`, calls agent_runner, `_write_agent_files()` writes `agent_transcript.md` + `agent_outcome.json`, `_screen_from_agent_cast()` replays cast or creates one via `CastRecorder`, returns steps/assertions/raw/screen.
- `build_agent_prompt(recipe)` — formats checks, target command via shlex.quote, recipe context JSON, instructs agent to return JSON schema `{"assertions":...,"transcript":...,"notes":...}`.
- `parse_agent_output(output)` → `(assertions, transcript, metadata)` — tries: stripped output, reversed lines, fenced ```json blocks, raw JSON object scan from `{`, picks first dict containing `"assertions"` or `"transcript"`, else first JSON dict.
- `_agent_assertions()` — for each `recipe.checks`, looks up outcome.assertions dict; also includes any extra keys agent returned.
- Helper functions: `_write_agent_files`, `_screen_from_agent_cast`, `_load_json`, `_timeout_output`.

### `builtin_renderers.py`
- `ScreenRenderer` protocol: `render(text, output_path, cols, rows)`.
- `SvgRenderer` — same SVG logic as `screen.render_svg` but via class.

### `builtin_reporters.py`
- `Reporter` protocol: `generate(results, build_info?, before_after?)→str`.
- `MarkdownReporter` — delegates to shared implementation (mirrors `report.py`): count passed, BuildInfo lines if present, before/after delta if present, markdown table `| Recipe | Renderer | Priority | Execution | Result | Score | Evidence |`, evidence = links to screenshot/video/cast/screen_text/step_screenshots if present in artifacts, per-result `<details><summary>` with assertions + steps.

### `builtin_video.py`
- `VideoBackend` protocol: `render(cast_path, output_path, fps)`.
- `AggFfmpegBackend` — calls `evidence.render_mp4()`.

### `builtin_session.py`
- `SessionBackend` protocol: `create_session(argv, cast_path, cwd, env, cols, rows)→TerminalSession`.
- `PexpectAsciinemaBackend` — returns `TerminalSession(...)`.

### `evidence.py`
See evidence-pipeline doc; summary above.

### `report.py`
Legacy `ReportGenerator` that duplicates `MarkdownReporter.generate` logic for direct import via `tui_verifier.report`.

### `renderer.py`
- `selected_renderers(recipe, selection)` — `recipe.renderers` defaults to `{"default":[]}`; if `selection in ("all","both")` returns all; elif `selection in renderers` returns that one; else raises `ValueError` with available list.

### `scaffold.py`
- `write_recipe_pack(path, name, command, pty, priority, cols, rows, force)` — mkdir, checks existence unless force, writes `f"{safe_name(name)}.recipe.json"` with default recipe (description, checks, renderers default, steps wait_for_idle, assertions output_not_contains Traceback, expect_exit_code None), writes README if missing. `_write_readme()`, `_safe_name()` helpers.

### `build_info.py`
- `BuildInfo(mode, command, binary_path, version, git_commit, timestamp)` frozen.
- `from_command(command, cwd?)` — `shutil.which(command[0])`, probes version via `binary --version`, git commit via `git rev-parse HEAD`.
- `verify_provenance()` — installed mode requires binary_path, source mode requires git_commit.
- `to_dict()`, helpers `_probe_version()`, `_git_commit()`.

### `before_after.py`
- `BehaviorDelta(recipe_name, renderer, before, after)` frozen.
- `BeforeAfterResult(before, after, deltas)` + `to_markdown()` — lists PASS→FAIL etc.
- `build_before_after(before, after)` + `compute_deltas()` — maps by `(recipe_name, renderer)`, compares `_status()` (PASS/FAIL/SKIP).

### `cli.py`
- `main(argv?)→int` — argparse with subparsers `run`, `list`, `init`.
- `run`: args recipes (Path+), --out default `.tui-verifier/runs`, --video, --no-video, --video-fps 60, --priority, --recipe-name append, --renderer default, --operator-command, --config Path, --reporter markdown, --screen-renderer svg, --video-backend agg_ffmpeg. Resolves config via `_resolve_config()`, loads+filters recipes, loops recipe×renderer via `selected_renderers()`, runs via `VerificationRunner(agent_runner, config)`, reports via reporter, writes `latest-report.md`, prints `passed/total`, per-result verdict, returns 0 if results and all passed else 1.
- `list`: filter + print tab-separated name/priority/execution/description.
- `init`: calls `write_recipe_pack()`, returns 1 on FileExistsError else 0.
- `_resolve_config(args)` — if `--config` given, calls `load_config(project_path=resolved_config, user_path=None)`; else `load_config()`.

## Dependency Flow

- `models` has no internal dependencies except stdlib dataclasses.
- `registry` depends on `models` only.
- `session` depends on `screen`.
- `config` has optional `yaml` dependency; raises RuntimeError if yaml missing and config file exists.
- `runner` depends on everything: config (for registries), session, screen, evidence, models, agent_driven, registry, and dynamically imported plugins.
- `evidence` depends on `screen` + `models`.
- `agent_driven` depends on `cast`, `screen`, `session`, `models`.
- CLI depends on `config`, `registry`, `renderer`, `runner`, `build_info`, `scaffold`, `agent_driven`.

This layering allows unit tests to construct `Recipe` directly and inject a custom `VerifierConfig` or mock `TerminalSession` without needing asciinema or real TUIs.
