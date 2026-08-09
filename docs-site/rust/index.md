# The Rust port has moved

TermProof's Rust reimplementation now lives in its own repository:
**[md-mt/termproof-rust](https://github.com/md-mt/termproof-rust)**.

The pages that used to sit here — Rust Install, Migration Guide and Plugin
Protocol v1 — described a Rust engine shipped from this repository. It is no
longer shipped from here, so those pages have been removed rather than left to
document something that does not exist.

## What this means for you

**If you install TermProof from PyPI, Homebrew, the container image or the
GitHub Action, nothing changes.** Those channels have always shipped the Python
implementation and they still do. It remains the only supported engine.

**If you were using the Rust binary,** it is not published anywhere today. The
port moved before it reached a release, and it has no parity gate: a
differential harness driving identical inputs through both implementations
found them agreeing on 55 of 217 cases. Track
[md-mt/termproof-rust](https://github.com/md-mt/termproof-rust) for its status
and its first release.

Concretely, from TermProof 0.2.1 onwards:

- the `rust/` workspace, the `Rust` and `Release (Rust)` workflows, and the
  `termproof-rust` binary in the container image are gone from this repository;
- the Action's `engine: rust` input is rejected with an error instead of
  downloading a release archive that was never published, and its
  `rust-version` input is gone;
- `engine: auto` and `engine: python` are unaffected.

## Still here

- [Plugins](/plugins) — the supported plugin interface, which is the Python one.
- [Durable evidence hosting](/ci/evidence-hosting) — moved out of this section
  because it documents `scripts/publish_evidence.py`, a Python script that is
  staying put.
