# Testing, GitHub Actions CI, and Release Flow

## Local Testing

### Unit Tests

Repository uses stdlib `unittest`.

Run:

```bash
uv run python -m unittest discover -s tests
# or python -m unittest discover -s tests
```

Test suite: 31 tests across 8 files:

- `test_agent_driven.py` (3) — agent prompt building, `parse_agent_output` JSON extraction cascade, `AgentDrivenRunner` operator artifact recording.
- `test_cli.py` (1) — `init` command creates recipe file (`CliTest.test_init_command_creates_recipe`); scaffolds files on disk.
- `test_config.py` (9) — cascading config merge: builtin → user → project YAML deep merge (`ConfigTest` 5 tests) plus `RegistryTest` (4 tests: register/get, unknown raises, sorted names, overwrite) covering the generic registry from `test_config.py`.
- `test_examples.py` (1) — validates example recipe JSON shape loads.
- `test_runner.py` (9) — runner orchestration: PTY mode `test_run_records_cast_and_asserts_output` spawns real processes via session backend (checks and requires `asciinema` CLI at `session.py:54-73,200-223`); process mode `test_run_process_mode_records_cast` also spawns real Python child processes; `test_runner_accepts_config`, `test_runner_defaults_to_builtin_config`, `test_runner_has_session_backend`, `test_session_backend_creates_session`, `test_runner_has_video_backend_registry`, `test_video_backend_roundtrip`, `test_runner_run_uses_video_backend` — note `test_video_backend_roundtrip` only resolves `agg_ffmpeg` from the registry and asserts non-null (`tests/test_runner.py:103-107`) without calling `render()`; `test_runner_run_uses_video_backend` sets `render_video=False` (`tests/test_runner.py:109-126`) so it verifies runner accepts a backend name but never reaches `evidence.render_artifacts()` video guard nor invokes any backend — both are registry/plumbing checks, not video rendering/artifact coverage.
- `test_scaffold.py` (1) — recipe pack scaffolding creates files on disk.
- `test_screen.py` (2) — cast replay, screen rendering.
- `test_stack_design.py` (5) — recipe discovery (`load_recipes`, `find_recipe_files`, `select_recipes`), renderer selection (`selected_renderers`), `BuildInfo.from_command`, `ReportGenerator.generate_markdown`, `BeforeAfterResult` delta computation.

Some tests (`test_runner.py:14-39,41-64,82-97`) invoke `VerificationRunner`/the session backend, which checks for and spawns the external `asciinema` CLI (`session.py:54-73,200-223`) and runs real Python child processes. `test_cli.py` and `test_scaffold.py` scaffold files rather than only constructing `Recipe` directly.

### Package Build

Declared in `pyproject.toml`:

- Build backend: `hatchling`
- Wheel includes: `tui_verifier` package
- Sdist includes: `tui_verifier`, `tests`, `examples`, `docs`, `README.md`, `LICENSE`, `pyproject.toml`, excludes `examples/artifacts`
- Console script: `tui-verify = tui_verifier.cli:main`
- Dependencies: `asciinema>=2.4.0`, `imageio-ffmpeg>=0.6.0`, `pexpect>=4.9.0`, `pyte>=0.8.2`, `pyyaml>=6.0` — `>=` denotes a lower bound with no upper bound.
- Requires Python >=3.11

Build via:

```bash
uv build
# or hatch build
```

Produces `dist/tui_verifier-*.whl` + sdist.

Smoke-test installed wheel (as release workflow does):

```bash
python -m venv .pkg-test
.pkg-test/bin/pip install dist/*.whl
.pkg-test/bin/tui-verify --help
```

### E2E Verification (Portable)

```bash
uv run tui-verify run examples/generic --video
# Or full CI-like set:
uv run tui-verify run \
  examples/generic \
  examples/multi_turn_conversation.recipe.json \
  examples/pi_workflow_readonly_review.recipe.json \
  examples/pi_workflow_guarded_edit.recipe.json \
  examples/pi_workflow_session_resume_export.recipe.json \
  examples/pi_workflow_model_context.recipe.json \
  --video --video-fps 60 --out .tui-verifier/local-ci
```

