# Case studies

Evidence-first verification in the wild. Each study is a real adopter that
ships with TermProof in CI — not a synthetic demo.

## Why this page exists

TermProof is not credible until external teams attest that it works for their
TUI and that they consented to be named, linked, and quoted. This section is
human-gated: the scaffolding and validator are engineering; the consent and
recruitment are human work under [RUST-030](https://github.com/md-mt/termproof/issues/123) / [#35](https://github.com/md-mt/termproof/issues/35).

Placeholders are drafts. **Fabricated adopters are a verifier failure.**

## Required coverage

Before RUST-030 closes, three published, consented studies across distinct
categories:

| Category | Slug | Status |
| --- | --- | --- |
| TUI framework | `placeholder-tui-framework` | draft |
| Terminal app | `placeholder-terminal-app` | draft |
| CLI tool | `placeholder-cli-tool` | draft |

Each study covers: **Problem -> Setup -> Recipe -> CI integration -> Results**.

## Index

<!-- keep in sync with docs/case-studies/_meta.json -->
- _Placeholder: TUI framework_ — draft, no consent yet
- _Placeholder: Terminal application_ — draft, no consent yet
- _Placeholder: CLI tool_ — draft, no consent yet

Published studies will appear here as they are completed. Until then, see the
authoritative tracker in [`docs/case-studies/`](https://github.com/md-mt/termproof/tree/main/docs/case-studies)
and the validator:

```bash
python3 scripts/validate_case_studies.py
```

## How to publish

1. Copy `docs/case-studies/TEMPLATE.md` to `docs/case-studies/<slug>.md`.
2. Fill every required section (Problem, Setup, Recipe, CI integration, Results).
3. Record written consent in `docs/case-studies/CONSENT.md`.
4. Register the entry in `docs/case-studies/_meta.json`.
5. Add the file here as `docs-site/case-studies/<slug>.md` (VitePress route is `/case-studies/<slug>`).

## Failure modes the validator catches

- Missing or placeholder content (`<slug>`, `lorem`, `TODO`)
- Consent not marked `granted`/`published`
- Duplicate adopter category counted twice
- Results section without an evidence link or quote
