# Launch Runbook: Response & Monitoring

> Draft for v0.2 launch of TermProof. Human operates monitoring after human gate t_550ba351 approval.
> Issues: #36 (HN), #37 (outreach), #38 (social). See also `docs/launch/checklist.md` and `docs/launch/show-hn.md`.

## Overview

TermProof public launch touchpoints:

1. **HN Show** — high visibility, technical audience, rapid comments
2. **X/Twitter + Mastodon + Bluesky** — announcement threads, retweets, replies
3. **Framework maintainer DMs** — Textual, Bubble Tea, Ratatui, Ink — one per day
4. **GitHub repo** — stars, issues, PRs, discussions

Goal: respond with technical depth, capture feedback, convert "tried it" into guides or plugins, avoid spam.

## Pre-Launch Setup (Before Posting)

- [ ] Subscribe to notifications:
  - HN: https://news.ycombinator.com/submitted?id=<user> + comment reply notifier (hacker news API or https://hnrss.github.io/)
  - GitHub: Watch repo `md-mt/termproof` for issues + PRs (email + Slack if configured)
  - X/Twitter: enable notifications for @termproof mentions
- [ ] Prepare local evidence:
  - Latest `termproof-ci-evidence` artifact from `origin/main` CI run
  - `examples/artifacts/` browse — have open links to SVGs + MP4s + reports ready to paste
  - `uv run termproof run examples/generic --video --out .termproof/demo` output — ensure <60s MP4 duration via `ffprobe .termproof/demo/*/session.mp4`; also fail preflight if `session.mp4` is absent (`termproof` silently skips video when `agg` is unavailable)
- [ ] Pre-draft snippets (keep in clipboard manager):
  - Quickstart 3 commands
  - Recipe pack minimal JSON
  - CI YAML snippet
  - Plugin config.yaml example
  - Badge markdown

## Show HN Day — Timeline

### T+0 Posting (8-10am PT, Tuesday-Thursday ideal)

- Post per `docs/launch/show-hn.md` — title + body verified links alive
- Immediately post companion comment from same doc
- Verify post appears on https://news.ycombinator.com/newest — if buried, do NOT repost immediately (HN flags dedupes)
- Share on X/Twitter thread linking HN within 1h (not before HN, to avoid flagging)

### T+0 to T+2h — Intensively Monitor (Every 15 min)

Channels to check:

- HN post comments: https://news.ycombinator.com/item?id=<id>
- X/Twitter replies & mentions
- GitHub issues — new "tried TermProof" or bug reports

Response guidelines:

