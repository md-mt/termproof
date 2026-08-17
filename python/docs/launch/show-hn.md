# Show HN: TermProof — Evidence-first verification for TUI apps (like Cypress for TUIs)

> Status: **DRAFT — do not post until v0.2.0 release approved via t_550ba351**
> Related: Issue #36
> Author guide: See `docs/launch/runbook.md` for response plan after posting.

## Target Title

`Show HN: TermProof – Verify terminal apps with cast, screenshots, video` (71 chars)

Alternatives, in order if HN dedupes or we need to reframe:

1. `Show HN: TermProof – I built Cypress for terminal apps (cast + video)` (69 chars)
2. `Show HN: TermProof – Verify your TUI in CI with replayable evidence` (67 chars)
3. `Show HN: TermProof – Stop trusting TUI screenshots, ship the proof` (66 chars)

HN title limit: 80 chars recommended. All titles pass.

## Why TermProof Exists

TUI frameworks are booming — Textual, Bubble Tea, Ratatui, Ink — but testing story is "trust me, it works in my terminal." Manual screenshots go stale in one PR. `expect` gives you no cast, no video, no per-step screenshots. Playwright/Cypress can't drive a PTY. VHS is great for demos, not for assertions or CI gates.

TermProof: write a JSON recipe that drives your TUI in a real PTY, records the full session as an asciinema-format cast, replays it into `final.svg`/`final.txt`, per-step screenshots, optional 60-fps MP4 via agg+ffmpeg, and a `report.md` + `result.json`. Upload the folder as a CI artifact. Reviewers inspect evidence instead of trusting a log line.

## Draft Body (HN Markdown)

---

I built TermProof — an evidence-first verification harness for terminal/TUI apps.

It drives your TUI from a JSON recipe (wait_for_text, send_line, press, etc.), records the real terminal session as an asciinema-format cast, replays the cast into screenshots, text snapshots, MP4 via agg+ffmpeg, and writes Markdown + JSON reports. Instead of "trust me, works in my terminal", you ship proof.

**What it looks like:**

```bash
pip install termproof
termproof init .termproof/recipes --name my-tui --command "my-tui"
termproof run .termproof/recipes --video
# -> .termproof/runs/<id>/session.cast, final.svg, session.mp4, report.md
```

Recipe example (`my-tui.recipe.json`):

```json
{
  "name": "open-dashboard",
  "command": {"argv": ["my-tui"], "pty": true},
  "steps": [
    {"action": "wait_for_text", "text": "my-tui>", "timeout_seconds": 5},
    {"action": "send_line", "text": "open dashboard"},
    {"action": "wait_for_text", "text": "DASHBOARD READY"}
  ],
  "assertions": [{"type": "output_contains", "value": "DASHBOARD READY"}]
}
```

**Evidence from a single run:**

- `session.cast` — asciinema v2 (source of truth)
- `final.svg` / `final.txt` — final screenshot + screen text
- `steps/` — per-step screenshots + text snapshots
- `session.mp4` — H.264 via agg + ffmpeg (60 fps)
- `result.json` + `report.md` — verdict + artifact paths

This repo publishes that folder as `termproof-ci-evidence` on every PR and as `termproof-release-evidence.tgz` on every release tag.

**Why not:**

| Approach | Gap |
| --- | --- |
| Manual screenshots | Stale in one PR, no replay |
| expect/pexpect | No cast, video, screenshots, report |
| Playwright/Cypress | Browser DOM, not terminal PTY/ANSI |
| VHS | Great demos, not assertions/CI gates |
| asciinema alone | No driving, assertions, pipeline |

**What works today:**

- Plugin registry: steps, assertions, session backends, video backends, reporters, execution modes — all in `.termproof/config.yaml`
- Example recipe sets, all checked in under `examples/`: a portable TUI, a colour-stress renderer, a multi-turn conversation, and Pi coding-agent flows
- Portable demo: `examples/generic/generic_tui.py` — run without any Pi binary or API key
- GitHub Actions: `termproof-ci-evidence` artifact + sticky PR comment with `latest-report.md`

**60-second demo:**

```bash
git clone https://github.com/md-mt/termproof
cd termproof
uv run termproof run examples/generic --video --out .termproof/demo
open .termproof/demo/*/session.mp4
```

Artifacts are checked in under `examples/artifacts/` if you want to look without running.

**Links:**

- Repo: https://github.com/md-mt/termproof
- Docs: https://github.com/md-mt/termproof/blob/main/docs/recipe-packs.md
- Badge: Verified by TermProof (see README)
- License: MIT, Python 3.11+

I'm actively working on: `termproof demo` built-in TUI (#9), wait_for_regex (#14), JUnit reporter (#15), Textual/Bubble Tea/Ratatui guides (#24), Homebrew formula (#17), reusable GitHub Action (#10), and a hosted demo site (#16).

Ask me anything about TUI testing — would love to help you write your first recipe.

---

## Companion Comment (Post Immediately After Submitting, As Author)

> Quick notes for context:
> - The cast is the source of truth for terminal output. Screenshots, final SVG/text, and video replay from the same `.cast` — reviewers can diff it. Assertions evaluate from live terminal state during the run; the report aggregates those results with replayed evidence.
> - Works for any terminal program, not just TUIs — the generic pack verifies a toy CLI with `open dashboard / filter errors / export report`.
> - Plugin system is already shipping: if you have a custom step (e.g. wait_for_regex for Textual DOM), you register `my_pkg:WaitForRegex` in `.termproof/config.yaml`.
> - Happy to review a recipe PR if you try it — open an issue with your command and expected flow.

## Images / Links to Include

HN doesn't embed images in the submission itself, but link in comments or host:

- `examples/artifacts/pi-workflow-guarded-edit/session.mp4` — 60-second demo, upload to GitHub Releases or link to `termproof-ci-evidence` latest run
- `examples/artifacts/latest-pi-workflows-report.md` — aggregate report
- SVG screenshots: use `rsvg-convert` to convert `final.svg` to PNG for HN compatibility:
  ```bash
  # From a termproof run:
  rsvg-convert -w 800 .termproof/runs/<id>/final.svg -o final.png
  # Or for checked-in artifacts:
  rsvg-convert -w 800 examples/artifacts/<run-dir>/final.svg -o final.png
  ```
  (`rsvg-convert` from `librsvg2-bin` on apt/brew; `inkscape --export-type=png` also works)

Preferred canonical demo link after v0.2 release:

- `https://github.com/md-mt/termproof/tree/main/examples/artifacts` (checked-in evidence)
- `https://github.com/md-mt/termproof/actions/workflows/python-ci.yml` → latest run → `termproof-ci-evidence` artifact
- `https://md-mt.github.io/termproof/` when Pages lands (#16) — update this file in follow-up PR

## Posting Checklist

See `docs/launch/checklist.md` Section "Show HN". Do not post before:

- [ ] v0.2.0 tag released and `termproof-release-evidence.tgz` attached
- [ ] `termproof demo` or `examples/generic --video` produces `session.mp4` < 60s
- [ ] README has Comparison table + Demo + 3-command quickstart + CI snippet (Issue #8, lane t_1b2bfea8)
- [ ] Human gate `t_550ba351` approved
- [ ] Second pair of eyes reviewed title/body for HN tone (no marketing fluff)

## Monitoring (From Runbook)

After posting, see `docs/launch/runbook.md`:

- Monitor HN comments every 15 min for first 2h
- Respond with technical depth, not marketing
- Track "tried it" responses — invite to `docs/plugins.md` (lands in t_1b2bfea8) or badge
- Capture FAQs for README/docs update
