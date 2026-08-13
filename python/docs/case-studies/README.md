# Case studies

> Human-gated publication track for RUST-030 / #35. Engineering owns the
> scaffolding and pipeline (this directory); the human owner secures real
> adopter consent. **Fabricated, lorem, or invented adopters are a verifier
> failure.**

## What lives here

| File | Purpose |
| --- | --- |
| `TEMPLATE.md` | Required structure for every case study |
| `CONSENT.md` | Consent record — one section per adopter |
| `_meta.json` | Machine-readable index consumed by `scripts/validate_case_studies.py` and the docs site |
| `<slug>.md` | One per adopter (e.g. `textual-dashboard.md`). Must be listed in `_meta.json`. |

## Required coverage

Three distinct adopter categories before RUST-030 can close:

1. **TUI framework team** (Textual, Bubble Tea, or Ratatui)
2. **Terminal application team** (any app that ships a terminal UI)
3. **CLI tool team** (command-line tooling or SDK)

Each case study must include all of:

- **Problem** — what the team shipped that needed verifiable terminal evidence
- **Setup** — target command, terminal dimensions, fixture mode, repository link
- **Recipe** — at least one runnable `*.recipe.json` excerpt and where the full pack lives
- **CI integration** — GitHub Action / GitLab / CircleCI / Docker snippet actually running `termproof run`
- **Results** — before/after, evidence links (cast/screenshots/report), and reviewer quote

## Publication checklist

Engineering gate (CI enforces):

- [ ] Each `*.md` listed in `_meta.json` exists and passes `scripts/validate_case_studies.py`
- [ ] Every case study has all five required sections with minimum lengths
- [ ] `CONSENT.md` has a signed entry for every slug
- [ ] No file contains `lorem`, `example.com` placeholder links, or `TODO` markers
- [ ] `docs-site` navigation includes the case study

Human gate (verifier checks out-of-band):

- [ ] Each adopter is a real external team with an attributable repo/org/person
- [ ] Each adopter gave explicit written consent to be named and quoted
- [ ] Evidence artifacts are publicly reachable (Actions artifact, `examples/artifacts/`, or hosted URL)

## Quick start

```bash
# 1. copy the template
cp docs/case-studies/TEMPLATE.md docs/case-studies/my-adopter.md

# 2. fill in every section, then register it
# edit docs/case-studies/_meta.json  -> add an entry to "case_studies"

# 3. record consent
# edit docs/case-studies/CONSENT.md  -> add a row for your adopter

# 4. validate
python3 scripts/validate_case_studies.py

# 5. preview the docs site
npm run --prefix docs-site docs:dev
# open http://localhost:5173/case-studies/
```

## Failure modes the verifier rejects

- Fewer than three published studies
- Missing consent entry or unsigned placeholder consent
- Two studies from the same adopter/category counted separately
- Recipe that never ran or CI snippet that cannot be matched to `.github/workflows/ci.yml` or equivalent
- Results section with no evidence link or with a stock photo instead of `session.cast`/`final.svg`/`report.md`
