# TermProof Plugin Template

![TermProof Plugin](https://img.shields.io/badge/termproof-plugin-blue)
![Verified by TermProof](https://img.shields.io/badge/verified%20by-termproof-green)
[![CI](https://github.com/md-mt/termproof-plugin-template/actions/workflows/ci.yml/badge.svg)](https://github.com/md-mt/termproof-plugin-template/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/termproof-my-plugin)](https://pypi.org/project/termproof-my-plugin/)

Production-ready scaffold for writing a [TermProof](https://github.com/md-mt/termproof) plugin.

Copy this repository to start your own plugin. It contains:

- **Example step** (`WaitForRegex`) — regex-aware terminal wait with `ignore_case`/`multiline`/`dotall` flags (`src/termproof_my_plugin/steps.py`)
- **Example assertion** (`ScreenCount`) — occurrence counting with optional min/max bounds (`src/termproof_my_plugin/assertions.py`)
- **Example step-aware assertion** (`StepScreenMatches`) — regex against the screen captured after a named step, not the final one (`src/termproof_my_plugin/step_assertions.py`)
- **Example reporter** (`JsonSummaryReporter`) — machine-readable JSON summary with build provenance (`src/termproof_my_plugin/reporters.py`)
- Packaging metadata (`pyproject.toml`) with dev extras
- Tests (`tests/`) including config-wiring verification
- CI (`.github/workflows/ci.yml`) — unit tests, build, wheel smoke-test, config wiring
- README + badge pattern
- Bootstrap / mirroring procedure: `scripts/bootstrap.sh` (human gate) and `scripts/sync.sh` (ongoing sync)

Origin: prepared as reviewable source under `md-mt/termproof/plugin-template/` — see Bootstrap for mirroring to `md-mt/termproof-plugin-template`.

## Quickstart

```bash
# 1. Use this template (GitHub UI: Use this template) or clone
git clone https://github.com/md-mt/termproof-plugin-template.git my-plugin
cd my-plugin

# 2. Rename package
#    - Rename src/termproof_my_plugin -> src/<your_package>
#    - Update pyproject.toml project.name, authors, urls
#    - Replace all project URLs (Homepage, Repository, Issues) with your own
#    - Update badge links
#    - Search-and-replace termproof_my_plugin in README and tests

# 3. Install
uv pip install -e ".[dev]"   # or: pip install -e ".[dev]"

# 4. Run tests
pytest -q
python -m unittest discover -s tests -v
```

## Using the plugin in TermProof

Add to your project's `.termproof/config.yaml`:

```yaml
steps:
  wait_for_regex: termproof_my_plugin.steps:WaitForRegex

assertions:
  screen_count: termproof_my_plugin.assertions:ScreenCount
  step_screen_matches: termproof_my_plugin.step_assertions:StepScreenMatches

reporters:
  json_summary: termproof_my_plugin.reporters:JsonSummaryReporter
```

Then reference by name in recipe JSON:

```json
{
  "steps": [
    { "action": "wait_for_regex", "pattern": "Dashboard .* \\\\d+/\\\\d+" }
  ],
  "assertions": [
    { "type": "screen_count", "pattern": "TODO", "max": 0 },
    { "type": "step_screen_matches", "step": "open dashboard", "pattern": "Dashboard .* \\\\d+/\\\\d+" }
  ]
}
```

CLI still supports flags:

```bash
termproof run .termproof/recipes --reporter json_summary
```

## Protocol compatibility

| TermProof version | Supported | Notes |
|-------------------|-----------|-------|
| >=0.2.1           | yes       | Stable plugin protocols exported from `termproof.protocols` |
| >=0.1.0           | yes       | Legacy protocol import locations remain compatibility re-exports |
| legacy tui_verifier prefix | yes via compat shim | tui_verifier.*:Cls auto-remapped |

Guard version requirement in pyproject.toml: `termproof>=0.1.0`.

See TermProof #32 for protocol stability guarantee.

## Badge

Add to your plugin's README:

```markdown
[![verified by TermProof](https://img.shields.io/badge/verified%20by-termproof-green)](https://github.com/md-mt/termproof)
![TermProof Plugin](https://img.shields.io/badge/termproof-plugin-blue)
```

## Bootstrap / Mirroring Procedure

This template lives as reviewable source under `md-mt/termproof/plugin-template/` so all changes go through PR review.

To publish as `md-mt/termproof-plugin-template` (separate repo) for "Use this template" UX:

### One-time repository bootstrap (human gate)

GitHub requires an initial default-branch commit to create a repository. This is the only allowed direct default-branch commit and must be performed by a human maintainer after PR review.

1. Create empty repo `md-mt/termproof-plugin-template` via GitHub UI (no README, no .gitignore — empty).
2. From reviewed `plugin-template/` directory of a PR that is approved and squash-merged to `md-mt/termproof` main:

   ```bash
   # From termproof checkout main
   ./plugin-template/scripts/bootstrap.sh md-mt/termproof-plugin-template
   ```

   Or manually:

   ```bash
   # Copy source out of monorepo first, then init inside the copy
   cp -R plugin-template ../termproof-plugin-template
   cd ../termproof-plugin-template
   git init
   git remote add origin https://github.com/md-mt/termproof-plugin-template.git
   git add .
   git commit -m "Initial commit: TermProof plugin template"
   git branch -M main
   git push -u origin main
   ```

3. In `md-mt/termproof-plugin-template` GitHub settings:
   - Enable "Template repository" checkbox.
   - Add branch protection on main.
   - Copy CI workflow secrets if needed.

### Ongoing sync from `md-mt/termproof/plugin-template/`

After initial bootstrap, updates flow via `scripts/sync.sh`:

```bash
# Inside md-mt/termproof
./plugin-template/scripts/sync.sh ../termproof-plugin-template
cd ../termproof-plugin-template
git status
git add -A
git diff --cached   # review what will be committed
git commit -m "Sync template from termproof@SHA"
git push
# Open PR in termproof-plugin-template if protected
```

Or open PRs directly in `md-mt/termproof` that edit `plugin-template/` — once merged, run sync script and PR in the template repo.

## License

MIT License — see LICENSE. When instantiating a new project from this template,
replace the copyright holder with your own.

## Development

```bash
pytest
python -m unittest discover -s tests -v
python -m build
```

## References

- TermProof main repo: https://github.com/md-mt/termproof
- Recipe pack format: https://github.com/md-mt/termproof/blob/main/docs/recipe-packs.md
- Plugins directory (future): https://github.com/md-mt/termproof/issues/22
- First-party plugin examples: https://github.com/md-mt/termproof/issues/23
- TUI Verifier rename: https://github.com/md-mt/termproof/issues/40
- Plugin template issue: https://github.com/md-mt/termproof/issues/11
