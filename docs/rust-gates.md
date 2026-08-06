# RUST-026–029 Gates (preparation)

This document prepares the cutover gates. No behavior is cut over until all M0–M4 gates pass.

## RUST-026 — Cross-runtime conformance

Corpus: same recipes executed by Python (`uv run termproof`) and Rust (`cargo run -p termproof-cli`) on Tier 1 targets (linux x86_64, macos x86_64). Difference report allows only reviewed normalizations (timestamps, durations, platform paths, font rendering, encoded video). Goal: zero unexplained semantic differences.

Run (when `scripts/conformance.py` lands in RUST-026):

```sh
python scripts/conformance.py --corpus examples/generic --py-out /tmp/py --rust-out /tmp/rust --report /tmp/conformance.json
# Until then, manually compare:
uv run termproof run examples/generic --out /tmp/py
cargo run --manifest-path rust/Cargo.toml -p termproof-cli -- run examples/generic --out /tmp/rust
diff -r /tmp/py /tmp/rust
```

## RUST-027 — Canary release

Publish prereleases to TestPyPI and `termproof-prerelease` Homebrew tap; dogfood on 2+ repositories; collect opt-in diagnostics; repair regressions. No existing install changes engine silently.

## RUST-028 — Cutover with rollback

- Rust becomes default; Python fallback retained for one stable release (`TERM_PROOF_ENGINE=python` or `termproof --engine python`).
- Downgrade and artifact compatibility tested.
- Rollback procedure: revert `termproof` entry point to Python wheel, keep Rust binary as `termproof-rust`.

## RUST-029 — First PyPI release (Rust-backed)

Trusted publishing already configured (`release.yml` + `release-rust.yml` with `id-token: write`, environment `pypi`). Publish and install-test:

```sh
uv build
twine check dist/*
# CI publishes via pypa/gh-action-pypi-publish@release/v1
pip install termproof==0.2.1 --force-reinstall
termproof --help
termproof run examples/generic --out /tmp/final
```
