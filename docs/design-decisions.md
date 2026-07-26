# Design Decisions and Trade-offs

All claims below reference observable current code and explicit source locations.

## 1. Evidence-first, cast as source of truth (with nuances)
**Decision:** Every completed execution path is normalized to an asciinema v2 cast; terminal-recorded paths (scripted PTY, scripted process, recorded agent) create that cast through asciinema recording, while non-recorded agent mode synthesizes a cast from transcript.

- `session.py:asciinema_rec_command()` shells out to `asciinema rec --overwrite --stdin --quiet --cols/--rows --command <recorded_command> <cast_path>`.
- `recorded_command()` wraps target argv via `shlex.join` + writes exit code to sidecar file `<cast>.exitcode`.
- `screen.py:replay_cast()` feeds output events into `pyte.Screen`.
- `evidence.py:render_artifacts()` at `31-61` calls `replay_cast()` for final text, renders final SVG/TXT via SVG renderer or fallback; at `65-83` renders per-step screens from stored `StepResult.screen` snapshots (not from cast replay); at `31-61,65-83,133-167`, `runner.py:171-201,297-325`, `builtin_assertions.py:127-184`, `agent_driven.py:138-157,228-253` show that `result.json`/`report.md` include independently evaluated assertions, exit status, file-system checks, and agent outcome; agent metadata files (`agent_prompt.md`, etc.) do not derive from the cast.
- Non-recorded agent mode at `agent_driven.py:138-157` synthesizes a cast from transcript via `CastRecorder` rather than recording a real terminal.
- Configured session backend (`config.session_backend`) is the extension point for scripted PTY and process paths; the builtin `PexpectAsciinemaBackend` returns a `TerminalSession`. In contrast, both built-in Codex paths bypass it: recorded mode at `agent_driven.py:51-70` directly constructs `TerminalSession`, and non-recorded mode at `agent_driven.py:87-131` calls `subprocess.run()` directly.

So final.txt/final.svg/video are cast replays for recorded paths (video via `render_mp4` calling `agg` directly on the cast then `ffmpeg`; `replay_cast` reconstructs text/screen for text/SVG), but PTY step files render stored `StepResult.screen` snapshots; result/report include independent evaluations and file checks; agent metadata does not derive from the cast; non-recorded agent mode synthesizes a cast from transcript.

**Trade-off:** Requires external `asciinema` binary on PATH (`shutil.which("asciinema")` checked, `RuntimeError` if missing). Non-pty process mode still uses asciinema via `TerminalSession` — even non-interactive commands are cast-recorded. Overhead: cast file includes terminal escape sequences; replay via pyte approximates final screen (pyte not a full VT emulator, but sufficient for evidence).

## 2. pexpect + asciinema composition (vs asciinema only or custom PTY)

**Behavior:** `TerminalSession` spawns `asciinema rec ...` as subprocess via `pexpect.spawn()`, not directly PTY-forking target nor using asciinema lib.

- Pexpect gives controllable PTY with `read_nonblocking`, `send`, `sendcontrol`, `isalive`, `close`.
- asciinema records the session as side effect (its `--command` arg runs the wrapped target).
- Exit code capture via sidecar file (`printf '%s' "$?" > exitcode`) works around pexpect exitstatus unreliability when asciinema intermediate process exits.

**Trade-off:** Two-layer PTY: pexpect PTY → asciinema → target. Signal propagation and TERM handling have an extra process. Exit code file adds filesystem I/O. Alternative of pure asciinema lib would lack pexpect's expect/send affordances.

## 3. pyte for screen model (vs direct VT parser)

**Behavior:** Both runtime session and cast replay use `pyte.Screen` + `pyte.Stream`.

- Runtime: `TerminalSession._screen` is pyte.Screen, fed via `_stream.feed(chunk)` in `read_available()`.
- Replay: `screen.py:replay_cast()` creates new pyte.Screen, feeds output events.

