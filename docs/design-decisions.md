# Design Decisions and Trade-offs

All claims grounded in current code.

## 1. Evidence-first, cast as source of truth

**Decision:** Every run records asciinema v2 cast via `asciinema rec` wrapper; all other evidence (final SVG/TXT, per-step screenshots, optional MP4) is derived by replaying the cast.

- `session.py:asciinema_rec_command()` shells out to `asciinema rec --overwrite --stdin --quiet --cols/--rows --command <recorded_command> <cast_path>`.
- `recorded_command()` wraps target argv via `shlex.join` + writes exit code to sidecar file `<cast>.exitcode`.
- `screen.py:replay_cast()` feeds output events into `pyte.Screen`.
- `evidence.py:render_artifacts()` calls `replay_cast()` for final text + per-step screens.

**Why:** Reviewers can inspect actual terminal output (cast JSON is trivial to cat or `asciinema cat`) rather than trust logs from inside tested process. Cast replays deterministically.

**Trade-off:** Requires external `asciinema` binary on PATH (`shutil.which("asciinema")` checked, `RuntimeError` if missing). Non-pty process mode still uses asciinema via `TerminalSession` — even non-interactive commands are cast-recorded. Overhead: cast file includes terminal escape sequences; replay via pyte approximates final screen (pyte not a full VT emulator, but sufficient for evidence).

## 2. pexpect + asciinema composition (vs asciinema only or custom PTY)

**Decision:** `TerminalSession` spawns `asciinema rec ...` as subprocess via `pexpect.spawn()`, not directly PTY-forking target nor using asciinema lib.

- Pexpect gives controllable PTY with `read_nonblocking`, `send`, `sendcontrol`, `isalive`, `close`.
- asciinema records the session as side effect (its `--command` arg runs the wrapped target).
- Exit code capture via sidecar file (`printf '%s' "$?" > exitcode`) works around pexpect exitstatus unreliability when asciinema intermediate process exits.

**Trade-off:** Two-layer PTY: pexpect PTY → asciinema → target. Means signal propagation and TERM handling have an extra process. Exit code file helps but adds filesystem I/O. Alternative of pure asciinema lib would lack pexpect's expect/send affordances.

## 3. pyte for screen model (vs direct VT parser)

**Decision:** Both runtime session and cast replay use `pyte.Screen` + `pyte.Stream`.

- Runtime: `TerminalSession._screen` is pyte.Screen, fed via `_stream.feed(chunk)` in `read_available()`.
- Replay: `screen.py:replay_cast()` creates new pyte.Screen, feeds output events.

**Why:** pyte is lightweight, pure Python, std API, in dependencies (`pyte>=0.8.2`).

**Trade-off:** pyte does not implement full xterm escapes; complex TUIs with alternate screen, mouse, or SGR beyond basic may render imperfectly. Same limitation exists both live and replay, so evidence self-consistent but maybe not pixel-identical to real terminal. Full fidelity would require richer VT emulator or headless terminal (bigger dep).

## 4. Generic `Registry[T]` with `module:ClassName` strings (vs entry_points)

**Decision:** 7 registries built from `BUILTIN_DEFAULTS` dict of strings; resolved at startup via `importlib.import_module`.

- No decorator registration, no pkg_resources scanning.
- Zero-arg factories (`lambda c=cls: c()`).
- Parameters read at call time from `step`/`assertion` dicts.

**Why:** Simple, debuggable, no import-time side effects; config file alone can wire custom implementations.

**Trade-off:** Stringly typed; typos surface only at import time (`ModuleNotFoundError`, `AttributeError`) not edit-time. Zero-arg constraint prevents constructor injection — must use per-call dicts. Alternative decorator-based registration would auto-discover but require import side-effect.

## 5. Cascading config: builtin → user → project deep merge

**Decision:** `config.py:load_config()` merges `BUILTIN_DEFAULTS` with optional YAML files at `~/.config/tui-verifier/config.yaml` and `.tui-verifier/config.yaml`. `_deep_merge` recurses dicts, replaces leaves.

**Why:** Mirrors familiar tool config cascade (think git, npm). Lets plugin authoring happen via YAML without code changes; user can override per-project.

