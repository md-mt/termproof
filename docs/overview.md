# TUI Verifier — Engineering Overview

TUI Verifier is an evidence-first verification harness for terminal and TUI applications. Every run records a real terminal session as an **asciinema v2 cast** (`session.cast`). Several artifacts are derived from that cast (final text, final SVG, optional MP4 via `agg`+`ffmpeg`), while others are not: per-step `steps/*.txt`/`*.svg` render stored `StepResult.screen` snapshots, `result.json`/`report.md` include independently evaluated assertions, exit status, file-system checks, and agent outcomes; agent metadata files (`agent_prompt.md`, etc.) are written separately and do not derive from the cast. Non-recorded agent mode synthesizes a cast from transcript rather than recording a real terminal.

Configurable video fps — `60` is only the CLI/runner default and `--video-fps` is configurable.

## Core Principle

> Record real terminal sessions; derive reviewable evidence. Reviewers inspect what happened.

The normal low-level pipeline for PTY mode is:

```bash
asciinema rec --overwrite --stdin --quiet --cols "$COLS" --rows "$ROWS" \
  --command "$TARGET_COMMAND" session.cast
cat session.exitcode
agg --quiet --fps-cap 60 session.cast session.agg.gif   # only if agg present + --video
ffmpeg -y -loglevel error -i session.agg.gif \
  -vf 'fps=60,scale=trunc(iw/2)*2:trunc(ih/2)*2' \
  -pix_fmt yuv420p -movflags +faststart session.mp4
```

In `tui_verifier` this is implemented by `TerminalSession` (`session.py`) which builds the asciinema command via `asciinema_rec_command()` and `recorded_command()`, and by `evidence.render_mp4()` which shells out to `agg` + `ffmpeg` (or `imageio-ffmpeg` fallback via `find_ffmpeg()`). Guard at `evidence.py:55-60` requires `shutil.which("agg")` before any video backend runs.

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
  builtin_steps.py     # 6 step actions (PTY only at runtime)
  builtin_assertions.py# 7 assertion evaluators (scripted modes only)
  agent_driven.py      # AgentRunner protocol, CodexCliAgentRunner, AgentDrivenRunner
  builtin_renderers.py # SvgRenderer
  builtin_reporters.py # MarkdownReporter
  builtin_video.py     # AggFfmpegBackend
  builtin_session.py   # PexpectAsciinemaBackend
  evidence.py          # new_run_dir(), render_artifacts(), write_result_files()
  report.py            # ReportGenerator (independently defines report logic)
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
3. Config cascades: builtin → `~/.config/tui-verifier/config.yaml` → `.tui-verifier/config.yaml` → CLI `--config`. Note `--config` has a known bug: help says YAML file but implementation treats it as project path and still loads default user config — see `configuration.md`.
4. `VerificationRunner` builds 7 registries plus a separately resolved session backend from the merged config; every extension point is a `module:ClassName` string resolved via `importlib` (8 extension families). `config.defaults` is modeled but currently unused — CLI and runner defaults remain hardcoded.
5. For each recipe × renderer combination, the runner resolves an execution mode (`agent_driven`, `scripted_pty`, `scripted_process` — only 3 fixed names) and executes steps: PTY mode via step registry, process mode via hardcoded `wait_for_text`/`sleep`, agent mode does not dispatch recipe steps.
6. Evidence is rendered from the cast (final text/SVG/MP4 when applicable), step snapshots rendered from stored screens, scored, written as `result.json` / `report.md`, and aggregated into `latest-report.md`.

See the individual docs for deeper dives.
