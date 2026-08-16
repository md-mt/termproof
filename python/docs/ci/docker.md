# Docker Image

TermProof ships a generic CI image from [`docker/termproof.Dockerfile`](../../docker/termproof.Dockerfile). The image includes TermProof, `agg`, and `ffmpeg`, so any CI system with Docker can run recipes and upload `.termproof/runs` as an artifact.

The GitHub workflow [`.github/workflows/python-docker-image.yml`](../../.github/workflows/python-docker-image.yml) builds the image on pull requests and publishes `ghcr.io/md-mt/termproof` on `main`, release tags, and manual dispatch.

## Usage

Run a recipe pack from any checkout:

```bash
docker run --rm \
  -v "$PWD:/workspace" \
  ghcr.io/md-mt/termproof:latest \
  run .termproof/recipes --video --video-fps 60 --out .termproof/runs
```

For local runs where evidence files should be owned by your host user:

```bash
docker run --rm \
  --user "$(id -u):$(id -g)" \
  -v "$PWD:/workspace" \
  ghcr.io/md-mt/termproof:latest \
  run examples/generic --out .termproof/docker
```

## CI Pattern

Most CI systems need the same three steps:

```bash
docker pull ghcr.io/md-mt/termproof:latest
docker run --rm -v "$PWD:/workspace" ghcr.io/md-mt/termproof:latest \
  run "$TERMPROOF_RECIPES" --out .termproof/runs $TERMPROOF_ARGS
```

Then upload `.termproof/runs` as an artifact, even when the run fails.

## Image Tags

The publish workflow emits:

| Tag | Source |
| --- | --- |
| `latest` | Default branch builds. |
| `vX.Y.Z` | Release tags. |
| `sha-<commit>` | Every pushed commit. |

The Dockerfile installs the repository checkout into the image, so release tag images contain the same code as the corresponding GitHub release.
