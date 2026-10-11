# TermProof Repository Governance

Status: Active
Owner: termproof maintainers (`@md-mt`)
Scope: the `md-mt/termproof` GitHub repository — both implementations
Baseline date: 2026-08-16 (main at `e6efcb5`)

**The baseline in section 1 was verified against `md-mt/termproof-rust`, the
predecessor repository, before the two implementations were consolidated.** It
has not been re-verified against this repository, so read it as the settings
this document argued for rather than as the settings that are live. The
settings-change task re-runs the audit commands in section 8 here and records
the before/after. The one exception is the ruleset: the *Rulesets* row of
section 1, the "Live today" paragraphs of section 5 and section 6.1 were
read from this repository's API on 2026-10-11.

This document records the repository's GitHub governance: metadata,
vulnerability settings, merge policy, the required CI checks by their stable
names, the `main` ruleset (live and intended), the emergency bypass, and the audit
procedure. It is the review trail for the settings change that follows it —
the external GitHub settings are deliberately **not** changed by this
document's PR. When the settings are applied, the exact before/after state is
recorded there, per the audit note in the open-source polish plan.

This document governs the GitHub repository surface. Code policy — formatting,
lints, errors, tracing, dependencies, features, unsafe code — is
[`docs/engineering-baseline.md`](engineering-baseline.md).

## 1. Baseline — current live state (verified 2026-10-10)

Verified against the live repository with the GitHub API/GraphQL, not assumed.
Every row was re-verified on 2026-10-10; the original baseline was taken on
2026-08-16:

| Setting | Live value |
|---|---|
| Visibility / default branch | public, `main` |
| Description | "Evidence-first verification for TUI and terminal applications" |
| Homepage | `https://md-mt.github.io/termproof/` |
| Topics | `asciinema`, `bubbletea`, `ci`, `cypress`, `evidence`, `ink`, `playwright`, `ratatui`, `terminal`, `testing`, `textual`, `tui`, `verification` |
| Issues / Wiki / Projects / Discussions | enabled / enabled / enabled / disabled |
| Merge methods | squash and rebase allowed, merge commits **disabled**; delete branch on merge **on**; auto-merge off; "always suggest updating pull request branches" off; squash commit title `COMMIT_OR_PR_TITLE`, message `COMMIT_MESSAGES` |
| Rulesets | one — `main: require CI (Rust) result + Oracle freshness result` (id `24859051`), enforcement active, targeting the default branch, requiring the two status checks `CI (Rust) result` and `Oracle freshness result`; admin-role bypass. Re-verified against `md-mt/termproof` on 2026-10-11 — section 6.1 |
| Branch protection | none (legacy endpoint returns 404) |
| Security policy file | `SECURITY.md` present in the repository root (the community profile API does not report a security file) |
| Private vulnerability reporting | **disabled** (`/private-vulnerability-reporting` returns `{"enabled":false}`) — the *Security → Report a vulnerability* button is not live, yet `SECURITY.md` directs reporters there |
| Vulnerability alerts | not enabled (`/vulnerability-alerts` returns 404; the Dependabot alerts API reports "Dependabot alerts are disabled for this repository") |
| Automated security fixes | not enabled (`{"enabled":false}`) |
| Secret scanning | enabled, with push protection enabled |
| Dependabot version updates | enabled — `.github/dependabot.yml`, weekly, grouped |
| Code owners | `* @md-mt` (`.github/CODEOWNERS`) |
| Community health files | present — `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `SUPPORT.md`, `CHANGELOG.md`, issue forms, PR template |
| CI on `main` | green on the current head: 5/5 check runs succeeded on `73375d7` |

That ruleset is the only one in the repository, and it enforces two checks:
a commit reaches `main` only with a passing `CI (Rust) result` and a passing
`Oracle freshness result`, unless the actor holds the admin role, which
bypasses it. It carries no pull-request, review, force-push or deletion
rule. Everything else section 6.2 intends is still social, not structural:
every change so far has gone through a reviewed PR, but nothing in GitHub
enforces that today.

## 2. Intended repository metadata

Applied by the settings-change task after this document merges and is reviewed:

- **Homepage:** `https://docs.rs/termproof` — the library's API docs, the most
  useful landing page for consumers (the README already links there).
- **Topics:** `rust`, `terminal`, `tui`, `testing`, `verification`,
  `evidence`, `pty`, `cli`, `snapshot-testing`, `developer-tools`.

## 3. Intended vulnerability settings

