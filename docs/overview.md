# TUI Verifier — Engineering Overview

TUI Verifier is an evidence-first verification harness for terminal and TUI applications. Every run records a real terminal session as an **asciinema v2 cast** (`session.cast`). Screenshots, screen-text snapshots, per-step evidence, optional 60-fps MP4 video, `result.json`, and `report.md` are all derived from that single recording.

## Core Principle

> The cast is the source of truth. Reviewers inspect what happened instead of trusting a private terminal session.

The normal low-level pipeline is:

```bash
asciinema rec --overwrite --stdin --quiet --cols "$COLS" --rows "$ROWS" \
  --command "$TARGET_COMMAND" session.cast
cat session.exitcode
agg --quiet --fps-cap 60 session.cast session.agg.gif
ffmpeg -y -loglevel error -i session.agg.gif \
  -vf 'fps=60,scale=trunc(iw/2)*2:trunc(ih/2)*2' \
  -pix_fmt yuv420p -movflags +faststart session.mp4
```

In `tui_verifier` this is implemented by `TerminalSession` (`session.py`) which builds the asciinema command via `asciinema_rec_command()` and `recorded_command()`, and by `evidence.render_mp4()` which shells out to `agg` + `ffmpeg` (or `imageio-ffmpeg` fallback via `find_ffmpeg()`).

## Package Layout

```
tui_verifier/
  models.py            # Recipe, CommandSpec, StepResult, AssertionResult, RunResult
  registry.py          # Generic Registry[T] + recipe discovery (find/load/select)
  session.py           # TerminalSession (pexpect + asciinema)
  cast.py              # CastRecorder (lightweight writer) — also used by agent mode
  screen.py            # replay_cast() + render_svg() — cast → text/SVG
  config.py            # BUILTIN_DEFAULTS, VerifierConfig, load_config() cascade
  runner.py            # VerificationRunner — 7 registries + session backend, run()
  builtin_modes.py     # ScriptedPtyMode, ScriptedProcessMode, AgentDrivenMode
  builtin_steps.py     # 6 step actions
  builtin_assertions.py# 7 assertion evaluators
  agent_driven.py      # AgentRunner protocol, CodexCliAgentRunner, AgentDrivenRunner
  builtin_renderers.py # SvgRenderer
  builtin_reporters.py # MarkdownReporter
  builtin_video.py     # AggFfmpegBackend
  builtin_session.py   # PexpectAsciinemaBackend
  evidence.py          # new_run_dir(), render_artifacts(), write_result_files()
  report.py            # ReportGenerator (duplicate of builtin_reporters for legacy import)
  renderer.py          # selected_renderers() — picks renderer(s) for a recipe
  scaffold.py          # write_recipe_pack() — init command
  build_info.py        # BuildInfo provenance
  before_after.py      # Before/After delta comparison
  cli.py               # Argument parsing + orchestration (run/list/init)
  __init__.py          # Public API surface
```

## Public API

Re-exported from `tui_verifier/__init__.py`:

- `VerifierConfig`, `load_config`
- `Recipe`, `RunResult`, `StepResult`, `AssertionResult`
- `Registry`
- `ReportGenerator`
- `VerificationRunner`, `load_recipe`

## Ten-Second Mental Model

1. Recipes are JSON files (`*.recipe.json`) describing a TUI to exercise.
2. Discovery is recursive — `examples/` and `.tui-verifier/recipes/` both work.
3. Config cascades: builtin → `~/.config/tui-verifier/config.yaml` → `.tui-verifier/config.yaml` → CLI `--config`.
4. `VerificationRunner` builds 7 registries from the merged config; every extension point is a `module:ClassName` string resolved via `importlib`.
5. For each recipe × renderer combination, the runner resolves an execution mode (`agent_driven`, `scripted_pty`, `scripted_process`) and executes steps via `TerminalSession`.
6. Evidence is rendered from the cast, scored, written as `result.json` / `report.md`, and aggregated into `latest-report.md`.

See the individual docs for deeper dives.
