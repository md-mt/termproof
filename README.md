# TermProof

TermProof is an evidence-first verification harness for terminal and TUI
applications. It records the real terminal session with `asciinema`, drives the
session from JSON recipes, replays the cast into screenshots and text snapshots,
optionally renders a 60-fps MP4 with `agg` plus `ffmpeg`, and writes Markdown
and JSON reports for review.

The verifier is product-agnostic: any terminal program can be plugged in by
checking in a recipe pack. Pi coding agent workflows are included as the main
showcase because they exercise realistic multi-turn coding-agent UI flows.

## Quickstart

Run the portable non-Pi example:

```bash
uv run termproof run examples/generic --video
```

Run the Pi coding-agent workflow showcase:

```bash
uv run termproof run examples/pi_workflow_*.recipe.json --video
```

Create a starter recipe pack for your own TUI:

```bash
uv run termproof init .termproof/recipes \
  --name my-tui \
  --command "my-tui"

uv run termproof run .termproof/recipes --video
```

Each run writes artifacts under `.termproof/runs/<run-id>/` unless `--out`
is provided:

## Upgrading from TUI Verifier

TermProof is the renamed distribution, import package, and CLI: install
`termproof`, import `termproof`, and invoke `termproof`. Existing project and
user configuration remains readable without being modified. During migration,
configuration is loaded in this order: built-ins, legacy
`~/.config/tui-verifier/config.yaml`, `~/.config/termproof/config.yaml`, legacy
`.tui-verifier/config.yaml`, then `.termproof/config.yaml`. A value in the new
location takes precedence over the corresponding legacy value.

Plugin references using the legacy `tui_verifier.*:ClassName` module prefix are
translated to `termproof.*:ClassName` at load time. This narrow compatibility
path is intentionally limited to configured plugin references; the legacy CLI
and Python import package are not shipped.

- `session.cast` - asciinema v2 terminal recording
- `final.svg` - final terminal screenshot from the cast
- `final.txt` - final terminal screen text
- `steps/` - per-step screenshots and text snapshots
- `session.mp4` - H.264 video rendered through `agg` and `ffmpeg`
- `result.json` - machine-readable verdict and artifact paths
- `report.md` - per-run review summary
- `latest-report.md` - aggregate report for multi-recipe runs

## Plug In Any TUI

A recipe pack is just a directory with `*.recipe.json` files and optional helper
scripts. Keep it near the product it verifies:

```text
.termproof/
  recipes/
    smoke.recipe.json
    regression.recipe.json
    fixtures/
      seed-project.sh
```

Run the whole pack:

```bash
uv run termproof run .termproof/recipes --video --out .termproof/runs
```

Use `command.argv` for the target process and keep `command.pty` set to `true`
for interactive TUIs. Steps wait for visible terminal states and send input.
Assertions check raw output, final screen text, exit code, or files.

```json
{
  "name": "my-tui-main-flow",
  "description": "Open the dashboard, filter data, and export a report.",
  "priority": "P0",
  "execution": "scripted",
  "determinism": "deterministic",
  "checks": [
    "dashboard opens",
    "filter applies",
    "export completes"
  ],
  "renderers": {
    "default": []
  },
  "command": {
    "argv": ["my-tui"],
    "pty": true
  },
  "timeout_seconds": 30,
  "cols": 100,
  "rows": 30,
  "steps": [
    {
      "name": "wait for prompt",
      "action": "wait_for_text",
      "text": "my-tui>",
      "timeout_seconds": 5
    },
    {
      "name": "open dashboard",
      "action": "send_line",
      "text": "open dashboard"
    },
    {
      "name": "wait for dashboard",
      "action": "wait_for_text",
      "text": "DASHBOARD READY",
      "timeout_seconds": 10
    },
    {
      "name": "export report",
      "action": "send_line",
      "text": "export report"
    },
    {
      "name": "wait for export",
      "action": "wait_for_text",
      "text": "EXPORT READY",
      "timeout_seconds": 10
    }
  ],
  "assertions": [
    {
      "type": "output_contains",
      "value": "DASHBOARD READY"
    },
    {
      "type": "output_contains",
      "value": "EXPORT READY"
    }
  ],
  "expect_exit_code": 0
}
```

For non-interactive terminal commands, set `pty` to `false`:

