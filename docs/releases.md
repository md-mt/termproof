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
uv run termproof run examples/generic examples/colorstress \
  examples/multi_turn_conversation.recipe.json \
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
PyPI and add this **Trusted Publisher** (PyPI → Manage → Publishing → Add a new
pending publisher → GitHub):

- PyPI project name: `termproof`
- Owner: `md-mt`
- Repository: `termproof`
- Workflow: `release.yml`
- Environment: `pypi`

> PyPI matches the OIDC claim `job_workflow_ref` against the workflow filename
> and the `environment` claim against the GitHub environment. Both must match
> exactly. Keep `.github/workflows/release.yml` with `permissions: id-token: write`
> and `jobs.release.environment: pypi` — see `tests/test_release_docs.py` for the
> regression guard. If the workflow file is renamed or the environment name
> changes, update the PyPI publisher to match or publishing will fail with
> `invalid-publisher`.

Repository variable gate:

- Keep `ENABLE_PYPI` unset (or any value other than `true`) until the publisher
  above is configured. The workflow still creates the GitHub release and attaches
  evidence, but it skips PyPI upload.
- After trusted publishing is configured, set `ENABLE_PYPI=true` before pushing
  the next release tag.
- If PyPI reports `invalid-publisher`, unset `ENABLE_PYPI` again until the
  publisher claims match the configuration above.

Verify after a release publish:

```bash
# Smoke-test the published package (isolated venv, no repo state)
bash scripts/smoke-install.sh              # latest from PyPI
bash scripts/smoke-install.sh 0.2.0        # pinned version
bash scripts/smoke-install.sh "" dist/*.whl  # local wheel without touching PyPI
```

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

## Hosted Video Evidence (R2/S3)

Videos are large and not suitable for the `termproof-evidence` branch. When
video hosting is configured, PR and release reports link directly to hosted
`session.mp4` files so reviewers don't need to download the full artifact.

Hosting is **S3-compatible** so it works with either AWS S3 or Cloudflare R2
without code changes:

| Env var | Purpose |
| --- | --- |
| `TERM_PROOF_VIDEO_BUCKET` | Bucket name (required to publish) |
| `TERM_PROOF_VIDEO_PREFIX` | Key prefix, default `termproof/videos` |
| `TERM_PROOF_VIDEO_BASE_URL` | Public URL prefix for the bucket (required to rewrite links), e.g. `https://pub-xxx.r2.dev/termproof/videos` or `https://my-bucket.s3.amazonaws.com/termproof/videos` |
| `AWS_ENDPOINT_URL_S3` | S3-compatible endpoint. Set to your R2 endpoint `https://<accountid>.r2.cloudflarestorage.com` for R2; leave unset for AWS S3. `R2_ENDPOINT_URL` is also accepted as an alias. |

Publish from CI or locally:

```bash
# Stage + publish videos for the current PR (uses env vars above)
uv run python -m termproof.evidence_publish publish-videos \
  --base-dir .termproof/pr-base --head-dir .termproof/ci \
  --bucket "$TERM_PROOF_VIDEO_BUCKET" --prefix "$TERM_PROOF_VIDEO_PREFIX" \
  --pr-number "$PR_NUMBER" --run-id "$GITHUB_RUN_ID" \
  --video-base-url "$TERM_PROOF_VIDEO_BASE_URL" --out .termproof/evidence-branch

# Dry-run: build manifest without uploading (useful for verification)
uv run python -m termproof.evidence_publish publish-videos \
  --base-dir .termproof/pr-base --head-dir .termproof/ci \
  --bucket my-bucket --dry-run
```

What happens when publishing:

1. Each `session.mp4` under `base_dir`/`head_dir` is uploaded to
   `s3://$BUCKET/$PREFIX/pr/$PR_NUMBER/$RUN_ID/{base,head}/<relative-path>`.
2. A `video-manifest.json` is written to the output branch payload.
3. When `--video-base-url` is set, `report.md` / `latest-report.md` links for
   `session.mp4` are rewritten to `{base_url}/pr/{pr}/{run}/{scope}/...`.

The PR comment (`termproof.ci_evidence comment`) accepts `--video-base-url` and
rewrites video links the same way it rewrites screenshot links. When
`TERM_PROOF_VIDEO_BASE_URL` is set in CI, the existing screenshot flow needs no
extra steps — video links become browsable alongside screenshots.

Retention: the bucket should be configured with a lifecycle rule (e.g. 90 days
for `termproof/videos/pr/*`), matching `docs/ci/evidence-receipt.json` →
`hosting.retention_days`. The workflow artifact remains the canonical fallback —
hosted URLs are additive, not a replacement. See [#69](https://github.com/md-mt/termproof/issues/69).

The release workflow intentionally uses portable recipes for public CI. The Pi
coding-agent recipes remain the showcase and can be run in environments where
Pi is installed or where deterministic Pi-style fixtures are sufficient.
