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
   portable TUI end-to-end suite, writes the verifier report to the run summary
   and release body, uploads evidence, and creates a GitHub release.
4. PyPI publishing uses GitHub trusted publishing from the release workflow.

## PyPI Trusted Publishing

Before pushing the first release tag, create or claim the `termproof` project on
PyPI and add this trusted publisher:

- Owner: `md-mt`
- Repository: `termproof`
- Workflow: `release.yml`
- Environment: `pypi`

The release job must keep `permissions.id-token: write` and `environment: pypi`.
If PyPI reports `invalid-publisher`, the GitHub release can still be created but
the package upload will fail until the PyPI project has the publisher above.

The GitHub Release includes `termproof-release-evidence.tgz`. That archive
contains `.termproof/release/latest-report.md`, per-recipe `report.md`,
`result.json`, `session.cast`, `final.svg`, `final.txt`, step screenshots, and
`session.mp4` videos.

The release workflow intentionally uses portable recipes for public CI. The Pi
coding-agent recipes remain the showcase and can be run in environments where
Pi is installed or where deterministic Pi-style fixtures are sufficient.
