# Evidence hosting: retention model and owner runbook

This page is the retention and deletion model for CI evidence, and the runbook
for provisioning the object-storage half of it. It covers where evidence lives,
how long each kind is kept, how it is deleted, and what credentials the publish
step may hold. It exists for
[#118](https://github.com/md-mt/termproof/issues/118), whose acceptance criteria
this page answers one by one at the end.

> **Status: not provisioned.** The upload mechanism exists —
> `ArtifactPublisher` and the S3/R2 helpers in
> `termproof/evidence_publish.py`, driven by the "Publish video evidence to
> R2/S3" step in the `verify` job of `.github/workflows/python-ci.yml` — but no
> bucket and no credentials are provisioned for this repository. The
> `TERM_PROOF_VIDEO_*` settings are unset, so that step takes its early exit on
> every run and uploads nothing. **Nothing is hosted anywhere today** beyond
> the screenshot branch and the workflow artifacts described below. Anywhere
> this page describes bucket behaviour, read it as "once the owner completes
> the runbook", not as a description of the present.

Related tracking: [#69](https://github.com/md-mt/termproof/issues/69) asked for
video evidence hosted outside Actions artifacts, with three acceptance
criteria — PR video links that resolve without downloading the artifact,
durable hosted release videos, and Actions artifacts remaining the canonical
fallback bundle. It was **closed as not planned on 2026-08-19**, so it will not
be satisfied as written; this model adopts its fallback criterion explicitly
and carries the other two as owner-gated outcomes of the runbook below.

---

## Evidence classes

There are four places evidence can land. They have different lifetimes because
they answer different questions: a PR screenshot answers "what changed in this
review", a release bundle answers "what did this version do", and only the
second needs to outlive the conversation that produced it.

| Class | Where it lives | Produced by |
| --- | --- | --- |
| PR screenshots | `termproof-evidence` branch, `pr/<pr>/<run>/{base,head}/…`, read via `raw.githubusercontent.com` | `evidence_publish screenshots` + "Publish screenshot evidence branch" step; same-repository PRs only |
| PR videos | S3-compatible bucket, `termproof/videos/pr/<pr>/<run>/{base,head}/…` (prefix configurable) | `evidence_publish publish-videos`; **no-op until provisioned** |
| PR fallback bundle | Actions artifact `termproof-ci-evidence` (`.termproof/ci`, `.termproof/pr-base`, PR comment body) | "Upload verification evidence" step, `if: always()` |
| Release evidence | GitHub Release asset `termproof-release-evidence.tgz`, plus the `termproof-release-evidence` Actions artifact | `.github/workflows/python-release.yml` |

Two honest gaps in that table, both deliberate scope lines rather than
oversights:

- **The release workflow has no bucket publish step.** Release videos exist
  only inside the Release asset today. Wiring `publish-videos` into
  `python-release.yml` is a follow-up the owner can take once a bucket exists;
  until then #69's "release reports link to durable hosted videos" is met by
  the Release asset itself being durable, not by per-video links.
- **Pushes to `main` publish nothing hosted.** The screenshot and video steps
  are gated on `github.event_name == 'pull_request'`; a `main` run produces
  the artifact bundle only.

## Retention

- **PR evidence — 90 days, then prunable.** Both the screenshot branch payload
  and the bucket's `termproof/videos/pr/*` keys are review aids for an open
  conversation. Ninety days matches `hosting.retention_days` in
  [`docs/ci/evidence-receipt.json`](ci/evidence-receipt.json) and the default
  Actions artifact window, so no surface outlives the others by accident.
  After 90 days a pruned screenshot or an expired video 404s; the PR comment
  keeps the (now dead) link, which is accepted behaviour — see "Missing,
  partial and expired evidence" below.
- **Release evidence — permanent.** The Release asset is kept for the life of
  the release. Nothing in this model ever expires it. The bucket policy below
  grants the CI identity no access outside `termproof/videos/*` and denies
  delete within that scope, so CI as currently scoped could not delete a
  future release prefix either; a release prefix outside `termproof/videos/`
  would need its own explicit policy change before CI could write there at
  all. Note that denying delete does not prevent *overwrite* — see
  "Cross-branch overwrite prevention".
- **Actions artifacts — GitHub's retention.** The upload steps set no
  `retention-days`, so the repository default applies (90 days unless the
  owner changes it in repository settings). Artifacts are the canonical
  fallback bundle (#69's third criterion): every hosted link is additive, and
  the full evidence for a run is always in the artifact regardless of bucket
  state.

## Deletion mechanics

- **Bucket (PR videos): lifecycle rule, not CI.** The owner configures the
  bucket to expire objects under the PR prefix after 90 days; deletion is
  performed by the storage service. The CI credential is denied
  `s3:DeleteObject` within its scope (see the policy below), so a compromised
  or buggy publish step cannot *delete* evidence — including its own run's.
  Delete is not overwrite, though: `s3:PutObject` to an existing key replaces
  it, and the credential can put anywhere under `termproof/videos/*` (see the
  residual risk under "Cross-branch overwrite prevention"). S3 lifecycle
  configuration sketch:

  ```json
  {
    "Rules": [
      {
        "ID": "expire-pr-video-evidence",
        "Status": "Enabled",
        "Filter": { "Prefix": "termproof/videos/pr/" },
        "Expiration": { "Days": 90 }
      }
    ]
  }
  ```

  On Cloudflare R2 the equivalent is a bucket lifecycle rule with the same
  prefix and age. If `TERM_PROOF_VIDEO_PREFIX` is changed from its default,
  the lifecycle prefix must change with it.

- **Screenshot branch: manual pruning; no automation exists.** To prune,
  check out `termproof-evidence`, delete the `pr/<pr>/` directories whose runs
  are older than 90 days (run ids increase monotonically, and each run
  directory names its PR), commit, and push. Two caveats belong in the model
  rather than in a footnote: deleting from the branch tip does not erase the
  blobs from git history, so pruning is a size and tidiness measure, not an
  erasure guarantee; and reclaiming the space requires rewriting the branch
  (an orphan squash), which invalidates every outstanding raw link at once
  and should be treated as a deliberate, announced act.

- **Artifacts and Release assets** expire or persist per GitHub's own rules
  above; nothing in this repository deletes them.

## Privacy: why the links look the way they do

Terminal evidence is a record of process output. Casts, screenshots and
reports can contain file paths, environment details, and — for a recipe that
drives a real tool carelessly — tokens or other sensitive text that happened
to reach the screen. The shipped CI recipes run deterministic fixtures, but
the model cannot assume every future recipe does.

That cuts both ways, and the current posture is a choice, not a default:

- Screenshot links are already public: the repository is public, so anything
  on the `termproof-evidence` branch is world-readable via
  `raw.githubusercontent.com`. Publishing a screenshot is publishing it.
- A bucket served under a public base URL (an `r2.dev` subdomain, a public S3
  website endpoint) makes videos equally public and guessable — keys are
  structured (`pr/<pr>/<run>/…`), not capabilities.
- The alternative postures are a private bucket with no link rewriting (the
  artifact bundle stays the only route to videos, which is today's behaviour
  and the safe default until the owner decides otherwise) or signed URLs.
  Signed URLs are **not implemented**: the publisher reports a stable public
  URL per key, and nothing mints or refreshes an expiring signature. Treat
  "private evidence with browsable links" as unbuilt, not as a configuration
  option.

The runbook below therefore stops at least-privilege *writing*. Whether the
read side is public is the owner's provisioning decision, and it should be
made knowing the links are permanent-looking, structured, and pasted into PR
comments.

## Owner runbook: provisioning least-privilege publishing

Everything in this section is owner-only: it creates cloud resources and
repository secrets, which cannot be done from a pull request. The repository
side is already wired to consume the repository settings below (step 2 also
lists two CLI-only names CI does not pass, so nothing else needs creating).

### 1. Create the bucket and the CI identity

Create one S3-compatible bucket (AWS S3 or Cloudflare R2) dedicated to
TermProof evidence, and one identity used only by the publish step. The
identity may put objects under the `termproof/videos/` prefix and nothing
else; the publisher never reads objects back (`_upload_file` in
`termproof/evidence_publish.py` only uploads via `aws s3 cp` or boto3
`upload_file`), so no read action is granted. Deletion belongs to the
lifecycle rule above, so it is explicitly denied within the same scope
rather than merely ungranted. S3 policy, with `<bucket>` replaced:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "TermProofEvidenceWrite",
      "Effect": "Allow",
      "Action": ["s3:PutObject"],
      "Resource": "arn:aws:s3:::<bucket>/termproof/videos/*"
    },
    {
      "Sid": "NoDeleteFromCI",
      "Effect": "Deny",
      "Action": ["s3:DeleteObject", "s3:DeleteObjectVersion"],
      "Resource": "arn:aws:s3:::<bucket>/termproof/videos/*"
    }
  ]
}
```

Notes on what is deliberately absent: no `s3:GetObject` (the publisher never
reads), no `s3:ListBucket` (the publisher uploads named files one at a time
via `aws s3 cp` or boto3; it never lists), no bucket-level actions, and no
access outside `termproof/videos/*`. Two things to verify at provisioning
rather than pre-grant: `aws s3 cp` / boto3 `upload_file` may use multipart
upload for a large mp4, in which case `s3:AbortMultipartUpload` and
`s3:ListMultipartUploadParts` (scoped to the same resource) may also be
needed — test with a representative large file before adding them. And
remember `s3:PutObject` *can overwrite* any existing key inside
`termproof/videos/*`; the delete deny does not prevent that (see
"Cross-branch overwrite prevention"). On R2 there is no equivalent policy:
an R2 API token is bucket-wide (it cannot be scoped to the
`termproof/videos/` prefix) and cannot express the delete deny, so on R2 the
token plus the lifecycle rule gives a strictly weaker guarantee — a
dedicated bucket is the containment there. Do not enable public access or an
`r2.dev` subdomain until the privacy question above has an explicit answer.

Then add the 90-day lifecycle rule from "Deletion mechanics".

### 2. Set the repository settings (names only)

Secrets (Settings → Secrets and variables → Actions → Secrets):

| Name | Value |
| --- | --- |
| `TERM_PROOF_VIDEO_BUCKET` | bucket name |
| `AWS_ENDPOINT_URL_S3` | `https://<accountid>.r2.cloudflarestorage.com` for R2; omit for AWS S3 |
| `AWS_ACCESS_KEY_ID` | CI identity's access key |
| `AWS_SECRET_ACCESS_KEY` | CI identity's secret key |

Variables (same page, Variables tab — these are not sensitive; fork safety
below does not rely on whether a fork run can read them):

| Name | Value |
| --- | --- |
| `TERM_PROOF_VIDEO_BASE_URL` | public **bucket-root** URL the bucket is read under, **without the key prefix**, e.g. `https://pub-xxx.r2.dev` |
| `TERM_PROOF_VIDEO_PREFIX` | optional; key prefix, default `termproof/videos` |

`TERM_PROOF_VIDEO_BASE_URL` is the bucket root everywhere — this is the one
convention both code paths now use, and a test pins that they agree
(`test_publish_url_equals_compose_url_for_same_file` in
`tests/test_ci_evidence.py`). The publisher writes keys as
`<prefix>/pr/<pr>/<run>/{base,head}/…` and forms each hosted URL as
bucket root + full key, rewriting report links to those URLs as it goes. The
"Compose TUI verification report" step starts from the same bucket root,
appends `<prefix>/pr/<pr>/<run>` itself (prefix from
`TERM_PROOF_VIDEO_PREFIX`, default `termproof/videos`), and lets the
rewriter append `/base` or `/head` and the relative path. Both therefore
produce `https://pub-xxx.r2.dev/termproof/videos/pr/<pr>/<run>/head/…` for
the same file. Setting the base URL to a prefix-inclusive value would
double-prefix the publisher's URLs (`…/termproof/videos/termproof/videos/…`)
and bake 404s into reports at publish time, before compose could repair
them — do not do it.

Other names the `publish-videos` CLI reads, for completeness. As the
workflow is currently wired these two are *not* passed in by CI, so they
only affect a direct/local invocation; do not create repository settings
with these names expecting CI to consume them:

| Name | Read by | Meaning |
| --- | --- | --- |
| `R2_ENDPOINT_URL` | `evidence_publish publish-videos` (`--endpoint-url` default) | Alias fallback when `AWS_ENDPOINT_URL_S3` is unset. The workflow only passes `AWS_ENDPOINT_URL_S3`, so for CI set that secret, not this. |
| `TERM_PROOF_ARTIFACT_PUBLISHER` | `evidence_publish publish-videos` (`--publisher` default) | Publisher registered under `artifact_publishers` in config; default `s3`. The workflow does not set it, so CI always uses `s3`. |

A third, look-alike name needs a warning rather than a value:
`hosting.video_base_url` in [`docs/ci/evidence-receipt.json`](ci/evidence-receipt.json).
That receipt field is *not* `TERM_PROOF_VIDEO_BASE_URL` and does not follow
the bucket-root convention. In `ci_evidence` it is treated as an
already-resolved prefix — compose would append only `/base` or `/head`, and
the run-target rewriting would append only the path relative to the output
directory — so it cannot reproduce the `pr/<pr>/<run>` publish layout from a
bucket root, and copying the bucket-root variable into it would produce
wrong links. The repository receipt leaves it empty (`""`), which disables
that path; leave it empty. Receipt fields `hosting.bucket_env`,
`hosting.video_base_url_env`, `hosting.endpoint_env` and `hosting.prefix`
merely *name* the settings above; `hosting.retention_days` is the 90-day
value from "Retention".

Beyond the workflow plumbing the publish steps also receive (`PR_NUMBER`,
`RUN_ID`/`GITHUB_RUN_ID`, `GITHUB_REPOSITORY`), no other names are read.
The divergent `python/scripts/publish_evidence.py` and its `EVIDENCE_*` names
(`EVIDENCE_BUCKET`, `EVIDENCE_BASE_URL`, `EVIDENCE_ENDPOINT`,
`EVIDENCE_PREFIX`, default prefix `termproof`) were removed with this
change: it duplicated `publish-videos` under different setting names and a
different key layout, and nothing in the workflows, docs or code referenced
it. Do not resurrect those names; everything goes through
`termproof.evidence_publish publish-videos` and the `TERM_PROOF_VIDEO_*`
names above.

### 3. Fork safety

The bucket credentials are used by exactly one step — "Publish video
evidence to R2/S3" — and that step runs only for pull requests
(`github.event_name == 'pull_request'`), never on pushes: a push to `main`
does not use these credentials at all and produces only the artifact bundle.
Within pull requests they are used only for same-repository PRs.
Fork pull requests publish nothing and their PR comments carry no hosted
links — they fall back to the artifact bundle, exactly as an unprovisioned
run does.

Two independent mechanisms hold this. The real boundary is that GitHub
withholds repository secrets from `pull_request` runs on forks, so the
publish step's credential environment is empty there. The workflow *also*
checks explicitly, as a fail-safe: even if variables were visible to a fork
run, a set `TERM_PROOF_VIDEO_BASE_URL` alone would not cause an upload or a
link, because the "Publish video evidence to R2/S3" step exits before any
upload when `head.repo.full_name` differs from the repository and the
compose step only adds `--video-base-url` for same-repository PRs, so a fork
comment cannot link to objects that were never uploaded. The explicit check
also keeps the guarantee if the trigger ever changes (a move to
`pull_request_target` would otherwise hand secrets to code from forks; do not
make that move for this job). The screenshot branch step has had the same
same-repository gate since it was introduced.

### 4. Cross-branch overwrite prevention

Keys are namespaced per pull request and per run, in both stores, by code
rather than by convention:

- Bucket: `_video_manifest_entries` in `termproof/evidence_publish.py` builds
  `<prefix>/pr/<pr>/<run>/{base,head}/<relative path>`.
- Branch: `prepare_screenshot_evidence` / `prepare_video_evidence` stage into
  `pr/<pr>/<run>/{base,head}/…`.

As constructed by that code, a run writes only inside its own
`<pr>/<run>` namespace, so two branches — or two runs of one PR — do not
overwrite each other's evidence in normal operation. That protection is
*code construction, not credential enforcement*, and the distinction is the
residual risk of this model: `s3:PutObject` can overwrite any existing key,
and the CI credential may put anywhere under `termproof/videos/*`. The
credentials therefore do not enforce per-PR isolation — a compromised
credential, or a buggy/hostile change to the key-building code running with
it, could overwrite another PR's or run's objects within that prefix, and
the `DeleteObject` deny would not stop it (delete is not overwrite; on R2
the token is bucket-wide besides). Accepting that risk is part of
provisioning; removing it would need per-PR credentials or a signing
service, neither of which this model builds.

One further gap in the code construction itself: when `pr_number` or
`run_id` is omitted, the bucket layout collapses to
`<prefix>/{base,head}/…`, which *can* overwrite across runs. CI always
supplies both (the workflow passes `--pr-number` and `--run-id`), so the gap
is reachable only from a local invocation that leaves them unset; a local
publish should pass both, or use `--dry-run`.

### 5. Verify provisioning

1. Open a same-repository PR that touches `python/**`. In the `verify` job,
   "Publish video evidence to R2/S3" should log `N videos published to
   s3://<bucket>/…` instead of the not-configured skip line.
2. Open one video link from the PR comment and confirm it resolves without
   downloading the `termproof-ci-evidence` artifact (#69's first criterion).
3. Confirm an object exists at `termproof/videos/pr/<pr>/<run>/head/…` in the
   bucket console, and that the lifecycle rule shows the `pr/` prefix at 90
   days.
4. Negative checks: assume the CI credential and confirm `DeleteObject`, a
   `PutObject` outside `termproof/videos/*`, and `GetObject` are all denied
   (on S3; on R2 confirm instead that the token reaches only this bucket —
   prefix scope and a delete deny cannot be expressed there).
5. Upload one representative large mp4 with the CI credential; if the
   transfer goes multipart and fails on abort/list-parts, add
   `s3:AbortMultipartUpload` / `s3:ListMultipartUploadParts` scoped to
   `termproof/videos/*` (see step 1) and retest.

## Missing, partial and expired evidence

What the code does today, which is what the tests pin:

- **Missing (nothing published).** With no bucket configured, or on a fork,
  the publish step no-ops with a log line naming the reason, the compose step
  adds no video base URL, and reports keep their local artifact-relative
  paths. The PR comment says hosted video links are tracked separately and
  points at the artifact. Nothing fabricates a URL for bytes that are not
  there: at the report layer, `rewrite_video_links` /
  `rewrite_screenshot_links` only rewrite a path when the file exists under
  the evidence root and a non-empty base URL was given, and
  `url_map_from_published` only credits artifacts the publisher reports as
  both stored and addressable.
- **Partial (some artifacts declined).** A publisher refusal is reported with
  its `detail`, the manifest records only what was stored, report links are
  rewritten only for stored artifacts, and `publish-videos` exits non-zero —
  a partial publish is a failed publish (#163). In CI the step is currently
  `continue-on-error: true`, so the failure is visible in the step log without
  failing the job; whether that leniency survives provisioning is an owner
  call worth revisiting once uploads are expected to succeed.
- **Expired (published, then pruned or lifecycle-expired).** There is **no**
  expiry handling at the link layer: rewriting is purely textual, nothing
  probes a URL for a 404, and nothing annotates or strips a dead link. An
  expired PR video leaves a dead link in an old PR comment next to the
  artifact pointer, and that is the designed end-state of the 90-day policy
  rather than a defect to paper over. If dead-link annotation is ever wanted
  it is a new feature (a link checker in the comment path), explicitly out of
  scope here.

## Criterion status for #118

| #118 criterion | Status |
| --- | --- |
| Document the retention and deletion model | Met by this page |
| Publish with least-privilege credentials | Repo-ready, pending owner: policy, names and wiring above; no credential exists until provisioned |
| Stable links in reports, checks and PR summaries | Repo-ready, pending owner: rewriting exists and is fork- and unset-safe; links resolve only once a bucket exists |
| Prevent cross-branch overwrites and fork credential exposure | Repo-side by code construction: `pr/<pr>/<run>` key layout, explicit fork guards, same-repository gates. Not credential-enforced — `PutObject` can overwrite anywhere under `termproof/videos/*`; residual risk stated above |
| Test missing, partial and expired behaviour | Met for missing and partial; expired behaviour is pinned as "no liveness handling by design" and documented above |
| Satisfy #69 | Cannot be met as written: #69 was closed not-planned (2026-08-19). Its fallback criterion is adopted; its link criteria become verifiable only after provisioning |

---
