# CI Integration

TermProof CI integrations run recipes, upload `.termproof/runs`, and surface reports where reviewers already work.

## GitHub Actions

Use the reusable action in `action.yml` or copy the workflow pattern from `.github/workflows/ci.yml`.

## GitLab CI

Start from `templates/gitlab/.gitlab-ci.yml` and `docs/ci/gitlab.md`.

## CircleCI

Use `.circleci/orb.yml` as the orb source and `docs/ci/circleci.md` for registry usage.

## Docker

Use `ghcr.io/md-mt/termproof:latest` from any CI runner with Docker.

```bash
docker run --rm -v "$PWD:/workspace" ghcr.io/md-mt/termproof:latest \
  run .termproof/recipes --out .termproof/runs
```
