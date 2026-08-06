# Case Study: <Adopter Name>

> Copy this file to `docs/case-studies/<slug>.md`, replace every
> `<placeholder>`, and register the slug in `docs/case-studies/_meta.json`.
> Remove this notice before publishing. The `scripts/validate_case_studies.py`
> gate will fail if any placeholder remains.

---
slug: <slug-kebab-case>
adopter: <Organization or team name>
category: <tui-framework | terminal-app | cli-tool>
repository: https://github.com/<org>/<repo>
consent: docs/case-studies/CONSENT.md#<slug>
published: YYYY-MM-DD
authors:
  - name: <Adopter contact name>
    role: <Role at adopter>
    contact: <email or GitHub handle>
  - name: <TermProof liaison>
    role: liaison
---

## Problem

<!-- 150+ words. What did the adopter ship that needed verifiable terminal
     evidence? What broke before TermProof (flaky screenshots, manual demos,
     no reviewer proof, regression escapes)? Name real symptoms, not generics. -->

<Describe the adopter's product, who uses it, and the specific pain point
that drove them to evidence-first verification. Quantify if you can:
release cadence, number of terminal flows, review bottlenecks.>

## Setup

<!-- 100+ words. Enough detail for a reader to reproduce. -->

- **Target command:** `<command the recipe drives, e.g. python -m my_app or ./my-tui>`
- **Repository:** <link to the adopter repo or the relevant sub-directory>
- **Terminal:** cols=100 rows=30 (or actual values), `TERM=xterm-256color`
- **Fixture mode:** <how nondeterminism is removed — seeded data, mocked network, clock pinning>
- **TermProof version:** <e.g. 0.2.1>
- **Dependencies:** <agg v1.9.0, ffmpeg, any special setup noted in the pack>

## Recipe

<!-- Must include a runnable recipe excerpt and a pointer to the full pack.
     The excerpt must be valid JSON with recipe_version, name, command, steps,
     and assertions. -->

Full pack: `<link to the recipe pack directory, e.g. .termproof/recipes/ or a
dedicated repo path>`

Example recipe excerpt:

```json
{
  "recipe_version": 1,
  "name": "<recipe-name>",
  "description": "<one-line intent>",
  "command": {
    "argv": ["<binary>", "<args>"],
    "pty": true
  },
  "cols": 100,
  "rows": 30,
  "timeout_seconds": 15,
  "steps": [
    {"action": "wait_for_text", "text": "<stable prompt>", "timeout_seconds": 5},
    {"action": "send_line", "text": "<user input>"},
    {"action": "wait_for_text", "text": "<expected output>", "timeout_seconds": 5}
  ],
  "assertions": [
    {"type": "screen_contains", "value": "<must-appear text>"},
    {"type": "output_not_contains", "value": "Traceback"}
  ]
}
```

Run it:

```bash
termproof run <pack-path> --video --out .termproof/runs
```

## CI integration

<!-- Show the actual CI snippet that runs TermProof and uploads evidence.
     This must be a real workflow the adopter runs, not aspirational YAML. -->

We verify on every pull request:

```yaml
# .github/workflows/verify.yml (or equivalent)
jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv run termproof run <pack-path> --video --video-fps 60 --out .termproof/runs
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: termproof-evidence
          path: .termproof/runs
```

Or the equivalent GitLab / CircleCI / Docker command — adapt to the adopter's
actual runner and link the workflow file.

## Results

<!-- 120+ words. What changed after adopting TermProof? Include at least one
     evidence link and one reviewer quote. -->

- **Before:** <qualitative or quantitative before-state>
- **After:** <qualitative or quantitative after-state — e.g. time-to-review,
  regressions caught, PR comment adoption, artifact views>
- **Evidence:**
  - Cast: `<link to session.cast — Actions artifact, release asset, or hosted URL>`
  - Screenshot: `<link to final.svg or final.png>`
  - Report: `<link to latest-report.md or per-run report.md>`
- **Quote:**

  > "<Verbatim quote from a reviewer, maintainer, or adopter lead. Attribute
  > by name and role. Consent for the quote is covered by CONSENT.md.>"

## Adoption notes

- **Time to first green run:** <e.g. 2 hours including fixture seeding>
- **Flake rate delta:** <e.g. 12% flaky manual screenshots -> 0 flaky TermProof runs over 30 PRs>
- **Reviewer workflow:** <how reviewers consume evidence — PR comment, artifact download, badge>
- **Alternatives considered:** <VHS, Playwright, expect-only, etc. — and why they were not sufficient>
- **Open gaps / wishlist:** <what the adopter still wants — optional, but honest>

---

*Verified by TermProof.* Add the badge:

```md
[![Verified by TermProof](https://img.shields.io/badge/verified%20by-TermProof-0a7a2e?style=flat-square)](https://github.com/md-mt/termproof)
```
