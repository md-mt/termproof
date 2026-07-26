# Outreach: Common Template + Notes

> Applies to all framework outreach (Textual, Bubble Tea, Ratatui, Ink)
> Issue: #37
> For full framework-specific versions, see `textual.md`, `bubbletea.md`, `ratatui.md`, `ink.md`

## Principles

1. **Evidence, not marketing.** Show the cast → SVG/MP4/report pipeline, not buzzwords.
2. **Respect maintainer time.** Short first message (<150 words) + optional long-form.
3. **No mass DMs.** One-by-one, manual, contextualized.
4. **Offer concrete help.** "I'll draft a recipe for your example X" beats "you should use this".
5. **Complement, don't replace.** Textual snapshots, Buffer asserts, VHS demos, ink-testing-library all have place — TermProof adds PTY evidence + CI gate.
6. **MIT + plugin-friendly.** Emphasize extensibility via `.termproof/config.yaml` → `module:Class`.

## Structure for Every Outreach

### Short (DM, Tweet, GH Discussion first reply)

- What: TermProof = Cypress for terminal, evidence-first verifier
- How: recipe JSON → PTY + asciinema cast → SVG + MP4 + Markdown report + CI artifact
- Why for them: one sentence tied to their framework's testing gap
- Demo: `termproof run examples/generic --video`
- Link: `https://github.com/md-mt/termproof`
- Offer: draft a recipe for one of their examples

### Long (Email, GH Discussion body when asked)

- Problem: stale screenshots, no cast/video/report, Playwright can't drive PTY
- What it does: recording = source of truth, replay = screenshots/video/report, PR artifact = reviewer evidence
- Framework-specific recipe JSON snippet (copy-paste runnable)
- CI snippet (their language: python / go build / cargo / npm)
- Demo: portable generic pack + checked-in `examples/artifacts/`
- Docs links: quickstart + recipe-packs + generic example + future guides (Issue #24)
- Offer: PR with first recipe

## Canonical Snippets (Reuse)

### One-liner

> TermProof verifies TUI apps with replayable evidence: recipe → real PTY + asciinema cast → screenshots, MP4, Markdown report, CI artifact.

### 60-second demo

```bash
git clone https://github.com/md-mt/termproof
cd termproof
uv run termproof run examples/generic --video --out .termproof/demo
open .termproof/demo/*/final.svg
open .termproof/demo/*/session.mp4
cat .termproof/demo/*/report.md
```

### CI (Generic GH Actions)

```yaml
- name: Install render deps
  run: |
    sudo apt-get update && sudo apt-get install -y ffmpeg
    cargo install --locked --git https://github.com/asciinema/agg --tag v1.9.0 || true

- name: Run TermProof
  run: |
    pip install termproof
    termproof run .termproof/recipes --video --out .termproof/ci

- name: Upload evidence
  uses: actions/upload-artifact@v4
  if: always()
  with:
    name: termproof-ci-evidence
    path: .termproof/ci
```

## Before Sending — Checklist Per Maintainer

- [ ] Verify current repo URL (e.g., Ink moved from vadimdemedes/ink)
- [ ] Find 1 concrete example in their repo to reference (e.g., Textual calculator, Bubble Tea filepicker, Ratatui demo2, Ink demos)
- [ ] Personalize first line — mention their work
- [ ] Check they haven't already been contacted in `t_550ba351` gate
- [ ] Human gate approval (blocked task)

## Tracking

After sending (human operation, not this PR), record on Issue #37:

- Date, channel (GitHub Discussion link / Twitter DM), framework
- Response (interested / not now / no reply)
- Follow-up date
- Whether co-authored recipe or guide landed
- Link to `termproof-*` plugin if created

Example comment on Issue #37:

> 2026-08-10 — Sent Textual outreach via GitHub Discussions https://github.com/Textualize/textual/discussions/XXXXX — short + long template from `docs/launch/outreach/textual.md`. Offered to draft recipe for `textual/calculator`. Awaiting reply. Follow-up 2026-08-15. Gate remaining: human approval via t_550ba351.

## Handling Responses

- **Interested:** Schedule 30-min pairing to wire first recipe. Co-author `docs/guides/<framework>.md` (Issue #24). Add to `docs/plugins.md`.
- **Not now:** Thank, leave badge + link, ask if ok to ping after v0.3 guides.
- **No reply:** One polite bump after 5 days with concrete evidence artifact link, then drop.

## Anti-patterns

- No mass cross-posting identical message.
- No unsolicited PRs without discussion.
- No claiming endorsement.
- No selling — TermProof is MIT, community tool.
