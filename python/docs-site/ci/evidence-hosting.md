# Durable Evidence Hosting

GitHub Actions artifacts expire, so TermProof's evidence has a documented
retention model with an optional S3-compatible store (Cloudflare R2 or AWS S3)
for PR videos. The full model — evidence classes, deletion mechanics, privacy
posture, and the least-privilege provisioning runbook — lives in
[`python/docs/evidence-hosting.md`](https://github.com/md-mt/termproof/blob/main/python/docs/evidence-hosting.md).

> **Status: not provisioned.** The upload code ships
> (`termproof.evidence_publish publish-videos`, through the
> `ArtifactPublisher` protocol), but this repository has no bucket and no
> publishing credentials yet, so the CI step no-ops on every run. Until the
> owner completes the runbook, hosted video links do not exist; the tables
> below describe the model once provisioned.

## Retention model

| Store | Retention | Use |
| --- | --- | --- |
| `termproof-ci-evidence` artifact | Repository default (90 days) | Canonical fallback bundle |
| `termproof-evidence` branch (`pr/{pr}/{run}/`) | 90 days, then prunable | Screenshot links in PR comments |
| Bucket `termproof/videos/pr/{pr}/{run}/` | 90 days (lifecycle rule) | Video links in PR comments, once provisioned |
| Release `termproof-release-evidence.tgz` | Permanent (GitHub Release) | Release provenance |

## Publish from CI (once provisioned)

Repository settings, names only — values come from the owner's bucket; see the
runbook for the exact least-privilege policy:

- Secrets: `TERM_PROOF_VIDEO_BUCKET`, `AWS_ENDPOINT_URL_S3` (R2 only),
  `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`. On S3 the policy is
  `s3:PutObject` only on `termproof/videos/*` (the publisher never reads),
  with delete explicitly denied in that scope. On R2 that policy cannot be
  expressed: an R2 token is bucket-wide, cannot be scoped to the
  `termproof/videos/` prefix, and cannot deny delete — so the R2 guarantee
  is weaker and a dedicated bucket is the containment.
- Variables: `TERM_PROOF_VIDEO_BASE_URL` (public **bucket-root** URL, without
  the key prefix), `TERM_PROOF_VIDEO_PREFIX` (optional, default
  `termproof/videos`).

The `verify` job in `.github/workflows/python-ci.yml` already runs the publish
step and rewrites report links through `termproof.ci_evidence`. Fork pull
requests never receive credentials and never get hosted links; their evidence
is the artifact bundle, as is everyone's until provisioning happens.