Requires `asciinema` (Python CLI) and `agg` + `ffmpeg` for video. Portable recipes use deterministic Python fixtures (`examples/generic/generic_tui.py` etc.) so they run on any machine with Python.

Pi-specific recipes (`pi_help`, `pi_version`, `pi_list`) call `examples/bin/pi-clean` which prefers `/usr/local/bin/pi_cli/pi.real` when present and can be overridden via `TUI_VERIFIER_PI_BIN`. Provider-backed Pi runs need Pi binary + credentials — run in local/private CI.

## GitHub Actions — CI (`ci.yml`)

File: `.github/workflows/ci.yml`

Triggers: `pull_request` (any), `push` to `main` only (`ci.yml:3-7`).

Permissions: `contents: read`, `issues: write`, `pull-requests: write`.

Single job `verify` on `ubuntu-latest`:

1. `actions/checkout@v4`
2. `actions/setup-python@v5` — python 3.12
3. `astral-sh/setup-uv@v5`
4. `dtolnay/rust-toolchain@stable` — needed for `agg`
5. `actions/cache@v4` — caches `~/.cargo/bin`, `registry`, `git`; key `cargo-agg-v1.9.0-${{ runner.os }}`
6. `sudo apt-get update && apt-get install -y ffmpeg`
7. `cargo install --locked --git https://github.com/asciinema/agg --tag v1.9.0` if `agg` not on PATH
8. `uv run python -m unittest discover -s tests`
9. `uv build`
10. Portable + deterministic Pi-style verification:

```bash
uv run tui-verify run \
  examples/generic \
  examples/multi_turn_conversation.recipe.json \
  examples/pi_workflow_readonly_review.recipe.json \
  examples/pi_workflow_guarded_edit.recipe.json \
  examples/pi_workflow_session_resume_export.recipe.json \
  examples/pi_workflow_model_context.recipe.json \
  --video --video-fps 60 --out .tui-verifier/ci
```

11. Publish summary — `if: always()`, appends `## TUI Verifier CI Report` + evidence artifact name + content of `.tui-verifier/ci/latest-report.md` (or fallback message) to `$GITHUB_STEP_SUMMARY`.
12. Upload artifact — `actions/upload-artifact@v4`, `name: tui-verifier-ci-evidence`, `path: .tui-verifier/ci`, `if-no-files-found: ignore`, `if: always()`.
13. PR comment — `actions/github-script@v7`, `if: always() && pull_request`, `continue-on-error: true`:
    - Reads `.tui-verifier/ci/latest-report.md` (or fallback)
    - Truncates to 55k chars with note.
    - Body: marker `<!-- tui-verifier-ci-report -->`, header `## TUI Verifier CI Report`, run link `serverUrl/owner/repo/actions/runs/runId`, evidence artifact note, `<details open><summary>latest-report.md</summary>` with report inside.
    - Lists existing comments, finds one with marker from Bot user, updates if found else creates.
14. Upload dist artifact — `actions/upload-artifact@v4`, `name: tui-verifier-dist`, `path: dist/*`

### CI Report Shape

CI attempts to create/update a sticky `TUI Verifier CI Report` comment on PRs when
GitHub permissions and API calls permit — the comment step at `ci.yml:92-95` uses
`continue-on-error: true`, so it is not guaranteed (permission/API failures are
deliberately tolerated). When successful, the comment contains:

- Link to workflow run
- Reference to `tui-verifier-ci-evidence` artifact name
- Embedded `latest-report.md` (truncated to 55k chars if needed)
- Note that report links point to files inside artifact

The same markdown also appears in GitHub Run Summary for PR and main commits
(handled by a separate `if: always()` summary step).

