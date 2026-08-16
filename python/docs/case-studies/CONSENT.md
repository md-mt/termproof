# Adopter consent record

> Human-gated. Each published case study MUST have a signed consent entry
> here before it counts toward RUST-030 / #35. The `scripts/validate_case_studies.py`
> gate fails if a slug listed in `_meta.json` has no corresponding entry.
>
> Consent is written, attributable, and on file. `pending` is not publishable.

## Instructions for the human owner

1. Contact the adopter team's designated representative (maintainer, tech lead, or media contact).
2. Share the draft case study (`docs/case-studies/<slug>.md`) and this consent text.
3. Collect explicit written consent (email, GitHub comment link, or signed statement — archive the source offline).
4. Fill in the row below. Leave no `TBD`s. The verifier will check that the quoted person matches the consent entry.
5. Update `_meta.json` for the published study: set `"consent": true` and `"status": "published"`.

## Consent text (send verbatim)

> I, the undersigned representative of **<Organization>**, consent for
> TermProof to publish the case study at `docs/case-studies/<slug>.md`
> under its current content, naming **<Organization>**, linking to
> **<repository>**, and quoting the attributed statements in the Results
> section. I confirm the statements and results are accurate and I have
> authority to consent on behalf of the team. I understand I may request
> withdrawal via a GitHub issue or email to the TermProof maintainers.

## Consent table

| Slug | Adopter | Representative | Title/Role | Consent date | Consent source (URL or on-file ref) | Quote approved | Withdrawal contact |
| --- | --- | --- | --- | --- | --- | --- | --- |
| _example_ | Example TUI Labs | — | — | — | — | — | — |
| <!-- replace the rows below with real adopters; delete the comment once filled --> |
| _placeholder-tui-framework_ | _TBD — TUI framework team_ | TBD | TBD | TBD | pending | no | TBD |
| _placeholder-terminal-app_ | _TBD — terminal application team_ | TBD | TBD | TBD | pending | no | TBD |
| _placeholder-cli-tool_ | _TBD — CLI tool team_ | TBD | TBD | TBD | pending | no | TBD |

## Status legend

- `pending` — outreach in progress, not yet publishable
- `granted` — written consent archived, study may publish
- `published` — study is live and linked
- `withdrawn` — adopter withdrew; remove the case study from `_meta.json` or revert to draft

## Audit notes

- Archive the raw consent artifact (email thread, GitHub comment URL, or signed PDF reference) outside this repo with access limited to maintainers.
- Do not paste personal email addresses directly into this file if the repo is public — use a GitHub handle or an on-file reference identifier.
- Three `granted`/`published` entries across distinct categories are required before RUST-030 can close. Two entries for the same org count as one.
