# Migration Guide (RUST-024)

The Rust reimplementation is a **compatibility-first** migration. The Python implementation remains the rollback path until the parity gates in `docs/rust-reimplementation-spec.md` (section 11) pass.

## What stays the same

- Recipe format v1 and legacy loading
- All CLI commands and flags (`run`, `list`, `validate`, `plugins`, `init`, `demo`)
- Exit codes (0 success, 1 failure, 2 usage)
- Artifact layout (`session.cast`, `final.svg`, `result.json`, `report.md`, `latest-report.md`, `session.mp4`)
- Reports (Markdown, JUnit XML), baselines/diff, cache, parallel runs
- CI receipt behavior

## How to try the Rust binary

```sh
cargo run --manifest-path rust/Cargo.toml -p termproof-cli -- run examples/generic --out /tmp/rust-out
cargo run --manifest-path rust/Cargo.toml -p termproof-cli -- --help
```

Help snapshots are stored under `rust/crates/termproof-cli/tests/snapshots/` and enforce CLI parity in CI.

## Rollback

If the Rust binary fails, use the Python implementation explicitly:

```sh
uv run termproof run examples/generic --out /tmp/py-out
# or
python -m termproof run examples/generic --out /tmp/py-out
```

The `termproof` entry point defaults to Python until the cutover gate (RUST-028) flips.

## Version source

One version lives in `pyproject.toml`; `rust/Cargo.toml` workspace version must match. CI enforces this via `scripts/check_version.py` (RUST-023). The changelog is the third source: `CHANGELOG.md` must contain an entry for the current version.
