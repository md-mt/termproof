# Contributing to TermProof

Thank you for considering a contribution. This document describes the ladder, local setup, and PR-only process.

## Contribution ladder

Progress from light to deep involvement. Each rung builds trust for the next.

1. **Star & spread** — star the repo, add the Verified by TermProof badge to your project, mention us.
2. **Recipe** — contribute a `*.recipe.json` under `examples/` or your own repo that verifies a real TUI. Must be deterministic and runnable in CI.
3. **Bug** — report reproducible bugs with recipe + cast + expected vs actual. Fixes welcome with tests.
4. **Plugin** — ship an external plugin (step, assertion, session backend, video backend, reporter) in your own repo, listed in `docs/plugins.md`.
5. **Core** — contribute to `termproof/` internals (registry, runner, config, CLI, screen, video). Requires understanding of petterm + asciinema + pexpect.
6. **Maintainer** — sustained, high-quality contributions, reviews, and stewardship. Invite-only, proposed by existing maintainers.

You don't need to move linearly — a solid core PR can jump rungs — but the ladder shows the path.

## Setup

Prerequisites: Python 3.11+, `uv`, `ffmpeg`, Rust (`cargo`) for `agg`.

```bash
git clone https://github.com/md-mt/termproof.git
cd termproof
uv sync                      # creates .venv and installs deps
uv run python -m unittest discover -s tests -v
```

Render verification (optional, requires `agg`):

```bash
cargo install --locked --git https://github.com/asciinema/agg --tag v1.9.0
ffmpeg -version
uv run termproof run examples/generic --video
ls .termproof/runs/
```

Build package:

```bash
uv build
ls dist/
```

## PR-only process

All changes go through pull requests. No direct commits to `main`.

1. **Fork & branch**

   ```bash
   git checkout main
   git pull origin main
   git checkout -b feat/your-feature
   ```

   Branch naming:

   - `feat/...` — features
   - `fix/...` — bug fixes
   - `docs/...` — documentation
   - `refactor/...` — code restructuring
   - `chore/...` — maintenance

2. **Code style**

   - Simple, direct solutions over abstractions.
   - One incremental change per PR (~100 lines of logic, <200 with tests). Split larger work into stacked PRs.
   - Write unit tests for behavioral changes.
   - Follow Tidy First: don't mix structural moves and behavioral changes in the same diff.
   - Don't add comments/docstrings/type hints to untouched code.
   - Use Conventional Commits: `feat: ...`, `fix: ...`, `docs: ...`, `refactor: ...`, `test: ...`, `chore: ...`.

3. **Recipes & evidence**

   - New features that affect recipe semantics should include a recipe under `examples/` if relevant.
   - Avoid checking in large binaries. Keep `examples/artifacts/` lean — CI generates the real evidence.

4. **Tests & verification**

   Before opening a PR, run:

   ```bash
   uv run python -m unittest discover -s tests
   uv build
   # if you touched runner/renderer/video:
   uv run termproof run examples/generic --video --out .termproof/ci
   ```

   CI runs unit tests, package build, wheel smoke test, generic + Pi workflow E2E, and publishes evidence artifacts.

5. **Commit & push**

   ```bash
   git add <files>
   git commit -m "feat: add wait_for_regex step

   - Implements WaitForRegexStep with regex matching
   - Adds unit tests for edge cases
   - Closes #14"
   git push -u origin HEAD
   ```

6. **Open PR**

   Use `gh`:

   ```bash
   gh pr create --title "feat: add wait_for_regex step" --body "Closes #14"
   ```

   PR body should contain:

   - What and why (link issues).
   - Test plan (unit + manual if relevant).
   - Screenshots/evidence if UX changes.

   Mark as draft early and request review when CI is green.

7. **Review & merge**

   - All CI checks must pass.
   - At least one maintainer approval.
   - Squash merge is default for feature branches.
   - Branch deleted after merge.

## Reporting issues

- Search existing issues first.
- Include: reproduction recipe (JSON), `termproof --help` output, Python version, OS, and observed vs expected.
- For security issues, email **md@mt.com** instead of filing public issues (see `SECURITY.md`).

## Compatibility contract

- **Legacy `tui-verifier` paths** (`~/.config/tui-verifier/config.yaml`, `.tui-verifier/`) remain readable but are overridden by new `termproof` paths. Do not remove this compat without a major version bump.
- **Plugin module prefix** `tui_verifier.*` is translated to `termproof.*` at load time for configured plugin references only.
- Breaking recipe semantics or artifact contracts requires a minor or major version per `docs/releases.md`.

## License

By contributing, you agree that your contributions will be licensed under the MIT License (see `LICENSE`).

## Questions?

Open an issue or draft PR — maintainers respond faster to concrete code than abstract questions.
