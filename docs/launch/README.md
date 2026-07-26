# TermProof v0.2 Launch Kit

Assets for the public launch of TermProof — the evidence-first verification harness for terminal and TUI applications.

**Status:** Draft assets for human review. External actions (posting, DMs, account creation) require explicit approval via `t_550ba351`.

## Contents

| Asset | Path | Related Issue | External Gate |
| --- | --- | --- | --- |
| Show HN draft | `docs/launch/show-hn.md` | #36 | Human posts on HN launch day |
| Outreach templates | `docs/launch/outreach/*.md` | #37 | Human sends DMs after release approval |
| Social profiles | `docs/launch/social/profiles.md` | #38 | Human creates accounts and posts |
| Launch checklist | `docs/launch/checklist.md` | #36 #37 #38 | Human-operated |
| Response/runbook | `docs/launch/runbook.md` | #36 #37 #38 | Human monitoring |

## Canonical Links

These URLs are referenced across outreach and social copy. Update after v0.2 release if paths change.

- **Repository:** `https://github.com/md-mt/termproof`
- **README / Quickstart:** `https://github.com/md-mt/termproof#quickstart`
- **Recipe packs:** `https://github.com/md-mt/termproof/blob/main/docs/recipe-packs.md`
- **Releases:** `https://github.com/md-mt/termproof/blob/main/docs/releases.md`
- **Generic demo recipe:** `https://github.com/md-mt/termproof/tree/main/examples/generic`
- **Pi workflow showcase:** `https://github.com/md-mt/termproof/tree/main/examples` (recipes `pi_workflow_*.recipe.json`)
- **60-second demo (local):** run `uv run termproof run examples/generic --video` then open `.termproof/runs/<id>/session.mp4` and `final.svg`
- **Tracked evidence artifacts:** `https://github.com/md-mt/termproof/tree/main/examples/artifacts` — e.g. `examples/artifacts/generic-tui-workflow/final.svg`, `pi-workflow-guarded-edit/session.mp4`, `latest-pi-workflows-report.md`
- **CI evidence artifact:** `termproof-ci-evidence` attached to every PR and `main` push (`https://github.com/md-mt/termproof/actions/workflows/ci.yml`)
- **Release evidence:** `termproof-release-evidence.tgz` on release tags (`https://github.com/md-mt/termproof/actions/workflows/release.yml`)
- **Demo site (when live):** `https://md-mt.github.io/termproof/` (Issue #16, `docs/plugins.md`, `docs/verified-badge.md`)
- **Integration guides (v0.3 target):** `docs/guides/textual.md`, `docs/guides/bubbletea.md`, `docs/guides/ratatui.md` per Issue #24 — link to recipe-packs doc until guides ship
- **Badge:** `docs/verified-badge.md`

### Demo script (60-second wow moment)

```bash
uv run termproof run examples/generic --video --out .termproof/demo
# artifacts: .termproof/demo/<run-id>/final.svg, session.mp4, report.md, result.json
```

For a more complex multi-turn agent flow:

```bash
uv run termproof run examples/pi_workflow_guarded_edit.recipe.json --video
```

The demo is intentionally portable — no Pi binary or API key required for `examples/generic`.

## Integration Docs Reference

Current integration surface until `docs/guides/` lands (Issue #24):

- Creating a recipe pack: `termproof init .termproof/recipes --name my-tui --command "my-tui"`
- Running with evidence: `termproof run .termproof/recipes --video --out .termproof/ci`
- GitHub Actions snippet: `README.md` CI section + `.github/workflows/ci.yml`
- Plugin system: `docs/plugins.md` + `docs/recipe-packs.md`

When referencing integration guides in outreach, link to:

1. `https://github.com/md-mt/termproof#quickstart`
2. `https://github.com/md-mt/termproof/blob/main/docs/recipe-packs.md`
3. `https://github.com/md-mt/termproof/tree/main/examples/generic` — minimal working example
4. For framework-specific questions, point to upcoming `docs/guides/<framework>.md` and offer to co-author a recipe.

## Usage Policy

- **Do not** create accounts, send DMs, or publish posts from this branch. Those are explicit human-operated external actions after release approval (see `t_550ba351`).
- **Do** iterate on copy in this PR via review comments.
- **Do** reference this directory from issues #36, #37, #38 when commenting on remaining gates.

## Validation

Run:

```bash
uv run python -m unittest discover -s tests -k launch
```

This checks that all referenced files exist, required sections are present, canonical links are valid paths or https URLs, and no placeholder social handle is marked as created.

## After Merge

1. Merge this PR via reviewed squash (requires verifier approval in `t_686b079e` and merge gate `t_cbf515a4`).
2. Complete v0.2 release (lanes `t_2847cc1d`, `t_55ca7b25`, `t_164fa418`).
3. Human gate `t_550ba351` authorizes actual external actions — record URLs on Issues #36-#38.
4. Issues #36-#38 close only when their actual external action is complete; otherwise comment with merged asset PR and remaining gate.
