# Releases

TermProof releases are Python package releases plus evidence from an
end-to-end terminal verification run.

## Versioning

- Patch releases fix verifier bugs without changing recipe semantics.
- Minor releases add recipe fields, CLI commands, or artifact types.
- Major releases can change recipe semantics or artifact contracts.

The package version in `pyproject.toml` should match the release tag without
the leading `v`.

## Local Release Check

```bash
uv run python -m unittest discover -s tests
uv build
uv run termproof run examples/generic examples/multi_turn_conversation.recipe.json \
  examples/pi_workflow_readonly_review.recipe.json \
  examples/pi_workflow_guarded_edit.recipe.json \
  examples/pi_workflow_session_resume_export.recipe.json \
  examples/pi_workflow_model_context.recipe.json \
  --video --video-fps 60 --out .termproof/release
```

## GitHub Release Flow

1. Update `pyproject.toml`.
2. Push a tag such as `v0.1.1`.
3. GitHub Actions runs unit tests, builds the wheel and sdist, executes the
   receipt-backed portable TUI end-to-end suite, writes the verifier report to
   the run summary and release body, uploads evidence, and creates a GitHub
   release.
4. PyPI publishing uses GitHub trusted publishing from the release workflow
   when the repository variable `ENABLE_PYPI` is set to `true`.

The release evidence receipt lives at
[`docs/ci/evidence-receipt.json`](ci/evidence-receipt.json). Update that receipt
whenever the release or PR evidence suite changes; CI tests fail if the
workflows stop using the receipt-backed runner.

## PyPI Trusted Publishing

Before pushing the first release tag, create or claim the `termproof` project on
PyPI and add this trusted publisher:

- Owner: `md-mt`
- Repository: `termproof`
- Workflow: `release.yml`
- Environment: `pypi`

The release job must keep `permissions.id-token: write` and `environment: pypi`.
Keep the repository variable `ENABLE_PYPI` unset or set to any value other than
`true` until the PyPI project has the publisher above. The workflow will still
create the GitHub release and attach evidence, but it will skip PyPI upload.
After trusted publishing is configured, set `ENABLE_PYPI=true` before pushing
the next release tag. If PyPI reports `invalid-publisher`, unset `ENABLE_PYPI`
again until the publisher claims match the configuration above.

The GitHub Release includes `termproof-release-evidence.tgz`. That archive
contains `.termproof/release/latest-report.md`, per-recipe `report.md`,
`result.json`, `session.cast`, `final.svg`, `final.txt`, step screenshots, and
`session.mp4` videos. It also contains `evidence-receipt.json`, so each release
records which recipes and render settings produced the report.

Pull requests publish the same suite as the `termproof-ci-evidence` workflow
artifact and as a sticky PR comment. The comment includes a base-commit report,
a head-commit report, and a behavioral delta generated from each run's
`result.json` files. Same-repository PRs also copy screenshot files to the
`termproof-evidence` branch and rewrite screenshot links to raw GitHub URLs.
Videos remain in the workflow artifact; hosted video evidence is tracked in
[#69](https://github.com/md-mt/termproof/issues/69).

The release workflow intentionally uses portable recipes for public CI. The Pi
coding-agent recipes remain the showcase and can be run in environments where
Pi is installed or where deterministic Pi-style fixtures are sufficient.
