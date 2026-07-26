# TermProof

[![CI](https://github.com/md-mt/termproof/actions/workflows/ci.yml/badge.svg)](https://github.com/md-mt/termproof/actions/workflows/ci.yml)
[![Release](https://github.com/md-mt/termproof/actions/workflows/release.yml/badge.svg)](https://github.com/md-mt/termproof/actions/workflows/release.yml)
[![Verified by TermProof](https://img.shields.io/badge/verified%20by-TermProof-0a7a2e?style=flat-square)](https://github.com/md-mt/termproof)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue?logo=python)](https://www.python.org)
![Stars](https://img.shields.io/github/stars/md-mt/termproof?style=social)

> **Evidence-first verification for terminal and TUI applications.** No more "trust me, it works in my terminal." Record the real session, replay it, and ship the proof.

TermProof is a harness that drives your TUI from JSON recipes, records the actual terminal with [`asciinema`](https://docs.asciinema.org/), replays the cast into screenshots and text snapshots, optionally renders a 60-fps MP4 via [`agg`](https://github.com/asciinema/agg) + `ffmpeg`, and writes Markdown and JSON reports. Your reviewers inspect evidence instead of trusting a log line.

---

## What is this?

- **You ship a TUI** — built with Textual, Bubble Tea, Ratatui, Ink, or plain curses.
- **You write a recipe** — JSON that says: launch the binary, wait for `dashboard>`, type `open`, wait for `DASHBOARD READY`, assert it appeared.
- **TermProof runs it** — real PTY, real asciinema cast, deterministic, CI-friendly.
- **You get proof** — `session.cast`, `final.svg`, `final.txt`, `session.mp4`, per-step screenshots, `result.json`, `report.md`. Upload the folder as a CI artifact and link it from the PR.

Product-agnostic by design. Pi coding-agent workflows are included as the flagship showcase because they exercise realistic multi-turn agent UI flows.

## Why not X?

| Tool | Approach | Where it falls short for TUI evidence |
| --- | --- | --- |
| **Screenshots in docs** | Manual `screencap` | Stale within one PR; no replay; no assertion. |
| **expect / pexpect alone** | Scripted PTY driving | No cast, no video, no per-step screenshots, no report. |
| **Playwright / Cypress** | Browser DOM automation | Designed for web; cannot drive terminal PTY, ANSI, or Ink renderers. |
| **VHS (Charm)** | Tape files → GIF | Great for demos, not for assertions, CI gates, or evidence bundles. |
| **Asciinema alone** | Manual `asciinema rec` | No driving, no assertions, no report pipeline. |
| **TermProof** | Recipe → PTY → cast → screenshots → video → report → artifact | Assertions, deterministic runs, PR comments, evidence archives. |

If you want demo GIFs, use VHS. If you want **verifiable, reviewable, replayable proof that your TUI behaves**, use TermProof.

## Demo

Portable non-Pi TUI (included in this repo) — no Pi binary required:

```bash
uv run termproof run examples/generic --video
open .termproof/runs/<run-id>/session.mp4
open .termproof/runs/<run-id>/final.svg
cat .termproof/runs/<run-id>/report.md
```

Pi coding-agent showcase (deterministic fixtures, reproducible on any runner):

```bash
uv run termproof run examples/pi_workflow_guarded_edit.recipe.json --video --video-fps 60 --out .termproof/ci
cat .termproof/ci/latest-report.md
```

Sample artifacts are checked into `examples/artifacts/` so you can inspect without running anything:

- [`latest-pi-workflows-report.md`](examples/artifacts/latest-pi-workflows-report.md) — full report with assertion tables
- `pi-workflow-guarded-edit/session.mp4` — edited flow (when artifacts are present)
- `generic-tui-workflow/final.svg` — final screenshot from `examples/generic`

> Full evidence packs (screenshots, casts, videos, reports) are published as `termproof-ci-evidence` on every PR and as `termproof-release-evidence.tgz` on each release tag.

See the [GitHub Pages demo](https://md-mt.github.io/termproof/) for rendered samples.

## 3-command quickstart

Install (Python 3.11+):

```bash
pip install termproof
# or
uv pip install termproof
# or from source
uv run termproof --help
```

Create a recipe pack for your TUI:

```bash
termproof init .termproof/recipes --name my-tui --command "my-tui"
```

Run it with video evidence:

```bash
termproof run .termproof/recipes --video --out .termproof/runs
```

Each run writes under `.termproof/runs/<run-id>/` (or the `--out` you provide):

- `session.cast` — asciinema v2 recording (source of truth)
- `final.svg` / `final.txt` — final screenshot and screen text
- `steps/` — per-step screenshots and text snapshots
- `session.mp4` — H.264 video rendered via `agg` + `ffmpeg`
- `result.json` — machine-readable verdict and artifact paths
- `report.md` — per-run review summary
- `latest-report.md` — aggregate report for multi-recipe runs

## Recipe example

```json
{
  "name": "my-tui-main-flow",
  "description": "Open dashboard, filter, export.",
  "priority": "P0",
  "execution": "scripted",
  "determinism": "deterministic",
  "checks": ["dashboard opens", "filter applies", "export completes"],
  "command": { "argv": ["my-tui"], "pty": true },
  "timeout_seconds": 30,
  "cols": 100,
  "rows": 30,
  "steps": [
    { "name": "wait for prompt", "action": "wait_for_text", "text": "my-tui>", "timeout_seconds": 5 },
    { "name": "open dashboard", "action": "send_line", "text": "open dashboard" },
    { "name": "wait for dashboard", "action": "wait_for_text", "text": "DASHBOARD READY" }
  ],
  "assertions": [
    { "type": "output_contains", "value": "DASHBOARD READY" }
  ],
  "expect_exit_code": 0
}
```

Step actions: `wait_for_text`, `wait_for_idle`, `send_text`, `send_line`, `press`, `sleep`, `wait_for_count`
Assertions: `output_contains`, `output_not_contains`, `screen_contains`, `screen_not_contains`, `exit_code`, `file_exists`, `file_contains`

See [`docs/recipe-packs.md`](docs/recipe-packs.md) for layout and [`examples/generic/generic_tui.recipe.json`](examples/generic/generic_tui.recipe.json) for a minimal working recipe.

## CI snippet

Copy-paste for GitHub Actions. Identical to what this repository uses:

```yaml
- name: Install agg + ffmpeg
  run: |
    sudo apt-get update && sudo apt-get install -y ffmpeg
    if ! command -v agg >/dev/null 2>&1; then
      cargo install --locked --git https://github.com/asciinema/agg --tag v1.9.0
    fi

- name: Run TermProof
  run: |
    uv run termproof run .termproof/recipes --video --video-fps 60 --out .termproof/ci

- name: Upload TermProof evidence
  uses: actions/upload-artifact@v4
  if: always()
  with:
    name: termproof-ci-evidence
    path: .termproof/ci
    if-no-files-found: ignore

- name: Publish report to summary
  if: always()
  run: cat .termproof/ci/latest-report.md >> "$GITHUB_STEP_SUMMARY"
```

This repo also posts a sticky **TermProof CI Report** comment on every PR with the run link and embedded report. See [`.github/workflows/ci.yml`](.github/workflows/ci.yml) for the full implementation.

Reuse as a GitLab template or CircleCI orb by porting the same three steps — no Docker image required (see [#27](https://github.com/md-mt/termproof/issues/27) for generic image).

## Verified by TermProof badge

If you verify your TUI with TermProof, add the badge to your README:

[![Verified by TermProof](https://img.shields.io/badge/verified%20by-TermProof-0a7a2e?style=flat-square)](https://github.com/md-mt/termproof)

Markdown:

```md
[![Verified by TermProof](https://img.shields.io/badge/verified%20by-TermProof-0a7a2e?style=flat-square)](https://github.com/md-mt/termproof)
```

HTML:

```html
<a href="https://github.com/md-mt/termproof"><img src="https://img.shields.io/badge/verified%20by-TermProof-0a7a2e?style=flat-square" alt="Verified by TermProof"></a>
```

See [`docs/verified-badge.md`](docs/verified-badge.md) for variants (flat, plastic, for-the-badge) and usage guidelines.

## Community & plugins

- **Plugin directory:** [`docs/plugins.md`](docs/plugins.md) — community step/assertion/session/reporters/video backends.
- **Contributing:** [`CONTRIBUTING.md`](CONTRIBUTING.md) — ladder, setup, PR-only process.
- **Code of Conduct:** [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) — Contributor Covenant 2.1.
- **Pages demo:** https://md-mt.github.io/termproof/ — sample evidence, getting started, comparison, plugin directory.
- **Examples:** [`examples/generic`](examples/generic) — portable TUI; `examples/pi_workflow_*.recipe.json` — Pi agent showcase.
- **Docs:** [`docs/recipe-packs.md`](docs/recipe-packs.md) · [`docs/releases.md`](docs/releases.md) · [`docs/plugins.md`](docs/plugins.md) · [`docs/verified-badge.md`](docs/verified-badge.md)

## Upgrading from tui-verifier

TermProof is the renamed distribution, import package, and CLI: install `termproof`, import `termproof`, invoke `termproof`.

Existing project and user configuration remains readable without being modified. During migration, configuration is loaded in order: built-ins, legacy `~/.config/tui-verifier/config.yaml`, `~/.config/termproof/config.yaml`, legacy `.tui-verifier/config.yaml`, then `.termproof/config.yaml`. A value in the new location takes precedence over the legacy value.

Plugin references using `tui_verifier.*:ClassName` are translated to `termproof.*:ClassName` at load time. This narrow compat path is intentionally limited to configured plugin references; the legacy CLI and import package are not shipped.

## Packaging

```bash
uv build
uv pip install dist/termproof-*.whl
termproof --help
```

See [`docs/releases.md`](docs/releases.md) for versioning and release flow.

## Why asciinema first?

The cast is the source of truth. The pipeline:

```bash
asciinema rec --overwrite --stdin --quiet --cols "$COLS" --rows "$ROWS" \
  --command "$TARGET_COMMAND" session.cast
cat session.exitcode
agg --quiet --fps-cap 60 session.cast session.agg.gif
ffmpeg -y -loglevel error -i session.agg.gif \
  -vf 'fps=60,scale=trunc(iw/2)*2:trunc(ih/2)*2' \
  -pix_fmt yuv420p -movflags +faststart session.mp4
```

Screenshots, videos, assertions, and reports all derive from the same recording. Reviewers inspect what happened instead of trusting a private terminal session.
