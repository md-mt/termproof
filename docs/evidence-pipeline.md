# Evidence Artifact Pipeline

## Principle

> Scripted PTY and process runs record a real terminal session as an asciinema cast (`session.cast`). Non-recorded agent mode (`record_terminal=False`) runs the operator via `subprocess` and synthesizes a cast from transcript via `CastRecorder`.

- For terminal-recorded runs (scripted modes and recorded agent mode), final text/SVG/video are cast replays — `TerminalSession` creates a cast via `TerminalSession` / asciinema. For non-recorded agent mode, the cast is synthesized by `CastRecorder` from the agent transcript, not from a real terminal.
- When a cast exists, terminal-derived display artifacts use the cast as source: final text/SVG are reconstructed via `replay_cast()` (pyte) from the cast; video is rendered by `render_mp4()` calling `agg` directly on the cast then `ffmpeg`. Other artifacts/results (assertions, filesystem checks, exit status, agent outcomes) have independent inputs.
- `steps/` renders every `StepResult` — including PTY, process (`wait_for_text`/`sleep`), and agent synthetic (`codex-operator`) steps — from stored `StepResult.screen` snapshots, not cast replay.
- `result.json`/`report.md` include independently evaluated `AssertionResult`s (including values reported by the agent's checks), synthetic operator step/exit status, and paths to agent artifacts as represented by `RunResult` — not the full agent outcome payload. The full `AgentOutcome` is serialized only in `agent_outcome.json`; these inputs remain independent of cast-derived data.
- Agent metadata files do not derive from the cast. `AgentDrivenRunner.run()` writes `agent_prompt.md` before invoking the runner; `_write_agent_files()` writes `agent_transcript.md` and `agent_outcome.json`. None of these files is derived from the cast.

The earlier claim "the cast is the source of truth, all other artifacts derive from it" was overbroad; scoped above to replayed terminal-derived display artifacts.

## Run Directory Creation

`evidence.new_run_dir(base_dir, recipe_name, renderer)`:

```python
def new_run_dir(base_dir, recipe_name, renderer="default"):
    safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in recipe_name)
    safe_renderer = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in renderer)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")  # microsecond precision
    return base_dir / f"{timestamp}-{safe_name}-{safe_renderer}"
```

Base dir is hardcoded in CLI at `cli.py:21` as `.tui-verifier/runs` and in runner at `runner.py:154-163` as `Path(".tui-verifier/runs")` — not read from `VerifierConfig.defaults.out_dir` (see `configuration.md`). The caller mkdirs it.

## Session Recording

### TerminalSession Recording Path

`session.TerminalSession.__enter__()`:

1. `mkdir -p cast_path.parent`, unlink old `cast_path` and `exit_code_path`.
2. `asciinema_rec_command(argv, cast_path, exit_code_path, cols, rows)`:
   - `shutil.which("asciinema")` — raises `RuntimeError("asciinema CLI is required...")` if missing.
   - Returns list: `[asciinema, rec, --overwrite, --stdin, --quiet, --cols, COLS, --rows, ROWS, --command, recorded_command(...), str(cast_path)]`.
3. `recorded_command(argv, exit_code_path)`:

```python
def recorded_command(argv, exit_code_path):
    target = shlex.join(argv)
    exit_file = shlex.quote(str(exit_code_path.resolve()))
    return f"{target}; __tui_verifier_status=$?; printf '%s' \"$__tui_verifier_status\" > {exit_file}; exit \"$__tui_verifier_status\""
```

Wraps target to capture exit code reliably to sidecar file (since asciinema itself may exit with its own code).

4. `pexpect.spawn(command[0], command[1:], cwd=cwd, env=merged_env, dimensions=(rows,cols), encoding="utf-8", codec_errors="replace")`
   - Merged env: `os.environ.copy()` into `merged_env`, then if `TERM` missing or `dumb` sets `xterm-256color` on `merged_env`; finally `merged_env.update(recipe_env)` overlays recipe env — so inherited `TERM` is normalized before recipe `env` overlay can override it.
5. Returns `self` — caller drives via methods.

### Session Driving

- `send_text(text)` → `child.send(text)`
- `send_line(text)` → `send_text(text+"\r")`
- `press(key)` — if `startswith "ctrl-"`, `child.sendcontrol(suffix)`; else `KEYS[lower]`.
- `read_available(timeout)` — loops `child.read_nonblocking(4096, timeout)`, handles `TIMEOUT` → return, `EOF` → collect exit code, `ValueError` → return. Appends to `raw_output` (str), feeds `pyte.Stream`.
- `screen` property → `screen_text(_screen)` — `"\n".join(line.rstrip())` trimmed trailing empty lines.
- `wait_for_text(text, timeout)` — deadline loop `time.monotonic()+timeout`, polls `read_available(0.05)`, checks `text in screen or text in raw_output`, returns on match or process exit.
- `wait_for_idle(stable, timeout)` — tracks last screen, resets stable_since on change, returns when screen unchanged for `stable` seconds.
- `wait_for_exit(timeout)` — polls until `not is_alive()` then `_collect_exit_code()`.
- `_collect_exit_code()` — if `exit_code` already set, return; else `child.close()`, try `_read_recorded_exit_code()` (read exit_code_path sidecar), else `child.exitstatus` (int), else `128+signal` if signal.
- `close()` — `read_available(0)`, force `child.close(force=True)` if alive, collect exit code.

### Agent Mode Recording

When `record_terminal=True`, `CodexCliAgentRunner._run_recorded()` at `agent_driven.py:56-85` directly constructs `TerminalSession(...)` (not `session_backend.create_session(...)`), so it bypasses the configured `config.session_backend`.

When `record_terminal=False`, `CodexCliAgentRunner._run_subprocess()` at `agent_driven.py:87-131` calls `subprocess.run()` directly and also bypasses `config.session_backend`. In this non-recorded subprocess path only, the explicit `TimeoutExpired` catch returns an `AgentOutcome` with `exit_code=None` and `metadata.timed_out=True`, while the explicit `FileNotFoundError` catch returns one with `exit_code=127`; recorded mode has neither catch.

Both built-in Codex paths (recorded and non-recorded) bypass `config.session_backend`.

When cast does not exist (non-recorded agent path), `AgentDrivenRunner` fallback:

```python
with CastRecorder(cast_path, recipe.cols, recipe.rows, ["codex-operator", recipe.name]) as recorder:
    recorder.output(outcome.transcript)
```

`CastRecorder` (`cast.py`) writes:

- Header line: JSON object `{version:2, width, height, timestamp:int(time.time()), command:" ".join(command), env:{SHELL, TERM}}`.
- Events: `[round(monotonic-start,6), kind, data]` where kind `"o"` output, `"i"` input.

This fallback applies whenever `run_dir/session.cast` does not exist after agent execution — including custom `AgentRunner` outcomes — not only a built-in non-recorded path or cast missing from `TerminalSession`. See `extension-points.md`.

## Artifact Rendering

`evidence.render_artifacts(run_dir, render_video, video_fps, steps?, cols?, rows?, screen_renderer?, video_backend?) -> dict[str,str]`

1. `replay_cast(cast_path)` → `(final_text, cols, rows)`:
   - Reads cast header for width/height.
   - `pyte.Screen(cols, rows)`, `pyte.Stream(screen)`.
   - Feeds all events where `event[1]=="o"` via `stream.feed(event[2])`.
   - Returns `screen_text(screen), cols, rows`.

2. Writes `final.txt` = `final_text + "\n"`.

3. Renders final SVG — fixed `.svg` contract (see `configuration.md`):
   - If `screen_renderer is not None`: `screen_renderer.render(final_text, final_svg, cols, rows)` where `final_svg = run_dir / "final.svg"`
   - Else: `screen.render_svg(final_text, final_svg, cols, rows)` (standalone function with same layout: line_height 20, char_width 9, padding 18, width max(320, cols*9+36), height max(160, rows*20+36)).
   - Custom renderers receive `.svg` paths; PNG-via-PIL is invalid unless pipeline is forked.

4. Artifacts dict initialized: `{"cast": str(cast_path), "screenshot": str(final_svg), "screen_text": str(final_txt)}`. Note `screenshot` is always the `final.svg` path even if a custom renderer writes different content to that file.

5. If `session.exitcode` exists, adds `"exit_code_file": str(path)`.

6. ` _render_step_screens(run_dir, steps, cols, rows, screen_renderer)`:
   - If no steps: returns None.
   - Creates `run_dir / "steps"` dir.
   - For each StepResult — every StepResult including PTY, process (`wait_for_text`/`sleep`), and agent synthetic (`codex-operator`) steps, not PTY-only — safe-name sanitized, writes `{index:02d}-{safe}.txt` = `screen+"\n"` and `{index:02d}-{safe}.svg` (not `{index}.svg`) via screen_renderer or `render_svg()` — filename is `path_base.with_suffix(".svg")` where `path_base = step_dir / f"{index:02d}-{safe}"`.
   - Returns step_dir Path; caller adds `"step_screenshots": str(step_dir)`.

7. For agent files: if `run_dir / name` exists for `agent_prompt.md`, `agent_transcript.md`, `agent_outcome.json`, adds stripped stem to artifacts (`agent_prompt`, `agent_transcript`, `agent_outcome` keys).

8. If `render_video and shutil.which("agg")`:
   - `mp4_path = run_dir / "session.mp4"`
   - If `video_backend is not None`: `video_backend.render(cast_path, mp4_path, video_fps)`
   - Else: `render_mp4(cast_path, mp4_path, video_fps)`
   - Adds `"video": str(mp4_path)`.

   The `shutil.which("agg")` guard is independent of session backend — custom session backend cannot avoid it.

### Video Rendering

`evidence.render_mp4(cast_path, mp4_path, fps=60)`:

```python
def render_mp4(cast_path, mp4_path, fps=60):
    gif_path = mp4_path.with_suffix(".agg.gif")  # e.g., session.agg.gif
    try:
        subprocess.run(["agg", "--quiet", "--fps-cap", str(fps), str(cast_path), str(gif_path)], check=True)
        ffmpeg = find_ffmpeg()
        subprocess.run([
            ffmpeg, "-y", "-loglevel", "error", "-i", str(gif_path),
            "-vf", f"fps={fps},scale=trunc(iw/2)*2:trunc(ih/2)*2",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            str(mp4_path)
        ], check=True)
    finally:
        gif_path.unlink(missing_ok=True)
```

`find_ffmpeg()`:

```python
def find_ffmpeg():
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg: return ffmpeg
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()
```

- Requires `agg` on PATH for video path; silently skipped if `agg` missing (guard in `render_artifacts` via `shutil.which("agg")`).
- Intermediate `.agg.gif` always cleaned up in `finally` — it is **not** a post-run artifact (the prior doc listed `session.agg.gif` as part of artifact tree, but `evidence.py:87-121` deletes it).
- Target MP4 uses even-width scaling `trunc(iw/2)*2`, yuv420p, faststart for web.

`AggFfmpegBackend.render()` (`builtin_video.py`) simply delegates to `evidence.render_mp4()`.

## Result Files

`evidence.write_result_files(run_dir, result)`:

- `(run_dir / "result.json").write_text(json.dumps(result.to_dict(), indent=2)+"\n")`
- `(run_dir / "report.md").write_text(render_report(result))`

`RunResult.to_dict()` includes: recipe_name, passed, exit_code, duration_seconds, priority, execution, renderer, score, steps (list of `__dict__`), assertions (list of `__dict__`), artifacts.

`evidence.render_report(result)` (per-run report):

```
# TUI Verification - PASS|FAIL

- Recipe: `name`
- Renderer: `renderer`
- Priority: `P`
- Execution: `scripted`
- Score: 1.00
- Exit code: `0`
- Duration: 2.34s

## Artifacts
- cast: `...`
- screenshot: `...`
...

## Assertions
- PASS `name` - detail

## Steps
- PASS `name` - detail
```

Aggregated report written by CLI:

- `BuildInfo.from_command(recipes[0].command.argv)` if recipes non-empty — probes binary via `which`, version via `--version`, git commit via `git rev-parse HEAD`, timestamp now.
- `reporter = runner.reporter_registry.get(--reporter)` default `markdown`
- `report = reporter.generate(results, build_info=build_info)` → markdown table `| Recipe | Renderer | Priority | Execution | Result | Score | Evidence |` with evidence links `[screenshot](path)` etc., plus per-result `<details><summary>`.
- Writes `out_dir / "latest-report.md"`.

## Full Artifact Tree

For a single recipe run with --video (when `agg` present):

```
.tui-verifier/runs/20260725-120000-123456-my-recipe-default/
├── session.cast                 # asciinema v2
├── session.exitcode             # sidecar exit code file (if recorded)
├── final.txt                    # replayed final screen text
├── final.svg                    # final screenshot via SvgRenderer
├── session.mp4                  # rendered via agg+ffmpeg (if --video + agg present)
├── result.json                  # RunResult.to_dict()
├── report.md                    # per-run evidence.render_report()
├── agent_prompt.md              # if agent-driven
├── agent_transcript.md          # if agent-driven
├── agent_outcome.json           # if agent-driven
└── steps/                       # if steps present — renders every StepResult (PTY, process, agent synthetic), not PTY-only; stored screen snapshots, not cast replay
    ├── 01-wait-for-prompt.txt
    ├── 01-wait-for-prompt.svg
    ├── 02-open-dashboard.txt
    ├── 02-open-dashboard.svg
    └── ...
```

`session.agg.gif` is **not** a post-run artifact — it is deleted in `finally` at `evidence.py:87-121`. Step screenshots are named `{index:02d}-{safe}.svg`, not `{index}.svg`.

For multi-recipe run, `out_dir/latest-report.md` aggregates all results.

## CI Artifacts

- CI workflow (`ci.yml`) runs with `--out .tui-verifier/ci`, uploads entire `.tui-verifier/ci` as artifact `tui-verifier-ci-evidence`.
- Release workflow runs on a `v*` tag push or manual dispatch. It uploads `.tui-verifier/release` as an artifact and tars it to `tui-verifier-release-evidence.tgz`; GitHub Release creation/archive attachment is gated by `startsWith(github.ref, 'refs/tags/v')`, so a manual dispatch on a matching v-tag ref also qualifies. Generated evidence paths include the output prefix, are not report-relative, and do not resolve inside embedded Markdown or archive members; users must download/extract the full artifact/archive. Release tar members are stored under `release/...`.

## Cast Format Notes

- v2 format: first line JSON header, subsequent lines `[float_timestamp, "o"|"i", data]` JSON arrays.
- `replay_cast()` only feeds `"o"` (output) events — input events are ignored for screen replay (they originate from tester, not TUI).
- Same cast file is used by `replay_cast()` for final text/SVG rendering and by `agg` directly for video when present (`render_mp4` calls `agg` on cast then `ffmpeg`; `replay_cast` reconstructs text/screen for text/SVG).
