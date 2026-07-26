# Outreach: Ink (React for CLIs)

> Status: DRAFT template — human sends after t_550ba351 approval
> Issue: #37
> Canonical links: see docs/launch/README.md

## Target

- **Framework:** Ink (React renderer for CLI/TUI, by Vadim Demedes, now maintained by community)
- **Repos:** https://github.com/vadimdemedes/ink, https://github.com/charmbracelet/ink (check current)
- **Maintainers:** via GitHub Discussions / Twitter
- **Why relevant:** React mental model for CLIs, widely used for `claude-code`, `opencode`, etc. Needs E2E evidence beyond unit snapshots + ink-testing-library

## Short Template

> Built TermProof — Cypress-for-terminal. JSON recipes drive Ink CLI in real PTY, record asciinema cast, replay to SVG+MP4+MD report. Complements ink-testing-library (unit) with integration evidence. 60s demo: `termproof run examples/generic --video`. Repo https://github.com/md-mt/termproof. Happy to draft a recipe for an Ink example + GH Action.

## Long-form Version

Hi Ink team — I maintain TermProof (https://github.com/md-mt/termproof) — MIT, evidence-first verifier for terminal/TUI apps.

**The gap for Ink:** `ink-testing-library` is excellent for unit rendering (React tree → output asserts), but you still need integration proof: real PTY, real keypress sequences, exit codes, file artifacts, video for reviewers, and a report artifact attached to PRs.

TermProof closes that:

- Recipe drives your compiled Ink binary in real PTY: `wait_for_text`, `press`, `send_text`, etc.
- Records asciinema v2 cast (source of truth)
- Replays into `final.svg`/`final.txt`, per-step screenshots, optional MP4 via agg+ffmpeg, `report.md` + `result.json`
- CI artifact `termproof-ci-evidence` + sticky PR comment

**For Ink:**

```json
{
  "name": "ink cli smoke",
  "command": {"argv": ["node", "dist/cli.js"], "pty": true},
  "cols": 100,
  "rows": 30,
  "steps": [
    {"name": "wait for prompt", "action": "wait_for_text", "text": "my-cli>", "timeout_seconds": 10},
    {"name": "list", "action": "send_line", "text": "list"},
    {"name": "wait for items", "action": "wait_for_text", "text": "3 items", "timeout_seconds": 5},
    {"name": "quit", "action": "send_line", "text": "exit"}
  ],
  "assertions": [
    {"type": "screen_contains", "value": "3 items"},
    {"type": "exit_code", "value": 0}
  ]
}
```

**JS/TS CI snippet:**

```yaml
- name: Build Ink app
  run: npm ci && npm run build

- name: Install TermProof + render deps
  run: |
    pipx install termproof
    sudo apt-get update && sudo apt-get install -y ffmpeg
    cargo install --locked --git https://github.com/asciinema/agg --tag v1.9.0 || true

- name: Verify CLI
  run: termproof run .termproof/recipes --video --out .termproof/ci

- uses: actions/upload-artifact@v4
  with:
    name: termproof-ci-evidence
    path: .termproof/ci
```

**Why both ink-testing-library + TermProof:**

- `ink-testing-library`: fast unit, React component output asserts, no PTY
- TermProof: integration, real terminal evidence, multi-turn flows, video for reviewers, PR artifact

Pattern: unit with testing library, integration with TermProof, both in CI.

**INK + Pi/Coding-agent showcase:**

This repository's `examples/pi_workflow_*.recipe.json` demonstrate how TermProof verifies multi-turn coding-agent CLI UIs (read-only review, guarded edit, session resume/export, model/context). Those flows are similar to verifying Ink CLIs that run long-lived sessions — TermProof records the whole session cast and replays to screenshot/video.

**60-second demo (generic TUI, no Node needed):**

```bash
git clone https://github.com/md-mt/termproof
uv run termproof run examples/generic --video
# artifacts: session.cast, final.svg, session.mp4, report.md
```

Or inspect `examples/artifacts/` — checked-in MP4s + SVGs + reports.

**Docs:**

- Quickstart: https://github.com/md-mt/termproof#quickstart
- Recipe packs: https://github.com/md-mt/termproof/blob/main/docs/recipe-packs.md
- Generic example: https://github.com/md-mt/termproof/tree/main/examples/generic
- Badge: `docs/verified-badge.md` — `Verified by TermProof`

**Offer:** I'll draft a recipe for one of your Ink examples (`examples/` in Ink repo or a real CLI like `pastel`/`ink-demo`) + GitHub Action snippet. If you adopt, we can list it in `docs/plugins.md` and ship an Ink-specific `wait_for_ink` step in future.

Thanks for Ink — made React CLI possible.

## Links

- https://github.com/md-mt/termproof
- https://github.com/md-mt/termproof#quickstart
- Badge + plugins directory: `docs/verified-badge.md`, `docs/plugins.md`

## Follow-up

- 1 bump after 4 days with concrete `termproof-ci-evidence` artifact link from a fork.
- If interested: co-author guide or `termproof-ink` helper plugin.
