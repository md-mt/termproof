<!--
Thanks for contributing to TermProof! Please read CONTRIBUTING.md.
All changes go through pull requests — no direct commits to `main`.
Open as a draft early and request review when CI is green.
-->

## Summary

What does this PR do and why? Keep changes small and incremental
(~100 lines of logic, <200 with tests). Split larger work into stacked PRs.

## Which implementation

- [ ] Python (`python/`)
- [ ] Rust (`rust/`)
- [ ] Shared — `spec/`, `conformance/`, `.github/`, or a root document

## Linked issue

<!-- Use a closing keyword so the issue auto-closes on merge. -->

Closes #

## Test plan

How did you verify this change? Run the gates for the trees you touched.

```bash
# Python
(cd python && uv run ruff check . && uv run mypy termproof)
(cd python && uv run python -m unittest discover -s tests && uv build)
# if you touched runner/renderer/video:
(cd python && uv run termproof run examples/generic --video --out .termproof/ci)

# Rust
cargo fmt    --manifest-path rust/Cargo.toml --check --all
cargo clippy --manifest-path rust/Cargo.toml --workspace --all-targets --all-features -- -D warnings
cargo test   --manifest-path rust/Cargo.toml --workspace
```

- [ ] Added/updated unit tests for behavioural changes
- [ ] Screenshots / evidence attached (if UX or output changed)

## Tidy First

Following Tidy First, structural moves and behavioural changes are not mixed in
the same diff.

- [ ] This PR is a **structural** change only (renames/moves/formatting), OR
- [ ] This PR is a **behavioural** change only, OR
- [ ] N/A (docs / chore)

## Checklist

- [ ] Title and commits follow Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`)
- [ ] No comments/docstrings/type hints added to untouched code
- [ ] Branch follows naming convention (`feat/`, `fix/`, `docs/`, `refactor/`, `chore/`)
- [ ] No large binaries checked in (`python/examples/artifacts/` kept lean)
- [ ] `CHANGELOG.md` updated under `[Unreleased]` if the change is user-facing
- [ ] No new claim that the code does not support (`python/tests/test_public_claims.py` sweeps the whole repository)
- [ ] Backward-compatibility contract respected (legacy `tui-verifier` paths / plugin prefix — see CONTRIBUTING.md)
- [ ] If the two implementations now disagree, the divergence is measured and recorded (see CONTRIBUTING.md)