**Trade-off:** pyte does not implement full xterm escapes; complex TUIs with alternate screen, mouse, or SGR beyond basic may render imperfectly. Same limitation exists both live and replay, so evidence self-consistent but maybe not pixel-identical to real terminal. Full fidelity would require richer VT emulator or headless terminal (bigger dep).

## 4. Generic `Registry[T]` with `module:ClassName` strings (vs entry_points)

**Behavior:** 7 registries built from `BUILTIN_DEFAULTS` dict of strings plus a separately resolved session backend; resolved at startup via `importlib.import_module`. `runner.py:124` calls `importlib.import_module(module_name)`, which executes plugin module top-level code, so import-time side effects are possible. This contradicts any claim of "no import-time side effects."

- No decorator registration, no pkg_resources scanning.
- Zero-arg factories (`lambda c=cls: c()`).
- Parameters read at call time from `step`/`assertion` dicts.

**Trade-off:** Stringly typed; typos surface only at import time (`ModuleNotFoundError`, `AttributeError`) not edit-time. Zero-arg constraint prevents constructor injection — must use per-call dicts. Plugin modules are executed on import, so top-level code runs and can have side effects.

## 5. Cascading config: builtin → user → project deep merge

**Behavior:** `config.py:load_config()` merges `BUILTIN_DEFAULTS` with optional YAML files at `~/.config/tui-verifier/config.yaml` and `.tui-verifier/config.yaml`. `_deep_merge` recurses dicts, replaces leaves.

**Trade-off:** Config YAML values are strings interpreted as import qualnames, not validated — invalid qualname surfaces later. Deep merge semantics for dicts: you can e.g., partially override `defaults.timeout_seconds` while preserving sibling keys because `_deep_merge` recurses. However for `steps` dict, you cannot remove a builtin step via config alone — you can only add or replace individual entries.

`defaults` is modeled but currently unused by CLI/runner — see `configuration.md`. CLI `--config` has a known bug where its argument is treated as project path rather than YAML file — see same doc.

## 6. Three execution modes resolved from `execution + pty` — Fixed 3 Names Only

**Behavior:** `_resolve_execution_mode_name(recipe)` at `runner.py:128-134`:

- `execution=="agent-driven"` → `agent_driven`
- `command.pty==True` → `scripted_pty`
- else → `scripted_process`

Only 3 fixed registry keys are ever returned. Adding a new execution mode name to the YAML config parses but is never routed to — you must override one of the 3 builtin keys or patch resolver.

Mode objects implement `execute(runner, recipe, run_dir)`.

- `ScriptedPtyMode` delegates to `runner._run_pty()` — drives session step-by-step, short-circuits on failure.
- `ScriptedProcessMode` delegates to `runner._run_process()` — waits for exit, then `_evaluate_output_steps()` post-hoc (only `wait_for_text` and `sleep` mean anything; other actions fail with "requires pty=true").
- `AgentDrivenMode` delegates to `runner._run_agent_driven()`.

**Trade-off:** `_run_process` reuses step syntax but semantics differ — e.g., `send_line` in process mode always fails, not ignored. Process mode hardcodes its meaning; PTY dispatch uses step registry; agent mode does not dispatch recipe steps at all. Video backend is separately gated on `agg` binary presence regardless of session backend (see `extension-points.md`).

## 7. Step loop short-circuits on first failure

In `_run_pty`, after each `StepResult`, if `passed==False`, loop `break`s. Remaining steps not executed. Score still computed from assertions; result `passed = all(steps.passed) and all(assertions.passed)` so single failed step fails overall.

**Trade-off:** Fail-fast prevents cascading errors; evidence shows screen at failure point. No full diagnostic run-through — you only see first failure.

## 8. Assertion list auto-augmented with expect_exit_code (scripted modes only)

`_evaluate_assertions()` copies `recipe.assertions` and appends `{"type":"exit_code","value":expect_exit_code}` if `expect_exit_code is not None`. This applies to scripted PTY and process modes only (`builtin_modes.py:23-66`). Agent mode never calls `_evaluate_assertions()` — `AgentDrivenMode` uses `_agent_assertions()` at `agent_driven.py:212-225`, which evaluates `recipe.checks` and agent-returned keys; `recipe.assertions` and `expect_exit_code` do not determine its assertions; synthetic operator step requires `exit_code==0` for its step pass, but assertions are agent-derived.

