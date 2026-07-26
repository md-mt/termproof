# Outreach: Bubble Tea (Go)

> Status: DRAFT template — human sends after t_550ba351 approval
> Issue: #37
> Canonical links: see docs/launch/README.md

## Target

- **Framework:** Bubble Tea (Charmbracelet Go TUI)
- **Repo:** https://github.com/charmbracelet/bubbletea
- **Maintainers:** via GitHub Discussions / Charm Slack
- **Why relevant:** Gold standard for Go TUI, already has VHS for demos but no assertion/CI gate story

## Short Template

> I built TermProof (like Cypress for terminal apps) — JSON recipes drive your TUI in real PTY, record asciinema casts, replay to SVG screenshots + MP4 + Markdown report. Complements VHS for CI evidence. 60s demo: `termproof run examples/generic --video` → `session.mp4`. Repo https://github.com/md-mt/termproof. Happy to draft a recipe for a Bubble Tea example + GH Action. MIT.

## Long-form Version

Hi Bubble Tea team — long-time fan of Charm's stack (VHS, Gum, etc.).

I built TermProof (https://github.com/md-mt/termproof) to close the TUI verification gap: VHS is fantastic for demos, but not for assertions, CI gates, or reviewer evidence.

**TermProof in one line:** Recipe JSON → real PTY + asciinema cast → screenshots + MP4 + Markdown/JSON report. Upload as `termproof-ci-evidence` on every PR.

**Why Bubble Tea specifically:**

Bubble Tea apps are typically driven via `tea.Batch`/`tea.Msg` — TermProof drives the compiled binary in a real PTY, so it works with your existing `main.go` without code changes:

```json
{
  "name": "bubbletea list navigation",
  "command": {"argv": ["./my-bubbletea-app"], "pty": true},
  "steps": [
    {"action": "wait_for_text", "text": "My List", "timeout_seconds": 5},
    {"action": "press", "key": "j"},
    {"action": "wait_for_text", "text": "second item selected"},
    {"action": "send_line", "text": "q"}
  ],
  "assertions": [{"type": "screen_contains", "value": "second item"}]
}
```

**Compared to VHS:**

- VHS: Tape → GIF/MP4 demo, manual authoring, great for READMEs
- TermProof: Recipe → cast (source of truth) → screenshots + video + assertions + report, CI artifact, sticky PR comment with `latest-report.md`

They complement: use VHS for polished 10s README embeds, TermProof for verifiable CI gates. TermProof itself uses agg (like VHS does internally) for MP4 rendering via `agg --fps-cap 60` + `ffmpeg`.

**Go integration snippet (GH Action):**

```yaml
- name: Build app
  run: go build -o ./my-app ./cmd/my-app

- name: Install render deps
  run: |
    sudo apt-get update && sudo apt-get install -y ffmpeg
    if ! command -v agg >/dev/null 2>&1; then
      cargo install --locked --git https://github.com/asciinema/agg --tag v1.9.0
    fi

- name: Run TermProof
  run: |
    pip install termproof
    termproof run .termproof/recipes --video --out .termproof/ci

- name: Check evidence produced
  run: |
    if ! find .termproof/ci -type f -name session.mp4 -print -quit | grep -q .; then
      echo "ERROR: session.mp4 missing (agg or ffmpeg unavailable?)"
      exit 1
    fi

- name: Upload evidence
  uses: actions/upload-artifact@v4
  with:
    name: termproof-ci-evidence
    path: .termproof/ci
```

**60-second demo (no Go needed, Python generic):**

```bash
git clone https://github.com/md-mt/termproof
uv run termproof run examples/generic --video
```

Or inspect `examples/artifacts/` — pre-recorded MP4s, SVGs, Markdown reports.

**Docs:**

- Quickstart: https://github.com/md-mt/termproof#quickstart
- Recipe packs: https://github.com/md-mt/termproof/blob/main/docs/recipe-packs.md
- Generic example: https://github.com/md-mt/termproof/tree/main/examples/generic
- Future: `docs/guides/bubbletea.md` (Issue #24) — I can co-author

**Offer:** If you have a `examples/` Bubble Tea program you'd like verified, I'll open a draft PR against your repo showing `termproof` in CI with evidence artifact. Happy to maintain `termproof-bubbletea` helper if there's interest.

Thanks for Bubble Tea — best TUI DX out there.

## Links

- https://github.com/md-mt/termproof
- https://github.com/md-mt/termproof/blob/main/docs/recipe-packs.md
- https://github.com/md-mt/termproof/tree/main/examples/generic
- Badge: `docs/verified-badge.md`

## Follow-up

- 1 polite bump after 4 days with concrete recipe PR or link to `termproof` running against `charmbracelet/bubbles` example.
- If interested: plugin list entry + Pages demo.

