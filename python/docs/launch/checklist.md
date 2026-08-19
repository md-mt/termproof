# Launch Checklist: TermProof v0.2

> **Historical. This plan was never executed at `0.2.0`.** Every `0.2.0` below
> is what the plan said, not what happened. The `v0.2.0` tag and GitHub release
> exist, but nothing was ever published to PyPI under that number — PyPI
> carries `0.3.0`, `0.3.3` and `0.3.4`, the first of them uploaded once
> `ENABLE_PYPI` was turned on in August 2026. So the `pip install
> termproof==0.2.0` smoke below cannot succeed, and never could. Reuse the
> shape of this checklist, not its version numbers.
>
> Status: DRAFT checklist for human execution
> Issues: #36 Show HN, #37 Outreach, #38 Social
> Human gate: t_550ba351 blocks actual publish/outreach/account creation
> Release lanes: t_2847cc1d (release prep), t_55ca7b25 (release review), t_164fa418 (publish)

This checklist is the single source for launch readiness. Check items in order; do not skip gates.

## Pre-Requisites (Before This PR's Verification)

- [x] Rename complete: PR #42 merged as 99d9631, issue #40 closed, feature branch deleted (gate t_768cdc68 done)
- [ ] v0.2 implementation lanes merged:
  - [ ] t_1b2bfea8 docs, contributor, badge, Pages assets
  - [ ] t_ed99c9ef core UX: demo, wait_for_regex, JUnit
  - [ ] t_abde3e3e plugin template
  - [ ] t_348e370d CI + bundled agg distribution
- [ ] Verifier gate t_686b079e passes — every v0.2 PR approved on current head + CI green
- [ ] Merge gate t_cbf515a4 done — squash merges verified, main head checked

## This PR (t_f05ac4a7: launch kit)

- [ ] Branch `wt/issues-36-37-38-launch-kit-v02` based on current origin/main (99d9631)
- [ ] Assets present:
  - [ ] `docs/launch/README.md` — canonical links to demo + integration docs
  - [ ] `docs/launch/show-hn.md` — TermProof retitled, with companion comment + links
  - [ ] `docs/launch/outreach/textual.md` — Textual template short + long + CI snippet
  - [ ] `docs/launch/outreach/bubbletea.md` — Bubble Tea + VHS complement story
  - [ ] `docs/launch/outreach/ratatui.md` — Ratatui + buffer snapshot complement
  - [ ] `docs/launch/outreach/ink.md` — Ink + ink-testing-library complement
  - [ ] `docs/launch/outreach/README.md` — common template + tracking
  - [ ] `docs/launch/social/profiles.md` — handle plan + fallback + profile copy
  - [ ] `docs/launch/checklist.md` — this file
  - [ ] `docs/launch/runbook.md` — monitoring + response
  - [ ] `tests/test_launch_kit.py` — validation for assets
- [ ] Tests pass:
  - [ ] `uv run python -m unittest discover -s tests -k launch` — 0 failures
  - [ ] Full suite: `uv run python -m unittest discover -s tests` — no regressions
  - [ ] No placeholder handle marked as created, no actual DMs sent
- [ ] Commit + push to `wt/issues-36-37-38-launch-kit-v02` with conventional commit
- [ ] PR created via `gh pr create --title ... --body ... --draft` linking Issues #36 #37 #38
- [ ] PR body links canonical demo + integration docs + test results
- [ ] Reviewer: `mw-ding` approval on exact head (no auto-merge)
- [ ] CI green: the `Build, verify TUI evidence and publish it` check on `CI (Python)`

## Release Prep (t_2847cc1d + t_55ca7b25)