```json
{
  "name": "my-tui-help",
  "priority": "P0",
  "execution": "scripted",
  "command": {
    "argv": ["my-tui", "--help"],
    "pty": false
  },
  "steps": [
    {
      "action": "wait_for_text",
      "text": "Usage:",
      "timeout_seconds": 5
    }
  ],
  "assertions": [
    {
      "type": "output_contains",
      "value": "Usage:"
    }
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

Use `renderers` when one recipe should run against multiple TUI frontends. For
example, `{"opentui": [], "ink": ["--renderer", "ink"]}` lets
`--renderer all` run both command variants and publish evidence for each.

## GitHub Actions

TermProof is also a reusable composite action (`md-mt/termproof@v0.2.0`). It accepts a recipe path plus video and fps controls, installs the published platform wheel, executes the recipes, uploads `termproof-evidence`, and writes the recipe report to the GitHub job summary. It does not read repository secrets or post PR comments, so it is safe for pull requests from forks.

```yaml
- uses: md-mt/termproof@v0.2.0
  with:
    recipe-path: .termproof/recipes
    video: "true"
    fps: "60"
```

This repository includes Actions for the regular verification lifecycle:

| Workflow | Trigger | What runs |
| --- | --- | --- |
| `CI` | every pull request and every commit pushed to `main` | unit tests, package build, generic TUI E2E verification, deterministic Pi agent UI verification, run summary, PR comment, evidence upload |
| `Release` | `v*.*.*` tags and manual dispatch | unit tests, package build, installed-wheel smoke test, generic TUI E2E verification, deterministic Pi agent UI verification, run summary, release notes, release evidence archive |

The CI command is intentionally the same shape a downstream project should use:

```bash
uv run termproof run \
  examples/generic \
  examples/multi_turn_conversation.recipe.json \
  examples/pi_workflow_readonly_review.recipe.json \
  examples/pi_workflow_guarded_edit.recipe.json \
  examples/pi_workflow_session_resume_export.recipe.json \
  examples/pi_workflow_model_context.recipe.json \
  --video --video-fps 60 --out .termproof/ci
```

For your own project, replace the `examples/...` paths with your recipe pack:

```yaml
- name: Run TUI verification
  run: |
    uv run termproof run .termproof/recipes \
      --video --video-fps 60 --out .termproof/ci

- name: Upload TUI evidence
  uses: actions/upload-artifact@v4
  if: always()
  with:
    name: termproof-evidence
    path: .termproof/ci
    if-no-files-found: ignore
```

Public CI runs deterministic Pi-style workflows instead of provider-backed live
Pi sessions. That keeps every PR, `main` commit, and release reproducible on a
fresh GitHub runner while still validating multi-turn coding-agent UI patterns.

Every PR receives a sticky `TermProof CI Report` comment. The comment links
to the workflow run, embeds `.termproof/ci/latest-report.md`, and points
reviewers to the `termproof-ci-evidence` artifact containing screenshots,
casts, videos, JSON results, and per-recipe reports. The same report is written
to the GitHub run summary for PR and `main` runs.

Release runs write `.termproof/release/latest-report.md` into the GitHub run
summary and into the GitHub Release body. The release also attaches
`termproof-release-evidence.tgz`, which contains the generated screenshots,
videos, casts, and reports.

## Pi Coding Agent Showcase

Pi examples demonstrate how TermProof captures coding-agent workflows:

- `examples/pi_workflow_readonly_review.recipe.json` - read-only review with
  tool gating.
- `examples/pi_workflow_guarded_edit.recipe.json` - edit, patch, validate, and
  summarize flow.
- `examples/pi_workflow_session_resume_export.recipe.json` - named session,
  resume, fork, and export flow.
- `examples/pi_workflow_model_context.recipe.json` - provider/model routing and
  context resource selection.
- `examples/pi_codex_operator.recipe.json` - Codex operates the verification
  target and returns a structured judgment.

Tracked evidence is included under `examples/artifacts/`:

- `examples/artifacts/latest-pi-workflows-report.md`
- `examples/artifacts/pi-workflow-guarded-edit/session.mp4`
- `examples/artifacts/pi-workflow-readonly-review/session.mp4`
- `examples/artifacts/multi-turn-conversation/session.mp4`

The real Pi CLI surface is also covered locally by:

```bash
uv run termproof run examples/pi_help.recipe.json --video
uv run termproof run examples/pi_version.recipe.json --video
uv run termproof run examples/pi_list.recipe.json --video
```

Those recipes call `examples/bin/pi-clean`, which prefers
`/usr/local/bin/pi_cli/pi.real` when present and can be overridden with
`TERMPROOF_PI_BIN`. Provider-backed or private Pi installations should be
run in local or private CI environments where the Pi binary and credentials are
available.

## Packaging

TermProof ships as a Python package with the `termproof` console script.

```bash
uv build
uv pip install dist/termproof-*.whl
termproof --help
```

See `docs/recipe-packs.md` and `docs/releases.md` for the reusable packaging
contract and release flow.

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

Screenshots, videos, assertions, and reports all come from the same terminal
recording. Reviewers can inspect what happened instead of trusting a private
terminal session.
