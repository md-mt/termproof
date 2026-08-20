# TermProof — Python implementation

[![Python CI](https://github.com/md-mt/termproof/actions/workflows/python-ci.yml/badge.svg)](https://github.com/md-mt/termproof/actions/workflows/python-ci.yml)
[![Release (Python)](https://github.com/md-mt/termproof/actions/workflows/python-release.yml/badge.svg)](https://github.com/md-mt/termproof/actions/workflows/python-release.yml)
[![Verified by TermProof](https://img.shields.io/badge/verified%20by-TermProof-0a7a2e?style=flat-square)](https://github.com/md-mt/termproof)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue?logo=python)](https://www.python.org)

> **Evidence-first verification for terminal and TUI applications.** No more
> "trust me, it works in my terminal." Record the real session, replay it, and
> ship the proof.

This is the **Python implementation** of TermProof — the shipped product and
the behavioural oracle the [Rust implementation](../rust) is measured against.
Both live in [`md-mt/termproof`](https://github.com/md-mt/termproof); the
[repository README](https://github.com/md-mt/termproof#readme) is the front
door, covers both implementations and says which to reach for. This page is
the Python-specific reference.

TermProof is a harness that drives your TUI from JSON recipes, records the
actual terminal as an
[asciinema v2 cast](https://docs.asciinema.org/manual/asciicast/v2/), replays
the cast into screenshots and text snapshots, optionally renders a 60-fps MP4
via [`agg`](https://github.com/asciinema/agg) + `ffmpeg`, and writes Markdown
and JSON reports. Your reviewers inspect evidence instead of trusting a log
line.

Product-agnostic by design: TermProof knows nothing about the program it
drives beyond what a recipe says. The examples reflect that — a portable TUI
that needs no external binary, a colour-stress renderer, a multi-turn
conversation, and a set of Pi coding-agent recipes for agent-UI flows. Each
covers a different shape of terminal program; none of them is the point, and
the recipe format is.

## Quickstart

Install (Python 3.11+):

```bash
pip install termproof
# or from Homebrew
brew tap md-mt/termproof https://github.com/md-mt/termproof
brew install termproof
# or unreleased, from GitHub
pip install git+https://github.com/md-mt/termproof.git
# or from source
git clone https://github.com/md-mt/termproof.git && cd termproof/python
uv run termproof --help
```

Create a recipe pack for your TUI, then run it with video evidence:

```bash
termproof init .termproof/recipes --name my-tui --command "my-tui"
termproof run .termproof/recipes --video --out .termproof/runs
```

Or run one of the examples in this repository. `examples/generic` is a
self-contained TUI and needs no external binary — start here:

```bash
uv run termproof run examples/generic --video
open .termproof/runs/<run-id>/session.mp4
open .termproof/runs/<run-id>/final.svg
cat .termproof/runs/<run-id>/report.md
```

The other examples cover different shapes of terminal program:
`examples/colorstress` for attributed rendering,
`examples/multi_turn_conversation.recipe.json` for a conversational flow, and
the `examples/pi_workflow_*.recipe.json` set for an agent UI. All of them run
from deterministic fixtures, so they reproduce on any runner:

```bash
uv run termproof run examples/pi_workflow_guarded_edit.recipe.json --video --video-fps 60 --out .termproof/ci
cat .termproof/ci/latest-report.md
```

Sample artifacts are checked into `examples/artifacts/` so you can inspect
without running anything:

- [`latest-pi-workflows-report.md`](examples/artifacts/latest-pi-workflows-report.md)
  — full report with assertion tables
- [`generic-tui-workflow/final.svg`](examples/artifacts/generic-tui-workflow/final.svg)
  — final screenshot from `examples/generic`

## What a run writes

Each run writes under `.termproof/runs/<run-id>/` (or the `--out` you provide):

- `session.cast` — asciinema v2 recording (source of truth)
- `final.svg` / `final.txt` — final screenshot and screen text
- `steps/` — per-step screenshots and text snapshots
- `session.mp4` — H.264 video rendered via `agg` + `ffmpeg`
- `result.json` — machine-readable verdict and artifact paths
- `report.md` — per-run review summary
- `latest-report.md` — aggregate report for multi-recipe runs

## Evidence collector

`termproof.collector.EvidenceCollector` is the ordered step model for a caller
driving its own run rather than a recipe. `capture` and `capture_failure` pull
from a `ScreenSource`; `capture_text` records a screen you already hold — text
recovered from a log, or a golden file in a test:

```python
collector.capture_text("from-log", recovered)
collector.capture_text("post-mortem", last_screen, CaptureKind.FAILURE)
```

**This is the one collector signature the two implementations do not share.**
Here `kind` defaults to `CaptureKind.CHECKPOINT`; Rust takes it positionally,
as `capture_text(label, screen, CaptureKind::Checkpoint)`. The meaning, the
ordering and the resulting manifest are identical.

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

Step actions: `wait_for_text`, `wait_for_idle`, `send_text`, `send_line`,
`press`, `sleep`, `wait_for_count`
Assertions: `output_contains`, `output_not_contains`, `screen_contains`,
`screen_not_contains`, `step_screen_contains`, `exit_code`, `file_exists`,
`file_contains`

Recipes are discovered as `*.recipe.json`. See
[`docs/recipe-packs.md`](docs/recipe-packs.md) for pack layout and
[`examples/generic/generic_tui.recipe.json`](examples/generic/generic_tui.recipe.json)
for a minimal working recipe. The format itself is specified independently of
this implementation, in [`spec/`](../spec).

## CI

The [repository README](https://github.com/md-mt/termproof#use-it-in-ci) has
the copy-paste GitHub Actions snippet. This repository posts a sticky
**TermProof CI Report** comment on every PR with the run link, base-commit
report, head report, and behavioural delta; release tags package the same
receipt-backed report as `termproof-release-evidence.tgz`. For
same-repository PRs, screenshot links are copied to the `termproof-evidence`
branch and rewritten to raw GitHub URLs so they are directly viewable from the
comment. Videos remain in the workflow artifact until hosted video evidence is
implemented in [#69](https://github.com/md-mt/termproof/issues/69). See
[`.github/workflows/python-ci.yml`](../.github/workflows/python-ci.yml) for the
full implementation, and [`docs/ci/`](docs/ci) for GitLab, CircleCI and Docker.

## Upgrading from tui-verifier

TermProof is the renamed distribution, import package, and CLI: install
`termproof`, import `termproof`, invoke `termproof`.

Existing project and user configuration remains readable without being
modified. During migration, configuration is loaded in order: built-ins, legacy
`~/.config/tui-verifier/config.yaml`, `~/.config/termproof/config.yaml`, legacy
`.tui-verifier/config.yaml`, then `.termproof/config.yaml`. A value in the new
location takes precedence over the legacy value.

Plugin references using `tui_verifier.*:ClassName` are translated to
`termproof.*:ClassName` at load time. This narrow compat path is intentionally
limited to configured plugin references; the legacy CLI and import package are
not shipped.

## Configuration

Optional configuration lives in `~/.config/termproof/config.yaml` (user) or
`.termproof/config.yaml` (project). The `defaults` block exposes the
post-script idle wait cap:

```yaml
defaults:
  # Cap (seconds) for the post-script idle wait in PTY mode. After the last
  # step, TermProof waits for the screen to quiesce before capturing the
  # final state. Slow-quiescing TUIs may need a larger cap; set to null to
  # wait up to the recipe's timeout_seconds instead of a fixed cap.
  idle_cap_seconds: 3.0
```

`idle_cap_seconds` is the documented replacement for the former hard-coded
3-second idle cap in `runner.py`. Defaults to `3.0` to preserve existing
behavior; raise it (or set `null`) for TUIs that take longer to settle. The
value must be a finite, nonnegative number: negative, NaN, or infinite values
are rejected at config load.

The idle wait — both the `wait_for_idle` step and this post-script wait —
starts measuring at the session's **first byte of output**, so a session that
has produced no output is never treated as idle. The trade: a target that stays
alive and never emits anything is never idle. A `wait_for_idle` step over such
a target fails with `no output observed from the session` after its
`timeout_seconds`, and the post-script wait burns its full budget — with
`idle_cap_seconds: null` that is the whole recipe `timeout_seconds`, so prefer
a finite cap for targets that may be silent. Once the first byte has arrived,
quiescence is measured on rendered screen text only: terminal-title updates,
colour changes, and repaints that redraw the same characters all count as
quiet.

### Evidence rendering

The `evidence` block sets the screenshot and video parameters that used to be
hard-coded in the renderers and the video pipeline, split into `svg`, `png`, and
`video`, plus the run-wide `dedup_step_screenshots` switch:

```yaml
evidence:
  svg:
    font_size: 16
    fg: "#e6edf3"
    bg: "#0b0f14"
  png:
    scale: 1
    font_path: null
  video:
    fps: 60
    pix_fmt: yuv420p
    crf: null
  dedup_step_screenshots: false
```

`BUILTIN_DEFAULTS` in `termproof/config.py` lists every knob with its default,
read off the config dataclasses rather than restated beside them.

- `evidence.svg` is the same geometry as `SvgStyle`, under the names the YAML uses, and takes every default from the same `DEFAULT_*` constants in `termproof/attributed.py`. `SvgStyle` is canonical; `SvgRenderConfig` is how a run overrides it. The two used to disagree in every field — see [`CHANGELOG.md`](../CHANGELOG.md) for what moved and how to pin the old values.
- `evidence.svg.min_width`/`min_height` floor the SVG canvas and default to `0`, because a viewer scales an SVG. On the two renderers that rasterise that SVG — `png_rsvg` and the `attributed_rsvg` video backend — setting them higher raises the floor, and setting them lower does not lower it below 320x160, since a PNG is a fixed pixel count. They do **not** reach the `png` renderer at all: it is configured by `evidence.png` and measures its own cell off the PIL face, and its own 320x160 floor is not adjustable.
- `evidence.video.fps` is the default for `--video-fps`; the flag wins when passed.
- A `null` video knob means "omit that flag"; `fps_cap: null` keeps `agg`'s cap tied to the output fps.
- `png.font_size` applies only when `png.font_path` is set — the bundled bitmap face has one fixed size.
- `png.scale` multiplies the canvas, the padding and the line pitch, not the glyphs of that bitmap face, so it spreads the same text over a larger image unless `png.font_path` is set too.
- Unknown keys under `evidence` are rejected at config load, so a misspelled knob fails loudly instead of silently doing nothing. So are a value of the wrong type, a section that is not a mapping, a non-positive size or frame rate, and a negative padding.
- Evidence values are part of the `--skip-unchanged` cache key, so changing one re-renders cached runs. The `video` knobs only count towards it for a run that renders video, as `--video-fps` and the video backend already do.
- `dedup_step_screenshots` skips the screenshot for a step whose screen is unchanged from the immediately preceding step, so an unbroken run of identical screens costs one image instead of one per step. A screen that reappears after a different one is rendered again. Half of the consecutive step screenshots in the shipped corpus are byte-identical. Every step still gets its `.txt`, and `steps/steps-manifest.json` names the image that represents each one, so no step is lost — but a consumer that globs `steps/*.svg` has to read the manifest instead. Off by default for that reason.

See [`docs/evidence-quality.md`](docs/evidence-quality.md) for what the research
measured about these defaults and which alternatives it recommends.

## Packaging

```bash
uv build
uv pip install dist/termproof-*.whl
termproof --help
```

See [`docs/releases.md`](docs/releases.md) for versioning and release flow. The
version train is shared with the Rust implementation and the history is in the
[root changelog](../CHANGELOG.md); the release paths are separate, and a Python
release is tagged `py-v<version>`.

## Why the cast comes first

The cast is the source of truth. Screenshots, videos, assertions and reports
all derive from the same recording, so reviewers inspect what happened instead
of trusting a private terminal session.

The default `pexpect` session backend writes the asciinema v2 cast itself, from
the PTY output it is already reading — nothing extra to install. Rendering it:

```bash
cat session.exitcode
agg --quiet --fps-cap 60 session.cast session.agg.gif
ffmpeg -y -loglevel error -i session.agg.gif \
  -vf 'fps=60,scale=trunc(iw/2)*2:trunc(ih/2)*2' \
  -pix_fmt yuv420p -movflags +faststart session.mp4
```

The `attributed_rsvg` video backend skips `agg` entirely and renders each frame
from the same attributed grid `final.svg` is rendered from, so a video frame and
the final screenshot of the same moment are the same image. It needs
`rsvg-convert` and `ffmpeg`.

A per-step screenshot is rendered from the grid its session reported at that
step, when the session had one to report. Every built-in backend does, so the
`steps/` images carry the same colour and text attributes as `final.svg` — but
they are read from the live session rather than replayed from the cast, so a
frame of the video and a *step* image are not guaranteed to be the same bytes
the way the final screenshot and its frame are. A session backend with no
`screen_attributed()` renders its step screenshots from the flattened text, in
monochrome; so does the `png` screen renderer, which accepts text only.

If you specifically want a cast that the asciinema CLI wrote, install the extra
and select that backend:

```bash
pip install 'termproof[record]'
```

```yaml
# .termproof.yaml
session_backend: pexpect_asciinema
```

## Documentation

- [`docs/install/homebrew.md`](docs/install/homebrew.md) ·
  [`docs/recipe-packs.md`](docs/recipe-packs.md) ·
  [`docs/recipe-format-v1.md`](docs/recipe-format-v1.md)
- Framework guides: [Textual](docs/guides/textual.md) ·
  [Bubble Tea](docs/guides/bubbletea.md) · [Ratatui](docs/guides/ratatui.md)
- [`docs/releases.md`](docs/releases.md) ·
  [`docs/evidence-quality.md`](docs/evidence-quality.md) ·
  [`docs/plugins.md`](docs/plugins.md) ·
  [`docs/verified-badge.md`](docs/verified-badge.md)
- CI: [GitLab](docs/ci/gitlab.md) · [CircleCI](docs/ci/circleci.md) ·
  [Docker](docs/ci/docker.md)
- [`docs-site`](docs-site) — VitePress documentation source and build.

Project-level documents — contributing, support, security, the code of
conduct, the changelog and the recipe specification — live at the repository
root.
