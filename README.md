# TUI Verifier

TUI Verifier is an evidence-first verification harness for terminal and TUI
applications. It launches a target command through `asciinema rec --command`,
drives it with recipe steps when requested, derives terminal screenshots from
the recorded cast, optionally renders a 60-fps MP4 video with `agg` plus
`ffmpeg`, and writes a compact report.

The initial showcase recipes target the Pi coding agent because Pi is a real
terminal coding assistant with a stable local CLI surface.

## Quickstart

```bash
uv run tui-verify run examples/pi_help.recipe.json --video
uv run tui-verify run examples/pi_version.recipe.json --video
uv run tui-verify run examples/pi_list.recipe.json --video
uv run tui-verify run examples --priority P0 --renderer all --video
uv run tui-verify run examples/pi_codex_operator.recipe.json --video
uv run tui-verify list examples --priority P0
```

Each run writes artifacts under `.tui-verifier/runs/<run-id>/`:

- `session.cast` - asciinema v2 terminal recording
- `final.svg` - final terminal screenshot derived by replaying the cast
- `final.txt` - final terminal screen text
- `steps/` - per-step terminal screenshots and text snapshots
- `session.mp4` - 60-fps H.264 video rendered with `agg` plus `ffmpeg`
- `result.json` - machine-readable verdict and artifact paths
- `report.md` - review-friendly summary
- `latest-report.md` - aggregate report when multiple recipes/renderers run

Tracked Pi sample artifacts are included under `examples/artifacts/`.

`examples/pi_codex_operator.recipe.json` demonstrates agent-driven execution
with `codex exec` as the operator. The verifier records that operator process
with `asciinema rec`, stores the prompt/transcript/outcome, then publishes the
cast, screenshots, MP4 video, result JSON, and reports. In local Meta launcher
environments where `codex exec` exits before running because `sandbox-exec`
cannot apply its profile, the failed operator launch is captured as normal
verification evidence.

## Stack Design

The harness follows the same architecture as the MetaCode TUI validation stack:

- recipe metadata: `priority`, `execution`, `determinism`, `checks`, `ci_paths`
- recipe discovery and selection from `*.recipe.json` files
- renderer expansion with `--renderer default|all|<name>`
- per-run build provenance in aggregate reports
- evidence-first artifacts: cast, screenshot, per-step screenshots, MP4 video,
  result JSON, report
- agent-driven execution with a Codex CLI operator adapter
- before/after delta primitives for guardrail-style comparisons

## Recipe Format

Recipes are JSON files so they can live beside any project without importing
Python code.

```json
{
  "name": "hello-terminal",
  "priority": "P0",
  "execution": "scripted",
  "determinism": "deterministic",
  "checks": ["terminal prints hello"],
  "renderers": { "default": [] },
  "command": { "argv": ["python3", "-c", "print('hello tui')"], "pty": true },
  "steps": [
    { "action": "wait_for_text", "text": "hello tui", "timeout_seconds": 5 }
  ],
  "assertions": [
    { "type": "output_contains", "value": "hello tui" }
  ],
  "expect_exit_code": 0
}
```

Supported step actions:

- `wait_for_text`
- `wait_for_idle`
- `send_text`
- `send_line`
- `press`
- `sleep`

Supported assertions:

- `output_contains`
- `output_not_contains`
- `screen_contains`
- `screen_not_contains`
- `exit_code`
- `file_exists`
- `file_contains`

`command.pty` defaults to `true` for interactive TUI coverage. Set it to
`false` for terminal commands that should be captured without an interactive
PTY, while still producing asciinema-derived evidence.

`renderers` maps renderer names to extra argv appended to the command. For a
TUI with two frontends, a recipe can declare `{"opentui": [], "ink": ["-x",
"ink"]}` and `--renderer all` will run both.

The Pi examples do not assert a fixed exit code because Meta launcher sandbox
policy differs by machine. The actual exit code is still recorded in
`result.json` and `report.md`.

For agent-driven recipes, set `"execution": "agent-driven"` and add an
`operator` block such as `{"command": ["codex", "exec"], "prompt_mode":
"stdin", "record_terminal": true}`. The prompt includes the recipe checks,
target command, terminal dimensions, and expected JSON response schema.

## Why Asciinema First

The cast is the source of truth. The normal pipeline is:

```bash
asciinema rec --overwrite --stdin --quiet --cols "$COLS" --rows "$ROWS" \
  --command "$TARGET_COMMAND" session.cast
cat session.exitcode
agg --quiet --fps-cap 60 session.cast session.agg.gif
ffmpeg -y -loglevel error -i session.agg.gif \
  -vf 'fps=60,scale=trunc(iw/2)*2:trunc(ih/2)*2' \
  -pix_fmt yuv420p -movflags +faststart session.mp4
```

Screenshots and videos are generated from the same terminal recording that the
verifier used for assertions, so reviewers can inspect what happened instead of
trusting a private terminal session.

This mirrors the product-validation direction from the MetaCode TUI validation
docs: drive the real terminal surface, assert product outcomes, and publish
reviewable evidence.