## GitHub Actions — Release (`release.yml`)

File: `.github/workflows/release.yml`

Triggers: `push` tags `v*.*.*`, manual `workflow_dispatch` (`release.yml:3-7`).

Permissions: `contents: write` (create release), `id-token: write` (trusted publishing).

Environment: `environment: pypi` for PyPI trusted publishing.

Job `release` on `ubuntu-latest`, same setup as CI plus:

- Run unit tests, build package.
- Smoke-test installed wheel:

```bash
python -m venv .pkg-test
.pkg-test/bin/pip install dist/*.whl
.pkg-test/bin/tui-verify --help
```

- Release verification:

```bash
uv run tui-verify run \
  examples/generic \
  examples/multi_turn_conversation.recipe.json \
  examples/pi_workflow_readonly_review.recipe.json \
  examples/pi_workflow_guarded_edit.recipe.json \
  examples/pi_workflow_session_resume_export.recipe.json \
  examples/pi_workflow_model_context.recipe.json \
  --video --video-fps 60 --out .tui-verifier/release
tar -czf tui-verifier-release-evidence.tgz -C .tui-verifier release
```

- Write release notes `release-notes.md` (`if: always()`):

```md
## TUI Verifier Release Evidence

Evidence archive: `tui-verifier-release-evidence.tgz`
Report links point to files inside that archive.

<content of latest-report.md>
```

Append same to `GITHUB_STEP_SUMMARY`.

- Upload release evidence artifact (same as CI but `release` dir) + dist artifact.
- Create GitHub Release — `softprops/action-gh-release@v2`, `if: startsWith(github.ref, 'refs/tags/v')`, `body_path: release-notes.md`, `files: dist/*` + `tui-verifier-release-evidence.tgz`.
- Publish to PyPI — `pypa/gh-action-pypi-publish@release/v1`, `if: startsWith(github.ref, 'refs/tags/v')` — uses OIDC trusted publishing (no token, relies on `environment: pypi` + `id-token: write`).

Tag pushes trigger the Release workflow, not CI. `ci.yml` triggers only PRs and pushes to `main`; `release.yml` is the tag-triggered workflow. A tag push produces a Release run (plus GitHub Release body/archive when tag conditions hold), not a CI run, unless the tagged commit was also pushed to `main` via a separate branch push.

## Versioning Contract

From `docs/releases.md`:

- Patch: verifier bug fixes without changing recipe semantics.
- Minor: add recipe fields, CLI commands, or artifact types.
- Major: may change recipe semantics or artifact contracts.
- `pyproject.toml` version should match tag without leading `v`.

Example release prep:

1. Update `pyproject.toml` version.
2. Push tag `v0.1.1` (triggers Release workflow, not CI).
3. Release workflow verifies, creates GitHub Release with evidence archive, publishes wheel+sdist to PyPI via trusted publishing. CI only runs on PRs and merges to `main`, not on tag push alone.

## What CI Intentionally Does NOT Run

From README: public CI runs deterministic Pi-style workflows instead of provider-backed live Pi sessions. That keeps PR/main/release reproducible. Real Pi CLI surface (`pi_help`, `pi_version`, `pi_list` recipes) calls `examples/bin/pi-clean` which prefers `/usr/local/bin/pi_cli/pi.real`; those are covered locally via `uv run tui-verify run examples/pi_help.recipe.json --video` etc., with `TUI_VERIFIER_PI_BIN` override.

## Recommended Downstream CI Usage

From README — for a project with its own recipe pack at `.tui-verifier/recipes`:

```yaml
- name: Run TUI verification
  run: |
    uv run tui-verify run .tui-verifier/recipes \
      --video --video-fps 60 --out .tui-verifier/ci

- name: Upload TUI evidence
  uses: actions/upload-artifact@v4
  if: always()
  with:
    name: tui-verifier-evidence
    path: .tui-verifier/ci
    if-no-files-found: ignore
```