- **Technical questions** (how does X work?): Answer with code + link to docs/recipe-packs.md or examples/generic + offer to review their recipe
- **Why not Y?** (VHS, expect, Playwright): Acknowledge Y's strength, explain TermProof's complement, table from README — avoid bashing
- **Does it work with Z framework?** Yes, product-agnostic — recipe drives binary in PTY — link to framework-specific outreach doc + offer to co-author guide (#24)
- **Bundle size / agg / ffmpeg**: Explain agg binary is Rust (cargo install) + ffmpeg apt, bundled wheel is Issue #39 — current CI installs agg + ffmpeg, release tgz includes evidence
- **Pricing / license**: MIT, no telemetry, local-first
- **Negative / criticism:** Thank, ask for specific gap, open issue if actionable — don't argue

Tone: concise, evidence-driven, no marketing fluff, show `session.cast` → replay pipeline.

Example reply template:

> Good Q — TermProof records the real PTY via asciinema (source of truth) then replays to `final.svg`, per-step screenshots, MP4 via agg+ffmpeg, and `report.md`. So reviewers inspect `termproof-ci-evidence` artifact, not just logs. Your [Textual/Bubble Tea/Ratatui/Ink] app would be:
> ```json
> { recipe snippet }
> ```
> Happy to review a recipe if you share your command + expected flow — `examples/generic` is a minimal starting point: https://github.com/md-mt/termproof/tree/main/examples/generic

### T+2h to T+24h — Hourly

- Same checklist, longer interval
- Capture FAQs in `docs/launch/runbook.md` or `docs/recipe-packs.md` issues
- If HN drops off front/new, let it — do not post to other aggregators until Day 1+

### Day 1-7 — Daily

- Morning check: HN replies, X mentions, GitHub issues
- If maintainer DM reply from `outreach/*` templates: engage per Handling in `outreach/README.md`
- Track "Converted" count: users who starred + opened issue with recipe, or adopted badge

## Outreach Monitoring (#37)

Per-framework DMs (max 1/day) — after human gate:

- Textual: Monitor GitHub Discussions https://github.com/Textualize/textual/discussions + Twitter DM
- Bubble Tea: GitHub Discussions + Charm Slack if invited
- Ratatui: GitHub Discussions + Discord
- Ink: GitHub Discussions

Tracking (update Issue #37):

```
2026-08-10 Textual — Sent GH Discussion https://... — short + long from docs/launch/outreach/textual.md — offered calculator recipe — follow-up 2026-08-15
```

Response buckets:

- **Interested →** schedule 30-min pairing, co-author `docs/guides/<framework>.md` (Issue #24), add to `docs/plugins.md` when plugin exists
- **Not now →** thank, leave badge + link, ask if ok to ping after v0.3 guides ship
- **No reply →** one polite bump after 5 days with concrete evidence artifact, then close thread

Never argue, never claim endorsement.

## Social Monitoring (#38)

X/Twitter:

- Track `#termproof`, `#tui`, `#terminal` mentions via search
- Respond within same day — technical depth over marketing
- Retweet community evidence packs (user posts `final.svg` or `session.mp4`)

Mastodon/Bluesky:

- Similar cadence, lighter volume expected
- Boost/repost community adoptions with badge

LinkedIn/Dev.to (if cross-posted):

- Respond to comments within 24h, link back to repo + comparison table

## GitHub Issues & PRs — Triage Playbook

| Label | Handling |
| --- | --- |
| `I tried TermProof with <framework>` | Thank, ask for recipe pack + `termproof-ci-evidence` link, invite to `docs/plugins.md` + badge |
| `Bug: <step / renderer>` | Repro via `termproof run <recipe> --video --out /tmp/repro`, check `session.cast`, open fix PR |
| `Feature: <wait_for_regex / plugin>` | Link to existing issue (#14 JUnit etc.), mention plugin extensibility via `.termproof/config.yaml` |
| `Question: docs` | Answer + PR to update `docs/recipe-packs.md` or `README.md` in same week |
| `Comparison: why not X` | Add to README comparison table if missing, link to table |

Add `area:community` label for adoption stories.

## Metrics (Collect Manually Week 1)

- GitHub stars Day 0, Day 1, Day 7
- HN points + comment count + front page time (if any)
- X impressions + profile visits (Twitter analytics if available)
- Framework outreach responses: 4 sent / X interested / Y plugin PRs / Z guides co-authored
- Issues opened by new users / PRs with `Verified by TermProof` badge
- Evidence downloads: `termproof-ci-evidence` artifact download count from latest CI run + release artifact downloads

Record in `docs/launch/checklist.md` final section or swarm ledger — do not embed in code.

## Failure Modes & Runbook

### HN post flagged/dead

- Symptoms: post not in `newest`, or flagged [dead]
- Action: do not repost same day. Read comments if visible via HN API. Revise title variant (second in list from `show-hn.md`), wait 24h, repost with tweaked intro (more technical, fewer claims). Notify team via issue comment.

### X handle @termproof taken actively

- Symptoms: search shows active account tweeting about unrelated product
- Action: use fallback order from `social/profiles.md`, update `profiles.md` in follow-up PR, keep consistent across platforms. Do not attempt to purchase handle in launch week.

### Release workflow failed, no v0.2.0 tag

- Symptoms: `gh release view v0.2.0` fails
- Action: Do not proceed to Show HN or social posts. Fix release lanes t_2847cc1d / t_55ca7b25, then re-enter `checklist.md`. Postpone social.

### Demo MP4 >60s or generic recipe flaky

- Symptoms: `session.mp4` duration >60s, or `termproof run examples/generic --video` times out
- Action: Check `tests/test_examples.py` + run `examples/generic/generic_tui.py` manually, examine `session.cast` via `asciinema play`. If flaky, reduce timeouts or simplify recipe temporarily, open issue. For MP4 >60s, acceptable — generic is ~15s normally, Pi workflow videos may be longer; ensure short clip highlighted in Show HN as `examples/generic`.

### Maintainer replies negatively ("spam")

- Symptoms: "Please don't DM" or similar
- Action: Apologize once, leave repo link, do not continue. Note in Issue #37 as "not interested — no further outreach". Do not argue.

## After Week 1 — Transition to Normal Operations

- Convert this runbook into lightweight `docs/community.md` or integrate into `docs/recipe-packs.md` + `docs/plugins.md`
- Archive launch kit thread to GitHub Discussion "TermProof v0.2 Launch Retrospective" — capture what worked, what was missed
- Update `docs/launch/README.md` canonical links after Pages demo live (#16)
- Open follow-up tasks: actual social handle URLs, guide co-authoring, badge adoptions

## Quick Reference Links (Paste-Ready)

- Repo: https://github.com/md-mt/termproof
- Quickstart: https://github.com/md-mt/termproof#quickstart
- Recipe packs: https://github.com/md-mt/termproof/blob/main/docs/recipe-packs.md
- Generic demo: https://github.com/md-mt/termproof/tree/main/examples/generic
- Generic recipe JSON: https://github.com/md-mt/termproof/blob/main/examples/generic/generic_tui.recipe.json
- Artifacts dir: https://github.com/md-mt/termproof/tree/main/examples/artifacts
- CI workflow: https://github.com/md-mt/termproof/actions/workflows/ci.yml
- Release workflow: https://github.com/md-mt/termproof/actions/workflows/release.yml
- Badge: `[![Verified by TermProof](https://img.shields.io/badge/verified%20by-TermProof-0a7a2e?style=flat-square)](https://github.com/md-mt/termproof)`
- Plugins: https://github.com/md-mt/termproof/blob/main/docs/plugins.md (once t_1b2bfea8 merges)
- Verified badge guide: https://github.com/md-mt/termproof/blob/main/docs/verified-badge.md (once t_1b2bfea8 merges)
- Config example:
  ```yaml
  # .termproof/config.yaml
  steps:
    wait_for_regex: my_org.steps:WaitForRegex
  assertions:
    json_schema: my_org.assertions:JsonSchema
  reporters:
    junit_xml: my_org.reporters:JunitReporter
  ```

## No-Exec Guardrail

This file must not contain secrets, tokens, or real DM URLs. All external actions are human-operated after `t_550ba351`. This PR only ships templates + instructions.
