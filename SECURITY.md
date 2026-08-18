# Security Policy

This policy covers the whole repository: both implementations of TermProof,
the recipe specification, the conformance corpus, the CI workflows and the
scripts under `.github/`.

## Reporting a vulnerability

Please report privately rather than opening a public issue.

- **Preferred:** GitHub Private Vulnerability Reporting — on the repository
  page, *Security* → *Report a vulnerability*. Reports go only to the
  maintainers and stay private until a fix can land.
- **Alternative:** email **md@mt.com**.

Do **not** disclose sensitive details — proof-of-concept code, exploit
write-ups, or affected-version specifics — in a public issue or pull request.
Public channels are not a private reporting path.

Please include:

- which implementation is affected (Python, Rust, or both) and the affected
  commit, tag or published version — or say "latest `main`";
- a minimal recipe or test case that triggers the issue;
- your assessment of impact, if you have one.

## What to expect

This is a small, best-effort, pre-1.0 project; there is no security SLA.

- The maintainers aim to acknowledge reports within **7 days**.
- A fix lands through the normal PR flow and, when it is user-facing, an entry
  under `[Unreleased]` in [`CHANGELOG.md`](CHANGELOG.md).
- The maintainers will coordinate disclosure with you, and will credit you
  unless you prefer otherwise. If you would prefer a specific embargo window,
  say so in the report.

## Supported versions

Both implementations share one version train, so one row covers both.

| Version | Supported          |
| ------- | ------------------ |
| 0.3.x   | :white_check_mark: |
| 0.2.x   | :x:                |
| 0.1.x   | :x:                |

In practice the supported set is **the latest `main`** plus the most recent
release of each distribution. Do not assume an older tag is patched; there are
no backport branches.

## What is published, and who has to be notified

A fix has different reach depending on which distribution carries it, so the
list is here rather than split across two policies.

| Distribution | Published today | A fix reaches consumers by |
| --- | --- | --- |
| `termproof` on PyPI | yes, through `0.3.4` — [release history](https://pypi.org/project/termproof/#history) | a new `py-v*` release |
| `termproof` crate on crates.io | yes, through `0.3.4` — [version list](https://crates.io/crates/termproof/versions) | a new `rs-v*` release |
| `termproof-cli`, `termproof-plugin-protocol` crates | no — held back with `publish = false` | source, or a release binary |
| Rust CLI binaries | attached to each `rs-v*` GitHub release | re-download |
| `ghcr.io/md-mt/termproof`, `ghcr.io/md-mt/termproof-rust` | on every push to `main` and every release tag | re-pull |

CI runs on GitHub-hosted runners; the workflows live in `.github/workflows/`,
and the release mechanics are in
[`python/docs/releases.md`](python/docs/releases.md) and
[`rust/docs/publishing.md`](rust/docs/publishing.md).