**Trade-off:** Config YAML values are strings interpreted as import qualnames, not validated — invalid qualname surfaces later. Deep merge semantics for dicts is fine for most cases, but leaf replacement means you cannot e.g., partially override only `defaults.timeout_seconds` without preserving sibling keys? Actually you can — because `_deep_merge` recurses, so `defaults: {timeout_seconds: 60}` merges preserving other defaults keys. That's correct. However for `steps` dict, you cannot remove a builtin step via config alone — you can only add or replace individual entries. To remove you'd need to set value to something invalid or edit code.

`--config` flag in CLI help says "path to a tui-verifier config YAML file" but implementation treats it as project_path base (`Path / .tui-verifier / config.yaml`). This is a minor doc-vs-code gap; documented accurately elsewhere.

## 6. Three execution modes resolved from `execution + pty`

**Decision:** `_resolve_execution_mode_name(recipe)`:

- `execution=="agent-driven"` → `agent_driven`
- `command.pty==True` → `scripted_pty`
- else → `scripted_process`

Mode objects implement `execute(runner, recipe, run_dir)`.

- `ScriptedPtyMode` delegates to `runner._run_pty()` — drives session step-by-step, short-circuits on failure.
- `ScriptedProcessMode` delegates to `runner._run_process()` — waits for exit, then `_evaluate_output_steps()` post-hoc (only `wait_for_text` and `sleep` mean anything; other actions fail with "requires pty=true").
- `AgentDrivenMode` delegates to `runner._run_agent_driven()`.

**Trade-off:** `_run_process` reuses step syntax but semantics differ — e.g., `send_line` in process mode always fails, not ignored. This lets a recipe declare expectations uniformly but may surprise: a recipe that works in PTY mode (with send_line steps) will fail if switched to `pty:false` unless steps rewritten to only wait_for_text/sleep. The design intentionally keeps same evaluator structure while documenting difference.

## 7. Step loop short-circuits on first failure

In `_run_pty`, after each `StepResult`, if `passed==False`, loop `break`s. Remaining steps not executed. Score still computed from assertions; result `passed = all(steps.passed) and all(assertions.passed)` so single failed step fails overall.

**Why:** Fail-fast prevents cascading errors; evidence shows screen at failure point.

**Trade-off:** No full diagnostic run-through — you only see first failure. To see later steps you must fix earlier ones.

## 8. Assertion list auto-augmented with expect_exit_code

`_evaluate_assertions()` copies `recipe.assertions` and appends `{"type":"exit_code","value":expect_exit_code}` if `expect_exit_code is not None`. So setting `expect_exit_code` in recipe adds implicit assertion — doesn't require explicit assertion.

**Trade-off:** Double reporting if recipe also contains explicit `exit_code` assertion — you'd get two exit_code checks (custom one plus implicit). Score includes both.

## 9. Score = passed/total assertions

`score_from_assertions()` returns 1.0 if no assertions OR all passed, else `passed/total`. `RunResult.score` is float 0..1. Sorting by score in reports would be meaningful.

**Trade-off:** Steps not weighted in score — only assertions count. A run could have failing steps but (if assertions pass) still pass? No — `RunResult.passed` is `all(steps.passed) and all(assertions.passed)`, so steps can fail run even if score 1.0 from assertions. Score reflects assertion pass rate only.

## 10. Evidence rendering pluggable but defaults to standalone functions

Historical layering:

- `screen.py` has standalone `render_svg()` function.
- `builtin_renderers.SvgRenderer` replicates SVG logic.
- `evidence.render_artifacts()` accepts `screen_renderer` optional; if None falls back to `screen.render_svg()`.
- Same for video: `evidence.render_mp4()` standalone; `AggFfmpegBackend.render()` delegates to it; `render_artifacts()` guards `shutil.which("agg")` before calling backend.
- `builtin_reporters.MarkdownReporter` duplicates logic also present in `report.ReportGenerator`.

**Trade-off:** Duplication (DRY violation) from phased refactor (Phases 1-4 wired registries). But ensures backward compat: code path without config (None passed) still works because standalone functions exist as fallback.

## 11. BuildInfo provenance via `which`, `--version`, `git rev-parse`

`BuildInfo.from_command(argv)`:

- `binary_path = shutil.which(argv[0])` — may be None.
- Version via `binary --version` subprocess, 5s timeout.
- Git commit via `git rev-parse HEAD` cwd.

`verify_provenance()`: installed mode requires binary_path, source requires git_commit.

**Trade-off:** Very small — probes external commands. Could fail if binary is wrapper script that doesn't support `--version`. No cryptographic provenance (no Sigstore). But matches "evidence-first" principle: report includes mode, command, binary, version, commit, timestamp for audit.

## 12. Before/After delta for behavioral comparison

`before_after.py` compares two result lists keyed by `(recipe_name, renderer)`. Status per key: PASS/FAIL/SKIP. Deltas reported when status differs.

Used by reporter if `BeforeAfterResult` supplied, though CLI currently does not wire before/after automatically (reserve for future `tui-verify diff` command).

**Trade-off:** Extra module currently not exercised by main CLI path (no `diff` subcommand wired). But kept for programmatic use (`ReportGenerator.generate_markdown(..., before_after=...)`).

## 13. Recipe fields: checks vs assertions vs steps

- `steps` — imperative driving actions for scripted modes.
- `assertions` — declarative evaluations after run (substr, file, exit_code).
- `checks` — human-readable check names for agent-driven mode; `build_agent_prompt()` lists them; `_agent_assertions()` uses them to evaluate agent's reported dict.

**Why:** Scripted mode is deterministic action list; agent-driven mode is non-deterministic LLM that reports pass/fail per check — two different assertion styles. Keeping both in Recipe allows same recipe file to be used in both execution modes? Not fully — agent-driven recipes require `operator` config. But check names provide shared vocabulary.

## 14. Renderer argv extension for multi-frontend testing

`renderers` field `dict[str, list[str]]` where key is renderer name, value extra argv. `selected_renderers()` expands `--renderer all` into multiple RunResults with same recipe but different renderer name and argv. `_with_renderer_argv()` uses `dataclasses.replace` to append extra argv.

**Trade-off:** Renderer concept overloads for TUI frontend variants (opentui/ink/...) but naming "renderer" predates extension to frontend abstraction. Could cause confusion with screen renderer / video backend registries which are also called "renderer". Documented distinction: recipe.renderers = frontend variants; screen_renderers registry = SVG → file converter; video_backends = agg+ffmpeg.

## 15. Scaffold via `init` command

`write_recipe_pack(path, name, command, pty, priority, cols, rows, force)`:

- Writes `<safe-name>.recipe.json` with default steps (`wait_for_idle stable 0.75s`) and one assertion (`output_not_contains Traceback`), expect_exit_code None.
- Writes README.md if not existing.

**Trade-off:** Starter recipe is minimal — user must edit assertions/steps. But works as discovery test: running it immediately records evidence for whatever command, even if not yet interactive.

## 16. Packaging choice: hatchling + uv

`pyproject.toml`: build-backend hatchling, dependencies listed minimal, console script `tui-verify`. Dependencies upper-bounded by `>=`, not pinned, allowing use in varied environments. `uv.lock` present for reproducible local dev but wheel not pin-transitive.

CI uses `uv run ...` for convenience but package does not require uv at runtime.

## 17. Test strategy: unit tests with constructed recipes

Tests don't require asciinema, agg, ffmpeg, or real TUI processes — they construct `Recipe` dataclass directly, call `load_recipes`, `selected_renderers`, `BuildInfo.from_command([sys.executable, ...])`, `ReportGenerator.generate_markdown`, etc.

E2E tests live as example recipes (`examples/generic`, deterministic Pi-style fixtures). CI runs both unit tests and E2E verification — unit fast, E2E validates whole stack including asciinema recording.

## Open Limitations Noted

- `agent_runner_registry` is built but not wired to execution mode — only `CodexCliAgentRunner` used unless caller injects custom runner programmatically.
- Custom execution mode names beyond 3 not routable via recipe `execution` field without resolver extension (see plugin-authoring doc).
- `screen_backend`? Actually session_backend is single value, not multi — cannot run multiple session backends in same run.
- Video guard `shutil.which("agg")` in `render_artifacts` means custom video backends won't run if agg missing, even if backend doesn't need agg.
- `--config` help vs implementation minor divergence noted earlier.
