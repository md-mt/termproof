# Social Profiles: Handle Plan, Copy, Fallback

> Status: DRAFT — no accounts created from this PR. Human gate t_550ba351 must create/claim handles and publish.
> Issue: #38
> Related: #8 README badge, #16 Pages demo, #12 badge design

## Desired Handles (All lowercase check)

Primary handle: `@termproof`

- X/Twitter: `@termproof`
- Mastodon: `@termproof@fosstodon.org` (preferred instance: fosstodon.org or hachyderm.io — check availability)
- Bluesky: `@termproof.bsky.social` (or custom domain `@termproof.sh` / `@termproof.dev` if domain acquired later)
- GitHub org: `md-mt/termproof` (already has repo, could later create `termproof` org if MX moves)

Secondary: `@tui_verifier` (legacy from Issue #38) — must reserve and redirect. On X/Twitter and Mastodon, register `@tui_verifier` and point bio to TermProof. On Bluesky, underscores are not valid in ATProto handles; register `tui-verifier.bsky.social` or `tuiverifier.bsky.social` as a redirect placeholder.

### Availability Check Process (Human)

1. Search X/Twitter for `@termproof` — if taken but inactive 1+ year, consider `@termproof_dev`, `@termproofhq`, `@trytermproof`
2. Search mastodon.social global for `termproof` — prefer instance fosstodon.org → hachyderm.io → mastodon.social
3. Bluesky: check `bsky.app/profile/termproof.bsky.social` via API/handle resolution
4. If `@termproof` taken actively, escalate: try `@termproofhq`, `@trytermproof` (consistent across X/Twitter and Mastodon). For Bluesky, use only labels without underscores: `termproofhq.bsky.social`, `trytermproof.bsky.social` — `termproof_cli` and `termproof_io` are not valid ATProto handles.
5. Reserve all three to same fallback if primary unavailable anywhere — consistency > perfection

### Fallback Order

1. `@termproof` (preferred) — Bluesky: `termproof.bsky.social`
2. `@termproofhq` — Bluesky: `termproofhq.bsky.social`
3. `@trytermproof` — Bluesky: `trytermproof.bsky.social`
4. `@termproof_dev` — X/Twitter and Mastodon only (not valid on Bluesky)
5. `@termproof_io` — X/Twitter and Mastodon only (not valid on Bluesky)

Document final choice in `t_550ba351` gate comment and update this file post-creation in follow-up PR.

## Profile Copy

### Short Bio (160 chars max for X/Twitter)

Option A (technical, recommended):

> Evidence-first verification for TUI/terminal apps. Recipe → PTY + asciinema cast → screenshots, MP4, Markdown report. Like Cypress for TUIs.

Option B (benefit):

> Stop trusting TUI screenshots. Record the real session, replay to evidence, ship the proof. MIT. Python 3.11+.

Character counts: A = 140, B = 110. Use A for launch.

### Long Bio (for GitHub org, Mastodon, Bluesky profile extended)

> TermProof verifies terminal and TUI applications with replayable evidence. JSON recipes drive real PTY sessions, record asciinema-format casts, replay into SVG screenshots, text snapshots, 60-fps MP4 via agg+ffmpeg, and Markdown/JSON reports. Upload `.termproof/runs` as CI artifact — reviewers inspect proof, not just logs. Works with Textual, Bubble Tea, Ratatui, Ink, or any CLI. MIT. `pip install termproof`. (412 graphemes — Mastodon/GitHub; Bluesky 256-grapheme description limit requires the shorter variant below)

### Bluesky Description (≤256 graphemes)

> TermProof verifies TUI apps with replayable evidence. JSON recipes drive PTY, record casts, replay to screenshots + video. CI artifact for reviewer proof. Works with Textual, Bubble Tea, Ratatui, Ink. MIT. pip install termproof.

### GitHub Repo About Section (Keep Updated)

Current repo: https://github.com/md-mt/termproof

- Description: `Evidence-first verification for terminal and TUI applications — like Cypress for TUIs (cast, screenshots, video, report)`
- Website: `https://md-mt.github.io/termproof/` (once live) else repo URL
- Topics: `tui`, `terminal`, `testing`, `verification`, `asciinema`, `textual`, `bubbletea`, `ratatui`, `ink`, `cypress`, `playwright`, `evidence`, `ci`

### Avatar / Banner

- **Avatar:** Use `final.svg` from `examples/generic` rendered at 400x400, or simple icon: terminal with checkmark (shield-check). Flat dark bg #0a7a2e (from badge color) + white `>_ ✓`
- **Banner:** Collage of `examples/artifacts/` — show three panels: recipe JSON snippet, `final.svg`, `session.mp4` thumbnail, plus text "Recipe → PTY → Cast → Evidence"
- Files to generate: place under `docs/launch/social/assets/` (PNG export from SVG via `termproof` renderer) — create in follow-up after badge (#12) is finalized

No avatar/banner binary committed in this PR — vector source + instructions only, to keep PR reviewable without binaries. Human gate to publish final assets.

## Launch Announcement Templates

### X/Twitter (Thread, 6 tweets)

> **Tweet 1/6 (hook):**
> I built TermProof — like Cypress for terminal apps.
>
> Recipe JSON → real PTY + asciinema cast → screenshots, MP4, Markdown report. Upload as CI artifact so reviewers see proof, not just "trust me, works in my terminal".
>
> Demo in 60s:
> github.com/md-mt/termproof

> **Tweet 2/6 (what):**
> You ship a TUI (Textual, Bubble Tea, Ratatui, Ink, or plain curses).
>
> You write:
> {wait_for_text "dashboard>", send_line "open", wait_for_text "DASHBOARD READY"}
>
> TermProof drives real PTY, records cast, replays to evidence.

> **Tweet 3/6 (evidence):**
> Single run artifacts:
> - session.cast (asciinema v2, source of truth)
> - final.svg / final.txt
> - steps/ per-step screenshots
> - session.mp4 (60fps via agg+ffmpeg)
> - result.json + report.md
>
> Every PR publishes termproof-ci-evidence.

> **Tweet 4/6 (why not X):**
> Screenshots stale in one PR. expect no video/report. Playwright/Cypress can't drive PTY. VHS great for demos, not assertions/CI. asciinema alone no driving.
>
> TermProof: cast is source of truth for terminal output — screenshots, final SVG, video replay from same cast. Assertions evaluate from live terminal state; report aggregates results.

> **Tweet 5/6 (quickstart):**
> pip install termproof
> termproof init .termproof/recipes --name my-tui --command "my-tui"
> termproof run .termproof/recipes --video
>
> Generic demo (no Pi/API key):
> uv run termproof run examples/generic --video
>
> Artifacts checked in: examples/artifacts/

> **Tweet 6/6 (CTA + links):**
> MIT. Python 3.11+. Extensible via plugins in .termproof/config.yaml.
>
> Try it, open an issue with your TUI command.
>
> Repo: github.com/md-mt/termproof
> Verified by TermProof
> #TUI #Python #Rust #Go #CLI

### Mastodon (single post, 500 chars, plus thread)

> I built TermProof — evidence-first verification for terminal/TUI apps (Textual, Bubble Tea, Ratatui, Ink, any CLI).
>
> Recipe → real PTY + asciinema cast → SVG screenshots + MP4 + Markdown report. CI artifact termproof-ci-evidence so reviewers inspect proof.
>
> 60s demo: uv run termproof run examples/generic --video
>
> Repo: https://github.com/md-mt/termproof
> MIT. Plugins via .termproof/config.yaml. Happy to help write your first recipe!
>
> #TUI #Textual #Bubbletea #Ratatui #Ink #Python #Rust #Go #OpenSource #Testing

### Bluesky (300 chars per post, thread-friendly)

> Post 1: TermProof — like Cypress for terminal apps. Recipe JSON → real PTY + asciinema cast → screenshots, MP4, MD report. Upload as CI artifact.
> Post 2: For Textual, Bubble Tea, Ratatui, Ink, or any CLI. Portable demo: examples/generic runs without Pi/binary/API key. Artifacts in examples/artifacts/.
> Post 3: pip install termproof / MIT / plugins.yaml / repo github.com/md-mt/termproof — try it, I'll help write first recipe.

### LinkedIn (Long-form, professional)

> Most TUI testing stops at "screenshot in docs" — stale within one PR.
>
> I built TermProof to bring evidence-first verification to terminal apps (Textual, Bubble Tea, Ratatui, Ink).
>
> How it works:
> - Recipe JSON drives real PTY: wait_for_text, send_line, press
> - Records asciinema v2 cast (source of truth, diffable)
> - Replays cast to final.svg, per-step screenshots, 60fps MP4, report.md
> - Publishes termproof-ci-evidence on every PR
>
> Unlike VHS (great for README demos) or Playwright (browser-only), TermProof is built for assertions + CI gates + reviewer evidence.
>
> MIT, Python 3.11+, plugin registry for steps/assertions/session/video/reporter.
>
> 60-second demo: git clone md-mt/termproof + uv run termproof run examples/generic --video
>
> Repo: https://github.com/md-mt/termproof — feedback + recipes welcome.

## Content Calendar (Post-Merge, Human-Operated)

### Week 1 (Launch week)

- **Day 0:** Show HN post (see `show-hn.md`) — morning PT (8-10am)
- **Day 0 (+1h):** X/Twitter thread + Mastodon + Bluesky announcement linking HN
- **Day 1:** Dev.to / Hashnode cross-post (copy of Show HN with more screenshots)
- **Day 2-3:** Framework outreach DMs (one per day max, from `outreach/*.md`)
- **Day 5:** "Recipe of the Week" #1 — generic TUI workflow breakdown with SVG screenshots

### Week 2-4

- Weekly: Recipe of the Week thread (Textual, Bubble Tea, Ratatui, Ink — each framework)
- Every PR: Auto-share `termproof-ci-evidence` insights (run summary) via GitHub integration
- After guides ship (Issue #24): Announce `docs/guides/<framework>.md` with tag to maintainer

### Ongoing

- Monthly: Plugin spotlight from `docs/plugins.md`
- Badge adoption shout-outs (when projects add `Verified by TermProof`)
- Release announcements for v0.3+ (with evidence archive link)

## Do Not Do (From Issue #38)

- Do NOT auto-post via bots without human review.
- Do NOT follow/unfollow spam.
- Do NOT register handles impersonating other projects.
- Do NOT publish before v0.2.0 release tag and human gate approval.

## Tracking Post-Creation (Human Gate to Fill)

After accounts created via t_550ba351, record on Issue #38:

```md
- X/Twitter: https://x.com/<handle> (created 2026-08-XX, bio version A, avatar: generic final.svg PNG)
- Mastodon: https://fosstodon.org/@<handle> or https://hachyderm.io/@<handle>
- Bluesky: https://bsky.app/profile/<handle>.bsky.social
- Link aggregator updated: README, docs/launch/README.md canonical links
- First posts: HN https://news.ycombinator.com/item?id=XXXX + X thread https://x.com/... + Mastodon https://fosstodon.org/@.../...
- Fallback decision: @termproof taken? -> @fallback used, updated here.
```

Close Issue #38 only when actual profiles exist and first announcement posted — not on merge of this assets PR.