**Trade-off for scripted modes:** Double reporting if recipe also contains explicit `exit_code` assertion — you'd get two exit_code checks (custom one plus implicit). Score includes both.

## 9. Score = passed/total assertions

`score_from_assertions()` returns 1.0 if no assertions OR all passed, else `passed/total`. `RunResult.score` is float 0..1.

**Trade-off:** Steps not weighted in score — only assertions count. A run could have failing steps but (if assertions pass) still pass? No — `RunResult.passed` is `all(steps.passed) and all(assertions.passed)`, so steps can fail run even if score 1.0 from assertions. Score reflects assertion pass rate only.

## 10. Evidence rendering and renderer selection (observed duplication)

**Observed:**

- `screen.py` has standalone `render_svg()` function.
- `builtin_renderers.SvgRenderer` replicates SVG logic.
- `evidence.render_artifacts()` accepts `screen_renderer` optional; if None falls back to `screen.render_svg()`.
- Same for video: `evidence.render_mp4()` standalone; `AggFfmpegBackend.render()` delegates to it; `render_artifacts()` guards `shutil.which("agg")` before calling backend.
- `builtin_reporters.MarkdownReporter` contains generation logic; `report.py` defines `ReportGenerator` that independently defines its own generation logic with similar output shape; package `__init__.py:3-19` re-exports `ReportGenerator`.

**Trade-off:** Duplicate fallback implementations exist — `screen.py:render_svg()` plus `SvgRenderer`, `evidence.render_mp4()` plus `AggFfmpegBackend`, and `report.py:ReportGenerator` independently defines logic similar to `MarkdownReporter`. This ensures code paths without config still work via standalone functions. Note `MarkdownReporter` does not delegate to a shared implementation; `report.py` is not merely a legacy re-export — it independently defines its logic.

## 11. BuildInfo provenance via `which`, `--version`, `git rev-parse`

`BuildInfo.from_command(argv)`:

- `binary_path = shutil.which(argv[0])` — may be None.
- Version via `binary --version` subprocess, 5s timeout.
- Git commit via `git rev-parse HEAD` cwd.

`verify_provenance()`: installed mode requires binary_path, source requires git_commit.

**Trade-off:** Probes external commands. Could fail if binary is wrapper script that doesn't support `--version`. No cryptographic provenance (no Sigstore). `BuildInfo` stores and serializes a timestamp, but the built-in Markdown outputs from `MarkdownReporter` and `ReportGenerator` include mode, command, binary, version, and commit and omit that timestamp.

## 12. Before/After delta for behavioral comparison

`before_after.py` compares two result lists keyed by `(recipe_name, renderer)`. Status per key: PASS/FAIL/SKIP. Deltas reported when status differs.

Used by reporter if `BeforeAfterResult` supplied, though CLI currently does not wire before/after automatically (no `diff` subcommand in current CLI).

**Trade-off:** Extra module currently not exercised by main CLI path (no `diff` subcommand wired). But kept for programmatic use (`ReportGenerator.generate_markdown(..., before_after=...)`).

## 13. Recipe fields: checks vs assertions vs steps

- `steps` — imperative driving actions for scripted modes (PTY: via registry; process: hardcoded wait_for_text/sleep; agent: not dispatched).
- `assertions` — declarative evaluations after run (substr, file, exit_code) for scripted modes only; agent checks do not use assertion registry.
- `checks` — human-readable check names for agent-driven mode; `build_agent_prompt()` lists them; `_agent_assertions()` uses them to evaluate agent's reported dict.

Keeping both in Recipe allows same file to declare data for both execution styles, but at runtime they are mutually exclusive paths (see execution-flow doc).

## 14. Renderer argv extension for multi-frontend testing

`renderers` field `dict[str, list[str]]` where key is renderer name, value extra argv. `selected_renderers()` expands `--renderer all` into multiple RunResults. `_with_renderer_argv()` uses `dataclasses.replace` to append extra argv.

