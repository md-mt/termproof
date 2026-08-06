from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = ROOT / "docker" / "termproof.Dockerfile"
WORKFLOW = ROOT / ".github" / "workflows" / "docker-image.yml"
DOCS = ROOT / "docs" / "ci" / "docker.md"


class DockerImageTest(unittest.TestCase):
    def test_dockerfile_installs_termproof_and_video_tools(self) -> None:
        text = DOCKERFILE.read_text(encoding="utf-8")

        self.assertIn("FROM rust:1.85-slim AS agg-builder", text)
        self.assertIn("cargo install --locked --git https://github.com/asciinema/agg", text)
        self.assertIn("FROM python:3.12-slim", text)
        self.assertIn("ffmpeg", text)
        self.assertIn('ENTRYPOINT ["termproof"]', text)

    def test_workflow_builds_and_publishes_ghcr_image(self) -> None:
        workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
        text = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("pull_request", workflow[True])
        self.assertIn("docker/build-push-action@v6", text)
        self.assertIn("ghcr.io/${{ github.repository_owner }}/termproof", text)
        self.assertIn("github.event_name != 'pull_request'", text)

    def test_docs_show_docker_run_pattern(self) -> None:
        text = DOCS.read_text(encoding="utf-8")

        self.assertIn("ghcr.io/md-mt/termproof:latest", text)
        self.assertIn("run .termproof/recipes", text)
        self.assertIn("upload `.termproof/runs` as an artifact", text)


if __name__ == "__main__":
    unittest.main()
