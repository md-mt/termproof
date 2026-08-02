# TermProof Rust Workspace

This directory holds the Rust reimplementation of TermProof. It is a fully
separate workspace from the Python implementation at the repository root: the
Python package, packaging, CLI default, and docs remain unchanged at the top
level until the parity gates in `docs/rust-reimplementation-spec.md` pass.

## Layout

- `Cargo.toml` — workspace manifest with shared lint and dependency policy.
- `rust-toolchain.toml` — pinned stable toolchain (`stable`, minimal profile).
- `docs/engineering-baseline.md` — formatting, lint, error, tracing,
  dependency, feature, and unsafe-code policies (RUST-002 deliverable).
- `crates/` — five workspace crates:
  - `termproof-cli` — binary (`termproof`), command parsing, diagnostics
  - `termproof-core` — models, config, schema, registries, planning, orchestration
  - `termproof-terminal` — PTY/process sessions, terminal screen, cast recording
  - `termproof-evidence` — rendering, reports, video, baselines, diff, cache
  - `termproof-plugin-protocol` — versioned process messages, client/host support

## Quickstart

```sh
cd rust

# Run the baseline binary
cargo run -p termproof-cli

# Local gates (must pass before every push; CI enforces the same)
cargo fmt --check --all
cargo clippy --workspace --all-targets --all-features -- -D warnings
cargo test --workspace
cargo doc --workspace --no-deps
```

## Status

RUST-002 baseline: the workspace builds, lints clean, and the `termproof`
binary prints the canonical greeting. Real behavior lands in the M0–M5
milestones tracked by issues 94–123.
