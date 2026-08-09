# Durable Evidence Hosting

GitHub Actions artifacts expire. TermProof now supports durable hosting via S3-compatible storage (Cloudflare R2 or AWS S3) with least-privilege publishing and stable PR links.

## Retention model

| Store | Retention | Use |
| --- | --- | --- |
| `termproof-ci-evidence` artifact | 90 days (GitHub) | Debug download |
| R2/S3 `termproof/pr/{pr}/{run}/` | 1 year (configurable) | Stable PR comment links |
| Release `termproof-release-evidence.tgz` | Permanent (GitHub Release) | Release provenance |

## Publish from CI

Set repository secrets/variables:

- `EVIDENCE_BUCKET` — R2/S3 bucket name
- `EVIDENCE_ENDPOINT` — endpoint URL (e.g., `https://<account>.r2.cloudflarestorage.com`)
- `EVIDENCE_BASE_URL` — public URL prefix (e.g., `https://evidence.termproof.dev`)
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` — least-privilege writer (PutObject only on `termproof/pr/*`)

CI step:

```yaml
- run: python scripts/publish_evidence.py --head-dir .termproof/ci --base-dir .termproof/pr-base --pr-number ${{ github.event.pull_request.number }} --run-id ${{ github.run_id }}
  env:
    EVIDENCE_BUCKET: ${{ secrets.EVIDENCE_BUCKET }}
    EVIDENCE_ENDPOINT: ${{ vars.EVIDENCE_ENDPOINT }}
    EVIDENCE_BASE_URL: ${{ vars.EVIDENCE_BASE_URL }}
    AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
    AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
```

Stable links are injected into the PR comment via `rewrite_screenshot_links` (existing `evidence_publish.py`).

## PR comment

The existing `termproof-ci-report` comment now includes stable screenshot URLs when `publish_evidence.py` succeeds; otherwise it falls back to `raw.githubusercontent.com` links from the `termproof-evidence` branch.

See `scripts/publish_evidence.py --help` for dry-run mode.
