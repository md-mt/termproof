# Outreach: Textual (Python)

> Status: DRAFT template — human sends after `t_550ba351` approval
> Issue: #37
> Canonical links: see `docs/launch/README.md`

## Target

- **Framework:** Textual (Python TUI, Rich ecosystem)
- **Repo:** https://github.com/Textualize/textual
- **Maintainers:** via GitHub Discussions / Twitter DM — do not spam
- **Why relevant:** Largest Python TUI framework, needs CI evidence story beyond `pytest` + snapshot tests

## Message Template (Short, Issue + PR + DM friendly)

Subject: TermProof — CI evidence for Textual apps?

> Hi Textual team — I built TermProof, an evidence-first verifier for TUI apps. Records real PTY sessions via asciinema, replays into SVG screenshots + MP4 + Markdown report. Upload `termproof-ci-evidence` on every PR so reviewers see the proof. 60-second demo: `uv run termproof run examples/generic --video`. Might help catch Textual widget regressions in CI. Happy to help wire your first recipe. Repo: https://github.com/md-mt/termproof — Maintained by MD.

## Long-form Version (GitHub Discussion / Email)

Hi — I'm the maintainer of TermProof (https://github.com/md-mt/termproof) — MIT, Python 3.11+, just renamed from TUI Verifier.

**The problem:** TUI screenshots in docs go stale in one PR, `expect` gives you no cast/video/report, and Playwright/Cypress can't drive a PTY.

**What TermProof does:**

- JSON recipe drives your TUI in real PTY: `wait_for_text "dashboard>"`, `send_line "open"`, etc.
- Records asciinema v2 cast (source of truth)
- Replays cast into `final.svg`/`final.txt`, per-step screenshots, optional 60-fps MP4 via agg+ffmpeg, `report.md` + `result.json`
- Publishes as CI artifact — every PR gets `termproof-ci-evidence` + sticky comment with `latest-report.md`

**For Textual specifically:**

```json
{
  "name": "textual-dashboard smoke",
  "command": {"argv": ["python", "-m", "my_textual_app"], "pty": true},
  "steps": [
    {"action": "wait_for_text", "text": "My App", "timeout_seconds": 10},
    {"action": "send_line", "text": "open dashboard"},
    {"action": "wait_for_text", "text": "DASHBOARD READY"}
  ],
  "assertions": [{"type": "output_contains", "value": "DASHBOARD READY"}]
}
```

**Plugin hook for Textual DOM:**

Register a custom step `wait_for_textual` in `.termproof/config.yaml`:

```yaml
steps:
  wait_for_textual: my_org.termproof_textual:WaitForTextualStep
```

This awaits a Textual DOM selector instead of raw text — lets you assert widget tree, not ANSI.

**60-sec demo:**

```bash
git clone https://github.com/md-mt/termproof
uv run termproof run examples/generic --video
open .termproof/runs/<id>/session.mp4
```

Or inspect checked-in artifacts: `examples/artifacts/` (SVGs, MP4s, reports).

**Integration docs (current):**

- https://github.com/md-mt/termproof#quickstart
- https://github.com/md-mt/termproof/blob/main/docs/recipe-packs.md
- https://github.com/md-mt/termproof/tree/main/examples/generic
- Upcoming: `docs/guides/textual.md` per #24 — I can co-author (lands in t_1b2bfea8)

**Offer:** If you're interested, I'll draft a recipe pack for one of your Textual examples (e.g., `textual-demo` or `calculator`) and open a PR showing CI integration. No obligations.

Thanks for Textual — it's the reason this tool exists.

- MD (md-mt/termproof)

## Attachments / Links to Include

- Repo: https://github.com/md-mt/termproof
- Demo artifacts: `examples/artifacts/pi-workflow-guarded-edit/session.mp4` (60-second demo)
- CI evidence: latest `termproof-ci-evidence` from https://github.com/md-mt/termproof/actions/workflows/ci.yml
- Badge: `docs/verified-badge.md` — `Verified by TermProof` (lands in t_1b2bfea8 lane; link to README badge section until then)

## Follow-up Plan

- Wait 3-5 days. If no reply, one polite bump with a concrete PR example.
- If interested: co-author `docs/guides/textual.md` + `termproof-textual` plugin skeleton (Issue #23).
- Add to `docs/plugins.md` and Pages site (#16) if they adopt (lands in t_1b2bfea8 lane).

## Anti-patterns to Avoid

- No mass DMs.
- No unsolicited PRs to Textual repo without prior chat.
- No claiming Textual endorsement.