- Enable **vulnerability alerts** and **Dependabot alerts**, so the advisory
  posture is visible in the UI as well as in CI (`cargo deny` already runs the
  advisory check on schedule).
- Keep **private vulnerability reporting** enabled — `SECURITY.md` documents it
  as the reporting path.
- Enable **automated security fixes** (Dependabot security updates) only if the
  maintainers will review the resulting PRs; otherwise leave them off. Least
  privilege applies: do not enable a surface nobody is committed to tending.
- The baseline for these settings is "not enabled" (section 1). The
  settings-change task records the exact before/after JSON.

## 4. Merge policy

Intended, and consistent with the pull-request template ("PRs are
squash-merged; the merge commit message will be the PR title"):

- **Squash merge only.** Merge commits and rebase merges are disabled, so every
  `main` commit reads as one conventional-commit message and `main` history
  stays linear. The auto-release workflow derives bumps from commit messages,
  so the PR title is the release input.
- **Delete branch on merge.** Merged branches are removed automatically.
- **Pull requests required for `main`.** No direct pushes to `main`.

## 5. Required checks (stable names)

A ruleset requires status checks by exact name, so the names below are the
stable job names from the merged workflows. Renaming a job silently un-gates
the ruleset, and this list is the contract.

The table is the contract for the ruleset section 6.2 intends: thirteen names.
The live ruleset (section 6.1) enforces exactly one of them, the first row,
plus `Oracle freshness result` from the second table below — two required
checks in total. No `CI (Python)` check is ruleset-required today.

One repository, two language paths, so the gate covers both. The Rust checks
and the Python checks are listed together because a ruleset on `main` is one
list, not two.

| Check name (exact) | Workflow | Job |
|---|---|---|
| `CI (Rust) result` | `CI (Rust)` | `result` |
| `Dependency and licence policy (cargo deny)` | `Security (Rust)` | `deny` |
| `Public API compatibility (cargo semver-checks)` | `Security (Rust)` | `semver` |
| `Package contents (cargo package)` | `Security (Rust)` | `package` |
| `Plan` | `Publish crates (Rust)` | `plan` |
| `Publish gate` | `Publish crates (Rust)` | `gate` |
| `Dry run` | `Publish crates (Rust)` | `dry-run` |
| `Stdlib-only modules` | `CI (Python)` | `stdlib` |
| `Lint, type-check and version drift` | `CI (Python)` | `lint` |
| `Unit tests and coverage (py3.11)` | `CI (Python)` | `test` (matrix leg) |
| `Unit tests and coverage (py3.12)` | `CI (Python)` | `test` (matrix leg) |
| `Unit tests and coverage (py3.13)` | `CI (Python)` | `test` (matrix leg) |
| `Build, verify TUI evidence and publish it` | `CI (Python)` | `verify` |

The `Publish crates (Rust)` jobs are dry runs on pull requests by design
(`publishing.md`): nothing uploads until a release is published, so they are
safe to require on every PR. That workflow triggers on `pull_request`,
`workflow_dispatch` and `release`, never on a push to `main`, so those three
are verified on PR heads rather than on `main`.

**Live today: `CI (Rust) result` and `Oracle freshness result`.** They are
the two required status checks on `main`, enforced by the repository
ruleset **`main: require CI (Rust) result + Oracle freshness result`**
(id `24859051`) — enforcement **active**, targeting the default branch, with
the strict up-to-date policy off. The ruleset carries an admin bypass: the
repository admin role, which is what release automation pushes to `main` go
through. This is narrower than the ruleset section 6.2 intends, and its
bypass is a role rather than the explicit `@md-mt` actor that section asks
for; the other twelve rows of the table are the contract for that ruleset
and are not enforced by this one. In particular, **no `CI (Python)` check
is ruleset-required today** — the Python rows above remain the contract for
the intended ruleset, not a description of the live one. Section 6.1 has
the full live configuration.

**Now required: `Oracle freshness result`.** This check is deliberately not
one of the thirteen above, and it is live today as the second required
context on the same ruleset:

| Check name (exact) | Workflow | Job |
|---|---|---|
| `Oracle freshness result` | `CI (Oracle)` | `result` |

Current state: **required**. The oracle freshness gate (#172) originally sat
inside the path-filtered `CI (Python)`, where it could never be required for
the reason the Docker image jobs below give: a workflow filtered out by
`paths:` reports no check at all. It now lives in its own always-on workflow
(`.github/workflows/oracle-ci.yml`, no `paths:` filter) whose `changes` job
decides whether an oracle-relevant path moved and whose
`Oracle freshness result` rollup reports on every PR either way — the same
shape as `CI (Rust) result` — so that rationale no longer applies. Its
`oracle` job holds the checked-in corpus to the canonical environment
(`ubuntu-24.04`, CPython 3.13.5) with `--strict-environment`. The bootstrap
this paragraph used to wait on is complete: the gate landed in #260, the
corpus was re-recorded in the canonical environment in #261, the
`CI (Oracle)` run on `main` for that re-record (run `38158366345`)
succeeded, and the exact context `Oracle freshness result` was then added
to ruleset `24859051`, which was renamed to
`main: require CI (Rust) result + Oracle freshness result` to say so. The
historical caution still explains the sequencing: requiring the check
before that re-record was green would have blocked the gate-carrying PR
itself and every oracle-touching PR until the re-record landed.

Not required, and why:

- `Lint, type-check and test (...)` (`CI (Rust)`) — the two matrix legs are no
  longer required by name. `CI (Rust) result` needs both and fails unless they
  passed, or `changes` said there was nothing to test, so requiring it covers
  them, and it reports on a PR that leaves Rust alone where the legs do not.

- `Build and smoke-test the bundled-agg wheel (...)` (`CI (Python)`) — three
  platform legs, one of which cross-builds and can only inspect the wheel it
  produced. Slow, and not a correctness gate for a source change.
- `Build, smoke-test and publish the image` (`Docker Image (Rust)`) and
  `Build and publish the image` (`Docker Image (Python)`) — path-filtered to
  one tree each, so requiring either would block every PR that does not touch
  it.
- `Docs site`, `Pages preview` — same reason, and neither gates behaviour.
- `Validate .github/dependabot.yml` (`Dependabot config`) — path-filtered to
  `.github/dependabot.yml` and its own workflow file, so the same reason. It
  is also only a schema check: Dependabot validates further than the schema
  does, so passing it is not Dependabot accepting the file.
- `Dependabot` / `.github/dependabot.yml` checks on `main` are not PR gate
  checks.

Any change to a workflow that renames a job must update this table in the same
PR, or the ruleset will silently stop enforcing that check.

## 6. The `main` ruleset: live and intended

### 6.1 Live (verified 2026-10-11)

Read from `gh api repos/md-mt/termproof/rulesets/24859051`. It is the only
ruleset in the repository.

| Field | Live value |
|---|---|
| Name | `main: require CI (Rust) result + Oracle freshness result` |
| Id | `24859051` |
| Source | repository `md-mt/termproof` |
| Target | branch; include `~DEFAULT_BRANCH`, no excludes |
| Enforcement | `active` |
| Rules | one — `required_status_checks` |
| Required contexts | two — `CI (Rust) result`, `Oracle freshness result` |
| Strict up-to-date policy | off (`strict_required_status_checks_policy: false`) |
| Enforce on branch creation | yes (`do_not_enforce_on_create: false`) |
| Bypass | one actor — `RepositoryRole` id `5` (the admin role), mode `always` |
| Created | 2026-10-10 |

What that does and does not do:

- **Two checks gate `main`.** `CI (Rust) result` is the rollup that waits for
  every Rust test job and reports on a PR that leaves Rust alone (section 5),
  which is what makes it safe to require on every PR. `Oracle freshness
  result` is the analogous always-on rollup for the oracle gate: it reports
  on every PR, and when an oracle-relevant path moved it requires the corpus
  to reproduce in the canonical environment (`ubuntu-24.04`, CPython
  3.13.5, `--strict-environment`; section 5). No `CI (Python)` check is
  required by this ruleset.
- **Nothing else is a rule.** No `pull_request` rule, so no required PR,
  review count, stale-approval dismissal or conversation resolution; no
  `non_fast_forward` or `deletion` rule, so the ruleset does not block force
  pushes or branch deletion; and a PR head does not have to contain the
  latest `main`.
- **The bypass is a role, not an account.** Anyone holding the admin role
  bypasses the ruleset, always. Release automation relies on it: the
  auto-release workflow pushes its version-bump commit straight to `main`
  with `RELEASE_TOKEN` (`git push origin HEAD:main`), without a PR. This is
  the blanket path section 6.2 argues against, and it is the standing one
  today.

### 6.2 Intended — not live

**None of this section is configured.** It is the design this document argued
for at the 2026-08-16 baseline, kept because the rationale still stands. The
settings-change task applies it — by extending ruleset `24859051` or by
replacing it — and records the resulting id, name and before/after JSON in
section 6.1.

Two things have to be settled before it can be applied as written:

- **Release automation needs a path.** Requiring pull requests and narrowing
  the bypass to `@md-mt` would reject the auto-release push to `main` unless
  `RELEASE_TOKEN`'s identity is itself a bypass actor or the bump moves to a
  PR.
- **Path-filtered workflows do not report on every PR.** `Security (Rust)`,
  `Publish crates (Rust)` and `CI (Python)` all trigger on `paths:`, so their
  checks never arrive on a PR outside those paths, and a required check that
  never arrives blocks the merge — the reason section 5 gives for not
  requiring the Docker image jobs. Those twelve rows — every row but
  `CI (Rust) result` — need a rollup like it before they can be required.

One ruleset, name **`main`**, enforcement **active**, targeting branch `main`:

- **Require pull requests** — direct pushes rejected.
- **Required approving reviews: 0 — the enforceable floor.** GitHub counts a
  required review only from a reviewer with write permission (or a designated
  code owner) who is not the PR author. Today the only write-capable account
  is the maintainer `@md-mt`, which authors every PR, and no second eligible
  reviewer exists (verified 2026-08-16: the review/audit account `@mw-ding`
  has no push access). A count of one would make every routine
  `@md-mt`-authored PR unmergeable without the emergency bypass, which
  section 7 reserves for incidents. The count is therefore **zero**: the
  ruleset still requires a PR, all thirteen checks, and up-to-date branches, and
  blocks force pushes; review stays social (the PR template asks for review)
  until a second eligible reviewer is established. Raising this count is
  gated on the promotion criteria below.
- **Code-owner review: not required** — `require_code_owner_review` stays
  off. With `CODEOWNERS = * @md-mt` and the sole code owner authoring the
  PRs, requiring code-owner review would reproduce the same lockout.
- **Dismiss stale approvals** when new commits are pushed.
- **Require conversation resolution** — a resolved thread must stay resolved.
- **Require status checks**: the thirteen names in section 5.
- **Require branches to be up to date before merging** — the PR head must
  include the latest `main` before the merge button works. CI latency for the
  thirteen checks is acceptable (minutes), so the strict option stays on.
- **Block force pushes** and **block branch deletion** on `main`.
- **Bypass: explicit, not blanket.** The sole bypass actor is the maintainer
  account `@md-mt` (the code owner). Do **not** enable the "bypass all
  administrators" toggle, so a future admin added to the repo does not inherit
  an unchecked path around the ruleset.
- **Least privilege**: nothing else is exempted. `CODEOWNERS` remains
  `* @md-mt` as the ownership signal; because the sole code owner authors the
  PRs, the ruleset enforces the gate structurally (PR + checks + up-to-date)
  and keeps code-owner review off, so no routine path depends on a bypass.

**Promotion criteria.** The review count is raised from zero to **one** only
when a second eligible reviewer exists — a collaborator granted write
permission (or designated code owner) who is not the PR author, or a
non-`@md-mt` authoring path (a bot/CI account opening PRs) that lets
`@md-mt` approve as the code owner. Until one of those is real, a count of
one stays out of the ruleset: it would lock every routine `@md-mt`-authored
PR onto the emergency bypass, which section 7 forbids. The settings task
records which reviewer was added and re-runs the audit when it promotes.

## 7. Emergency bypass

The ruleset exists to keep normal work on the reviewed PR path; it must not be
able to lock the maintainer out of the repository.

This section is written for the intended ruleset (section 6.2) and its explicit
`@md-mt` bypass. The live bypass is the admin role (section 6.1), and release
automation uses it routinely; the rules below are the policy for people, and
they hold today for any human use of that role.

- **When it is used:** incident recovery only — e.g. a ruleset misconfiguration
  that blocks an urgent security fix, a botched CI workflow that gates every
  PR, or GitHub-side drift that makes the required checks un-runnable.
- **Who:** `@md-mt`, the explicit bypass actor. It is a per-incident decision,
  not a standing permission to push to `main`.
- **Procedure:**
  1. Record the incident and the reason in the repository (a comment on the
     relevant issue/PR, or a maintenance note) before acting.
  2. Use the bypass to land the fix.
  3. Re-run the normal gate as soon as the incident clears; if the bypass was
     a ruleset edit, restore the documented ruleset and re-verify it with the
     audit commands in section 8.
  4. Note the bypass in the next audit (section 8), so it cannot become the
     habitual path.
- **Non-uses:** never for routine changes, version bumps, or "small fix,
   quick push" convenience. If a change is worth making to `main`, it is worth
   the reviewed PR path.

## 8. Audit procedure

Governance is a live surface; the audit re-verifies that the repository still
matches this document. Run it:

- after any settings change (before/after JSON recorded with the change);
- after any workflow rename that touches a required check;
- quarterly, or whenever the governance document is edited.

Commands (all read-only):

```sh
# Metadata
gh repo view md-mt/termproof --json homepageUrl,repositoryTopics,hasIssuesEnabled,hasWikiEnabled,hasProjectsEnabled,hasDiscussionsEnabled,mergeCommitAllowed,rebaseMergeAllowed,squashMergeAllowed,deleteBranchOnMerge

# Rulesets and branch protection. The list must be exactly one ruleset,
# 24859051; the list endpoint omits rules and bypass actors, so the detail
# is read by id further down.
gh api repos/md-mt/termproof/rulesets --jq '.[] | "\(.id)\t\(.enforcement)\t\(.name)"'
gh api repos/md-mt/termproof/branches/main/protection

# Vulnerability settings (admin token; record 2xx vs 4xx per endpoint)
gh api -i repos/md-mt/termproof/vulnerability-alerts
gh api -i repos/md-mt/termproof/automated-security-fixes
gh api repos/md-mt/termproof/dependabot/alerts

# Baseline CI health on the current head of main. `CI (Rust) result` always
# reports; the Security (Rust) and CI (Python) checks report only when the
# push touched their paths, and the Publish jobs never run on main, so this
# command alone cannot verify the full section 5 contract.
gh api repos/md-mt/termproof/commits/main/check-runs --jq '.check_runs[].name'

# The section 5 contract — audit from a PR head. All thirteen report only on
# a PR that touches both the Rust and the Python paths; pick one that does:
gh pr checks <pr-number> --repo md-mt/termproof --json name,state,workflow
# or directly against a PR head commit:
gh api repos/md-mt/termproof/commits/<pr-head-sha>/check-runs --jq '.check_runs[].name'

# The live ruleset, by id (section 6.1). Expected output, exactly:
#   {"name":"main: require CI (Rust) result + Oracle freshness result","enforcement":"active","include":["~DEFAULT_BRANCH"],"exclude":[],"rules":["required_status_checks"],"strict":false,"bypass":["RepositoryRole:5:always"]}
gh api repos/md-mt/termproof/rulesets/24859051 --jq '{name, enforcement, include: .conditions.ref_name.include, exclude: .conditions.ref_name.exclude, rules: [.rules[].type], strict: (.rules[] | select(.type == "required_status_checks") | .parameters.strict_required_status_checks_policy), bypass: [.bypass_actors[] | "\(.actor_type):\(.actor_id):\(.bypass_mode)"]}'

# The contexts the live ruleset requires. Today that is two lines,
# `CI (Rust) result` and `Oracle freshness result` — not the thirteen of
# section 5:
gh api repos/md-mt/termproof/rulesets/24859051 --jq '.rules[] | select(.type == "required_status_checks") | .parameters.required_status_checks[].context'

# The same as a check: exits non-zero unless the live contexts are exactly
# the expected set. Edit the expected list when section 6.1 changes.
test "$(gh api repos/md-mt/termproof/rulesets/24859051 --jq '[.rules[] | select(.type == "required_status_checks") | .parameters.required_status_checks[].context] | sort | join(",")')" = "CI (Rust) result,Oracle freshness result"

# Every rule that applies to main, across all rulesets — catches a second
# ruleset or an added rule that the by-id read above would not show.
# Expected: one line, `24859051<TAB>required_status_checks`.
gh api repos/md-mt/termproof/rules/branches/main --jq '.[] | "\(.ruleset_id)\t\(.type)"'

# Community health
gh api repos/md-mt/termproof/community/profile --jq .health_percentage
```

Expected today, for the ruleset: exactly one, id `24859051`, as section 6.1
records it — active on the default branch, one `required_status_checks` rule
whose contexts are `CI (Rust) result` and `Oracle freshness result`, strict
policy off, and the admin-role bypass. A second ruleset, another context, or
a different bypass actor is a finding.

Expected after the settings change (not live): homepage
`https://docs.rs/termproof`; topics present; vulnerability/Dependabot alerts
enabled; private reporting enabled; squash-only + delete-branch-on-merge; one
active `main` ruleset with the thirteen required checks and a required-review
count of zero (until a second eligible reviewer exists — see promotion criteria
in section 6.2); `main` refusing direct pushes, force pushes and deletion; and
an explicit `@md-mt` bypass. Any deviation from section 1–6 is a finding to fix
or a deliberate change to record here first.