**Trade-off:** Renderer concept overloads for TUI frontend variants (opentui/ink/...) but naming "renderer" overlaps with screen renderer / video backend registries which are also called "renderer". Documented distinction: recipe.renderers = frontend variants; screen_renderers registry = SVG → file converter; video_backends = agg+ffmpeg.

## 15. Scaffold via `init` command

`write_recipe_pack(path, name, command, pty, priority, cols, rows, force)`:

- Writes `<safe-name>.recipe.json` with default steps (`wait_for_idle stable 0.75s`) and one assertion (`output_not_contains Traceback`), expect_exit_code None.
- Writes README.md if not existing.

**Trade-off:** Starter recipe is minimal — user must edit assertions/steps. But works as discovery test: running it immediately records evidence for whatever command, even if not yet interactive.

## 16. Packaging choice: hatchling + uv

`pyproject.toml`: build-backend hatchling, dependencies listed as `name>=version` lower bounds with no upper bounds (e.g., `asciinema>=2.4.0`), not pinned, allowing use in varied environments. `uv.lock` present for reproducible local dev but wheel not pin-transitive.

CI uses `uv run ...` for convenience but package does not require uv at runtime.

## 17. Test strategy: some tests spawn real processes and require asciinema

Tests are listed at `testing-ci-release.md` as 31 tests / 8 files. Several tests (`test_runner.py:14-39,41-64,82-97`) invoke `VerificationRunner`/session backend which checks and spawns the external `asciinema` CLI (`session.py:54-73,200-223`) and runs real Python child processes. `test_cli.py` and `test_scaffold.py` scaffold files on disk rather than constructing only `Recipe` via dataclass.

E2E tests live as example recipes (`examples/generic`, deterministic Pi-style fixtures). CI runs both unit tests and E2E verification — unit fast, E2E validates whole stack including asciinema recording.

## 18. Open Limitations (Verified)

- `agent_runner_registry` is built at `runner.py:94-99,150` but not wired to execution mode — only `CodexCliAgentRunner` used unless caller injects custom runner programmatically via `VerificationRunner(agent_runner=...)`.
- Custom execution mode names beyond 3 not routable via recipe `execution` field without resolver extension at `runner.py:128-134,169-170`.
- `session_backend` is single value, not multi — cannot run multiple session backends in same run.
- Video guard `shutil.which("agg")` in `render_artifacts()` at `evidence.py:55-60` means custom video backends won't run if agg missing, even if backend doesn't need agg. Custom session backend cannot avoid this guard.
- `--config` help at `cli.py:29-30` says "path to a tui-verifier config YAML file" but `_resolve_config` at `cli.py:116-123` treats arg as project path and appends `.tui-verifier/config.yaml`; supplied YAML file is not loaded; default user config at `config.py:99-105` still loads when `--config` given — see `configuration.md` known bug.
- Screen renderer receives fixed `.svg` paths (`final.svg`, `steps/{index:02d}-{safe}.svg`) at `evidence.py:34-43,76-83` — PNG-via-PIL pattern passing `output_path` expecting extension-based format inference is invalid.
- Process mode `_run_process` hardcodes step support to `wait_for_text` and `sleep`; other steps fail requiring PTY — see `runner.py:275-295`.
- Agent-driven non-recorded mode `_run_subprocess` at `agent_driven.py:88-131` bypasses session backend; only explicit `TimeoutExpired`/`FileNotFoundError` → exit 127 conversion exists in this non-recorded subprocess path, while recorded mode at `56-85` uses `TerminalSession` without those explicit catches — see `extension-points.md`.
- Compatibility: `create_session` return value (the session object) must be a context manager because runner uses `with ...create_session(...)` at `runner.py:222-229,247-254`; the backend object itself need not be a context manager — only the session it returns must be.
- `config.defaults` is modeled but currently unused — CLI hardcodes `--out`/`--video-fps` at `cli.py:21-24`, runner at `runner.py:154-163`, recipe at `models.py:31-34,82-108`.
