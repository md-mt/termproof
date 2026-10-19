from __future__ import annotations

import re
import tomllib
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
DOCKERFILE = ROOT / "docker" / "termproof.Dockerfile"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "python-docker-image.yml"
DOCS = ROOT / "docs" / "ci" / "docker.md"
RUST_DOCKERFILE = REPO_ROOT / "rust" / "docker" / "termproof.Dockerfile"
RUST_TOOLCHAIN = REPO_ROOT / "rust" / "rust-toolchain.toml"
RUST_FROM = re.compile(r"^FROM rust:(\S+?)-slim(?:-\w+)?(@sha256:[0-9a-f]{64})? AS (\S+)$", re.MULTILINE)


class DockerImageTest(unittest.TestCase):
    def test_dockerfile_installs_termproof_and_video_tools(self) -> None:
        text = DOCKERFILE.read_text(encoding="utf-8")

        self.assertRegex(text, r"(?m)^FROM rust:\S+ AS agg-builder$")
        self.assertIn("cargo install --locked --git https://github.com/asciinema/agg", text)
        self.assertRegex(text, r"(?m)^FROM python:3\.14-slim$")
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

    def test_rust_base_images_match_toolchain_pin(self) -> None:
        # Both Dockerfiles that compile Rust must use the exact channel pinned
        # in rust/rust-toolchain.toml, and the same digest-pinned image, so the
        # two published images never drift apart again (#187).
        channel = tomllib.loads(RUST_TOOLCHAIN.read_text(encoding="utf-8"))["toolchain"]["channel"]
        images = set()
        for dockerfile in (DOCKERFILE, RUST_DOCKERFILE):
            matches = RUST_FROM.findall(dockerfile.read_text(encoding="utf-8"))
            self.assertEqual(1, len(matches), dockerfile)
            version, digest, _stage = matches[0]
            self.assertEqual(channel, version, dockerfile)
            self.assertTrue(digest, f"{dockerfile} rust base image is not digest-pinned")
            images.add((version, digest))
        self.assertEqual(1, len(images), "Rust base images differ between Dockerfiles")

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
