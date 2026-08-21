# Contributing to TermProof

Thank you for considering a contribution. TermProof is one project with two
implementations — Python under [`python/`](python) and Rust under
[`rust/`](rust) — sharing one specification, one conformance corpus, one
version train and one tracker. Everything above the two language sections
applies to both.

## Contribution ladder

Progress from light to deep involvement. Each rung builds trust for the next.

1. **Star & spread** — star the repo, add the Verified by TermProof badge to
   your project, mention us.
2. **Recipe** — contribute a `*.recipe.json` under `python/examples/` or your
   own repo that verifies a real TUI. Must be deterministic and runnable in CI.
3. **Bug** — report reproducible bugs with recipe + cast + expected vs actual.
   Fixes welcome with tests.
4. **Plugin** — ship an external plugin (step, assertion, session backend,
   video backend, reporter) in your own repo, listed in
   [`python/docs/plugins.md`](python/docs/plugins.md).
5. **Core** — contribute to either implementation's internals.
6. **Maintainer** — sustained, high-quality contributions, reviews, and
   stewardship. Invite-only, proposed by existing maintainers.

You don't need to move linearly — a solid core PR can jump rungs — but the
ladder shows the path.

## What the two implementations owe each other

The Python implementation is the **shipped product and the behavioural
oracle**. The Rust implementation is an **in-progress port**: it is not at
parity, and there is no parity gate. Three rules follow, and they bind every
contribution:

1. **A divergence is a parity gap, not a preference.** If your change makes
   the Rust implementation behave differently from the Python one, that is
   something to measure and document, not to ship silently. File it with the
   [parity gap form](.github/ISSUE_TEMPLATE/parity_gap.yml).
2. **No claim of parity without a measurement.** The numbers quoted in
   [`README.md`](README.md), [`conformance/README.md`](conformance/README.md)
   and [`rust/docs/status-and-parity.md`](rust/docs/status-and-parity.md) come
   from the differential harness. If your change moves them, update them
   honestly. A number nobody can reproduce is not a measurement.