- [ ] Version bumped in `pyproject.toml` to `0.2.0`
- [ ] `uv build` + wheel smoke: `termproof --help` + `termproof run examples/generic --video` produces `session.cast`, `final.svg`, `session.mp4` < 60s
- [ ] Release notes draft includes: rename note (TUI Verifier → TermProof), quickstart, comparison table ref, evidence artifact link, badge
- [ ] GitHub Pages: `https://md-mt.github.io/termproof/` live with sample evidence (Issue #16) — or note in release that it's pending
- [ ] README polished with comparison table, animated demo, CI snippet (Issue #8, lane t_1b2bfea8) — or at minimum current README's 3-command quickstart verified
- [ ] Release workflow dry-run: `gh workflow run release.yml -f ...` if available

## Publish (t_164fa418)

- [ ] Tag `v0.2.0` pushed
- [ ] Release action: units tests + build + generic + Pi deterministic E2E + release evidence archive `termproof-release-evidence.tgz`
- [ ] Release body contains `latest-report.md` + evidence archive link
- [ ] PyPI trusted publishing (if configured) — `pip install termproof==0.2.0` smoke

## Human Gate (t_550ba351) — Do Not Automate

### Handle Registration (#38)

- [ ] Check availability for `@termproof` on X/Twitter, Mastodon (fosstodon.org/hachyderm.io), Bluesky
- [ ] Decide fallback per `docs/launch/social/profiles.md` fallback order
- [ ] Register/redirect `@tui_verifier` (legacy handle from Issue #38): reserve on X/Twitter and Mastodon; on Bluesky use a valid ATProto label (e.g. `tui-verifier.bsky.social` or `tuiverifier.bsky.social`) since underscores are not allowed
- [ ] Create accounts with bio version A + avatar from `final.svg` PNG export
- [ ] Record URLs on Issue #38 comment: X, Mastodon, Bluesky profile links
- [ ] Link aggregator: update README "Community" or socials — if none, add issue to update README post-launch

### Show HN (#36)

- [ ] Time: Tuesday-Thursday 8-10am PT (HN best traffic)
- [ ] Title final: `Show HN: TermProof – Verify terminal apps with cast, screenshots, video` (or variant from `show-hn.md`)
- [ ] Body: copy from `show-hn.md` draft body, verify all links alive (repo, quickstart, recipe-packs, generic example, artifacts)
- [ ] Submit: https://news.ycombinator.com/submit
- [ ] Immediately post companion comment from `show-hn.md`
- [ ] Cross-link: X/Twitter thread within 1h, referencing HN link

### Outreach (#37)

- [ ] Wait 24h after Show HN to avoid spam perception
- [ ] For each framework (Textual, Bubble Tea, Ratatui, Ink), max 1 outreach per day:
  - [ ] Pick specific example from their repo to reference
  - [ ] Personalize first line
  - [ ] Short template first, offer long-form if they reply
  - [ ] Do not open unsolicited PRs before chat
- [ ] Record every send on Issue #37 with link + date + channel
- [ ] Track responses per `outreach/README.md` handling guide

### Social Posts (#38)

- [ ] X/Twitter thread (6 tweets) from `profiles.md` + link to HN post
- [ ] Mastodon single + thread
- [ ] Bluesky 3-post thread
- [ ] Optional: LinkedIn long-form + Dev.to cross-post (Day 1-2)
- [ ] Record post URLs on Issue #38

## Post-Launch Monitoring (Runbook)

- [ ] HN — monitor every 15 min first 2h, hourly Day 1, per `docs/launch/runbook.md`
- [ ] X/Twitter replies — respond same day, technical depth
- [ ] GitHub issues — triage "tried TermProof" feedback into docs update PR
- [ ] Outreach replies — co-author guides per Issue #24 if interested

## Close Criteria for Issues

- **#36 Show HN:** Closed only when HN post URL exists + companion comment posted + monitoring first 24h done. Otherwise comment on #36 with merged launch-kit PR URL + `t_550ba351` gate remaining.
- **#37 Outreach:** Closed only when all 4 frameworks contacted AND responses tracked (interested/not now) with links. Otherwise comment with launch-kit PR + remaining sends.
- **#38 Social:** Closed only when profiles created (URLs recorded) + first announcement posted + legacy `@tui_verifier` registered/redirected. Development update, screenshot post, and first "Recipe of the Week" are required per #38 — keep #38 open until these are delivered, or create linked follow-up issues (e.g. #38-continued-1, #38-continued-2) and update #38 description with the agreed split before closing. Otherwise comment with launch-kit PR + handle decision.

## Rollback / Contingency

- If HN post flagged/dead: delete/don't repost same day, revise title variant (2nd in list), wait 24h
- If X handle @termproof taken actively: use fallback order, update `profiles.md` in follow-up PR, keep consistent across platforms
- If release workflow fails: do not proceed to Show HN — fix release lane first, then re-enter checklist
- If demo MP4 >60s: re-run `examples/generic` with default timeouts, check `session.mp4` duration via `ffprobe`, trim recipe steps if needed (current generic is ~15s expected)

## Final Gate

- [ ] Human approves with comment on `t_550ba351`: "Authorize external actions — release v0.2.0 published, launch kit merged, handles decided"
- [ ] All three issues updated with asset PR link + actual external URLs when done
- [ ] Swarm ledger updated via crew-trivial lane if applicable

