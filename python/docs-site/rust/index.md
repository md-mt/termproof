# The Rust implementation

TermProof has two implementations, and both live in this repository. The Rust
one is under [`rust/`](https://github.com/md-mt/termproof/tree/main/rust); the
Python one — the shipped product, the behavioural oracle, and what this
documentation site is about — is under `python/`.

Read
[status and parity](https://github.com/md-mt/termproof/blob/main/rust/docs/status-and-parity.md)
before depending on the Rust implementation. It is **in progress** and **not at
parity**: there is no parity gate, and the differential harness in
[`conformance/`](https://github.com/md-mt/termproof/tree/main/conformance)
reports 82 of 115 step cases and 124 of 147 assertion cases in full agreement
with the Python implementation, with 113 and 143 agreeing on the verdict alone.

## What this means for you

**If you install TermProof from Homebrew, the container image or the GitHub
Action, nothing changes.** Those channels ship the Python implementation and
they still do. It remains the only engine those channels support.

**If you want the Rust binary,** the `termproof` library crate is published on
crates.io; the `termproof-cli` binary is not, and installs from a git tag or a
checkout. See the
[repository README](https://github.com/md-mt/termproof#install).

The Action's `engine: rust` input is still rejected: the Action installs a
Python package, and wiring it to the Rust binary is a separate change from
consolidating the repositories. `engine: auto` and `engine: python` are
unaffected.

## Still here

- [Plugins](/plugins) — the supported plugin interface, which is the Python one.
- [Durable evidence hosting](/ci/evidence-hosting) — it documents
  `scripts/publish_evidence.py`, a Python script that is staying put.