3. **Version and release claims must be true.** What is published where is
   listed in [`SECURITY.md`](SECURITY.md#what-is-published-and-who-has-to-be-notified);
   the mechanics are in [`python/docs/releases.md`](python/docs/releases.md)
   and [`rust/docs/publishing.md`](rust/docs/publishing.md).

The repository has a documented history of claims outrunning code, and
`python/tests/test_public_claims.py` is the standing guard: it sweeps every
tracked prose and metadata surface in the repository — both trees, the spec
and the conformance corpus — for phrasings that had to be withdrawn once. New
prose anywhere is judged by it.

## PR-only process

All changes go through pull requests. No direct commits to `main`.

1. **Fork & branch.**

   ```bash
   git checkout main
   git pull origin main
   git checkout -b feat/your-feature
   ```

   Branch naming: `feat/`, `fix/`, `docs/`, `refactor/`, `chore/`.

2. **Code style.**

   - Simple, direct solutions over abstractions.
   - One incremental change per PR (~100 lines of logic, <200 with tests).
     Split larger work into stacked PRs.
   - Write unit tests for behavioural changes.
   - Follow Tidy First: don't mix structural moves and behavioural changes in
     the same diff.
   - Don't add comments, docstrings or type annotations to untouched code.
   - Use [Conventional Commits](https://www.conventionalcommits.org/):
     `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`. The Rust
     auto-release workflow derives version bumps from commit messages, so a
     misleading type is not just cosmetic. A breaking change must carry `!`
     (or a `BREAKING CHANGE:` footer) — under the pre-1.0 rule it is what
     bumps the minor digit.

3. **Recipes & evidence.**

   - New features that affect recipe semantics should include a recipe under
     `python/examples/` if relevant.
   - Avoid checking in large binaries. Keep `python/examples/artifacts/` lean
     — CI generates the real evidence.

4. **Update the changelog.** If the change is user-facing, add an entry under
   `[Unreleased]` in [`CHANGELOG.md`](CHANGELOG.md), in the same PR, under the
   heading for the implementation it affects. There is one changelog for the
   whole project because there is one version train.

5. **Open a PR** against `main` using the
   [pull request template](.github/PULL_REQUEST_TEMPLATE.md).

   ```bash
   gh pr create --title "feat: add wait_for_regex step" --body "Closes #14"
   ```

   The body should say what and why (link issues), give a test plan, and
   attach evidence if output changed. Mark as draft early and request review
   when CI is green.

6. **Review & merge.**

   - All CI checks must pass. Fix failures rather than working around them.
   - At least one maintainer approval.
   - Squash merge is default for feature branches; the branch is deleted after
     merge.

## Finding work

- Issues labelled [`good first issue`](https://github.com/md-mt/termproof/labels/good%20first%20issue)
  are a good starting point.
- Issues labelled [`help wanted`](https://github.com/md-mt/termproof/labels/help%20wanted)
  are open asks.
- Nothing else is off-limits — but if an issue is unlabelled and unassigned,
  comment on it before starting, so two people do not build the same thing.

## Reporting issues

- Search existing issues first.
- Say which implementation you are running.
- Include a reproduction recipe, `termproof --help` output, your toolchain
  version, OS, and observed vs expected behaviour.
- For security issues, use the private path in [`SECURITY.md`](SECURITY.md)
  instead of filing publicly.

---

## Working on the Python implementation

Everything below runs from `python/`. Prerequisites: Python 3.11+, `uv`,
`ffmpeg`, and Rust (`cargo`) to build `agg`.

```bash
git clone https://github.com/md-mt/termproof.git
cd termproof/python
uv sync                      # creates .venv and installs deps
uv run python -m unittest discover -s tests -v
```

The gates CI enforces (`.github/workflows/python-ci.yml`):

```bash
uv run ruff check .
uv run mypy termproof
uv run python -m unittest discover -s tests
uv build
```

CI additionally runs the stdlib-only subset with nothing installed (so a
module that documents itself as stdlib-only stays that way), the test suite on
3.11–3.13, the plugin-template build and demo, a wheel smoke test, and the
end-to-end evidence run that produces the PR comment.

Render verification (optional, requires `agg`):

```bash
cargo install --locked --git https://github.com/asciinema/agg --tag v1.9.0
uv run termproof run examples/generic --video
```

### Compatibility contract

- **Legacy `tui-verifier` paths** (`~/.config/tui-verifier/config.yaml`,
  `.tui-verifier/`) remain readable but are overridden by the new `termproof`
  paths. Do not remove this compat without a major version bump.
- **Plugin module prefix** `tui_verifier.*` is translated to `termproof.*` at
  load time, for configured plugin references only.
- Breaking recipe semantics or artifact contracts requires a minor or major
  version per [`python/docs/releases.md`](python/docs/releases.md).

---

## Working on the Rust implementation

The workspace pins an exact toolchain via `rust/rust-toolchain.toml`
(`channel = "1.96.0"`, `profile = "minimal"`, components `rustfmt` and
`clippy`). With `rustup` installed, the pin is picked up automatically.

```bash
cargo build --manifest-path rust/Cargo.toml --workspace
```

The gates CI enforces (`.github/workflows/rust-ci.yml`):

```bash
cargo fmt   --manifest-path rust/Cargo.toml --check --all
cargo clippy --manifest-path rust/Cargo.toml --workspace --all-targets --all-features -- -D warnings
cargo test  --manifest-path rust/Cargo.toml --workspace
```

Run all three before pushing. CI also runs the suite across the whole feature
powerset (five features — `evidence`, `junit`, `json-schema`, `schema` and the
default-off `clap`, so thirty-two combinations) and at the declared dependency
floors, so a change that only breaks a non-default combination is caught there
even if your local default build is green. Note that `clap` being default-off
means `cargo test --workspace` above does not compile `run_config::cli` at all;
add `--features clap` if you are touching it. `.github/workflows/rust-security.yml` adds
`cargo deny`, `cargo semver-checks` against the latest published `termproof`,
and a `cargo package` contents check.

Read [`rust/docs/engineering-baseline.md`](rust/docs/engineering-baseline.md)
before your first change — it is the workspace policy on formatting, linting,
errors, tracing, dependencies, features and unsafe code, and CI enforces it.

### If you change a step or an assertion

The differential harness replays the checked-in corpus through both runtimes
and asserts a floor, not equality. If your change moves the port's answers:

- run `cargo test --manifest-path rust/Cargo.toml -p termproof --test differential_steps -- --nocapture`
  (and the assertions twin) and read what it prints;
- update the counts and the divergence list in
  [`conformance/README.md`](conformance/README.md) and in
  [`rust/docs/status-and-parity.md`](rust/docs/status-and-parity.md) to match;
- do **not** regenerate the recorded oracle expectations to make the test pass
  — `conformance/README.md` explains why that is falsifying the measurement.

### If you change a manifest

- Every dependency in `[workspace.dependencies]` carries a documented reason
  in `rust/docs/engineering-baseline.md`; add one for anything new, and name
  the API that justifies a floor above the oldest workable version.
- A requirement there is a *floor*, not a preference. If you widen one, CI
  pins it and runs the suite at it — make sure the code actually works there.
- `Cargo.toml` and `Cargo.lock` changes land in the same commit.

---

## Licence

By contributing, you agree that your contributions are licensed under the
[MIT Licence](LICENSE) — the same terms as the rest of the repository.

## Questions?

Open an issue or a draft PR. See [`SUPPORT.md`](SUPPORT.md) for where each
kind of question belongs.
