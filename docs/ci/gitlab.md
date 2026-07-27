# GitLab CI

TermProof can run in GitLab CI by installing the CLI, executing a recipe pack, uploading the evidence directory, and optionally posting the Markdown report back to a merge request.

Use [`templates/gitlab/.gitlab-ci.yml`](../../templates/gitlab/.gitlab-ci.yml) as a starting point:

```bash
curl -L https://raw.githubusercontent.com/md-mt/termproof/main/templates/gitlab/.gitlab-ci.yml -o .gitlab-ci.yml
```

The template runs:

```bash
uvx --from git+https://github.com/md-mt/termproof.git termproof run "$TERMPROOF_RECIPES" --out .termproof/runs $TERMPROOF_ARGS
```

By default it records video evidence for `.termproof/recipes`. Override these variables in your project or pipeline:

| Variable | Default | Purpose |
| --- | --- | --- |
| `TERMPROOF_RECIPES` | `.termproof/recipes` | Recipe file or recipe pack directory to run. |
| `TERMPROOF_ARGS` | `--video --video-fps 60 --xml-path .termproof/runs/latest-report.xml` | Extra `termproof run` flags. |
| `GITLAB_TOKEN` | unset | Optional project/group variable with `api` scope for merge request comments. |

## Evidence Artifacts

The `termproof` job uploads `.termproof/runs` with `when: always`, so failed runs still include `session.cast`, screenshots, text snapshots, videos, JSON results, and Markdown reports.

GitLab keeps the evidence for 14 days by default. Adjust `artifacts.expire_in` to match your review and compliance window.

## Merge Request Comments

The `termproof:mr-comment` job runs only for merge request pipelines. When `GITLAB_TOKEN` is available, it posts `.termproof/runs/latest-report.md` to the merge request notes API. Without a token, the job prints setup guidance and exits successfully.

Set `GITLAB_TOKEN` as a masked CI/CD variable with `api` scope. Protected variables are only available to protected branches, so use an unprotected project access token if merge request pipelines from feature branches need comments.

## JUnit Reports

GitLab can show TermProof results in the pipeline test report when the run writes JUnit XML:

```yaml
variables:
  TERMPROOF_ARGS: --xml-path .termproof/runs/latest-report.xml
```

The template already declares `.termproof/runs/latest-report.xml` under `artifacts.reports.junit`.
