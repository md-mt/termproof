from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
DOCKERFILE = ROOT / "docker" / "termproof.Dockerfile"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "python-docker-image.yml"
DOCS = ROOT / "docs" / "ci" / "docker.md"


class DockerImageTest(unittest.TestCase):
    def test_dockerfile_installs_termproof_and_video_tools(self) -> None:
        text = DOCKERFILE.read_text(encoding="utf-8")

        self.assertIn("FROM rust:1.85-slim AS agg-builder", text)
        self.assertIn("cargo install --locked --git https://github.com/asciinema/agg", text)
        self.assertIn("FROM python:3.12-slim", text)
        self.assertIn("ffmpeg", text)
        self.assertIn('ENTRYPOINT ["termproof"]', text)

    def test_dockerfile_ships_the_python_engine_only(self) -> None:
        # This image ships the Python implementation. The Rust one has its
        # own image (`ghcr.io/md-mt/termproof-rust`, built from
        # `rust/docker/`); the only Rust in this image is the toolchain that
        # builds `agg`.
        text = DOCKERFILE.read_text(encoding="utf-8")

        self.assertNotIn("termproof-rust", text)
        self.assertNotIn("rust-builder", text)
        self.assertEqual(1, text.count("FROM rust:"))

    def test_workflow_builds_and_publishes_ghcr_image(self) -> None:
        workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
        text = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("pull_request", workflow[True])
        # Allow major bumps via dependabot — pin must stay on the correct action, not a fixed major.
        self.assertRegex(text, r"docker/build-push-action@v\d+")
        self.assertIn("ghcr.io/${{ github.repository_owner }}/termproof", text)
        self.assertIn("github.event_name != 'pull_request'", text)

    def test_docs_show_docker_run_pattern(self) -> None:
        text = DOCS.read_text(encoding="utf-8")

        self.assertIn("ghcr.io/md-mt/termproof:latest", text)
        self.assertIn("run .termproof/recipes", text)
        self.assertIn("upload `.termproof/runs` as an artifact", text)


if __name__ == "__main__":
    unittest.main()
