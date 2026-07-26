# Outreach: Ratatui (Rust)

> Status: DRAFT template — human sends after t_550ba351 approval
> Issue: #37
> Canonical links: see docs/launch/README.md

## Target

- **Framework:** Ratatui (Rust TUI, tui-rs successor)
- **Repo:** https://github.com/ratatui/ratatui
- **Maintainers:** via GitHub Discussions / Discord
- **Why relevant:** Largest Rust TUI ecosystem, testing relies on buffer snapshots — TermProof adds real PTY + cast evidence + video

## Short Template

> Built TermProof — evidence-first TUI verifier (Cypress-for-terminal). Drives real PTY, records asciinema cast, replays to SVG+MP4+MD report. Catches Ratatui regressions that buffer asserts miss (pty, resizing). 60s demo: `termproof run examples/generic --video`. Repo https://github.com/md-mt/termproof. Happy to wire a recipe for one of your examples + GH Action.

## Long-form Version

Hi Ratatui team — Ratatui + frameworks built on it (e.g. `tui-widgets`, `gitui`-style apps) commonly test via `Buffer::assert_buffer` snapshots. That's great for widget unit tests, but misses real terminal behavior: PTY sizes, double-render, input sequences, resize handling, actual ANSI.

TermProof (https://github.com/md-mt/termproof) bridges that:

- Recipe: `wait_for_text`, `press`, `send_line`, `sleep`, etc. — drives real PTY
- Records asciinema v2 cast (source of truth, diffable)
- Replays cast into `final.svg`/`final.txt`, per-step screenshots, optional 60-fps MP4 via agg+ffmpeg, `report.md` + `result.json`
- CI artifact `termproof-ci-evidence` + sticky PR comment

**For a Ratatui binary:**

```json
{
  "name": "ratatui explorer smoke",
  "command": {"argv": ["./target/debug/my-ratatui-app"], "pty": true},
  "cols": 120,
  "rows": 30,
  "steps": [
    {"name": "wait for list", "action": "wait_for_text", "text": "Files", "timeout_seconds": 10},
    {"name": "down", "action": "press", "key": "j"},
    {"name": "wait for selection", "action": "wait_for_text", "text": "selected: 2", "timeout_seconds": 5},
    {"name": "quit", "action": "press", "key": "q"}
  ],
  "assertions": [
    {"type": "screen_contains", "value": "Files"},
    {"type": "exit_code", "value": 0}
  ]
}
```

**Rust CI snippet:**

```yaml
- uses: cargo install --locked --git https://github.com/asciinema/agg --tag v1.9.0
  if: "! command -v agg"
- run: sudo apt-get update && sudo apt-get install -y ffmpeg

- name: Build TUI
  run: cargo build --bin my-ratatui-app

- name: Verify with TermProof
  run: |
    pipx install termproof
    termproof run .termproof/recipes --video --out .termproof/ci

- uses: actions/upload-artifact@v4
  with:
    name: termproof-ci-evidence
    path: .termproof/ci
```

**Why TermProof + Ratatui buffer tests:**

- Buffer snapshots: pixel-perfect widget assertions, fast, no PTY
- TermProof: real terminal evidence, cross-run diffable cast, video for reviewers, catches resize/input regressions buffer tests miss

Use both: buffer tests for unit, TermProof for integration + reviewer evidence.

**60-second demo:**

```bash
git clone https://github.com/md-mt/termproof
uv run termproof run examples/generic --video
# -> session.mp4 + final.svg + report.md
```

Or browse checked-in evidence: `examples/artifacts/` (MP4s, SVGs, reports from Pi workflow guard/edit flows).

**Docs:**

- https://github.com/md-mt/termproof#quickstart
- https://github.com/md-mt/termproof/blob/main/docs/recipe-packs.md
- https://github.com/md-mt/termproof/tree/main/examples/generic
- Future: `docs/guides/ratatui.md` per #24 — can co-author

**Offer:** I'll draft a recipe pack for `ratatui/examples/demo` or `demo2` and show a GitHub Actions run with evidence artifact. If you adopt, we can list Ratatui projects in `docs/plugins.md` + badge program (`docs/verified-badge.md`).

Thanks for Ratatui — best TUI testing foundations in Rust.

## Links

- https://github.com/md-mt/termproof
- Badge + plugins: `docs/verified-badge.md`, `docs/plugins.md`

## Follow-up

- Bump after 5 days with concrete CI run link.
- If interested: co-author guide + ratatui-specific `wait_for_rect` step plugin.

