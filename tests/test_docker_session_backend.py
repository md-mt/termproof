from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from termproof.builtin_session import DockerSessionBackend
from termproof.config import DockerBackendConfig, VerifierConfig
from termproof.runner import VerificationRunner


class DockerSessionBackendTest(unittest.TestCase):
    def test_create_session_wraps_command_in_docker_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            backend = DockerSessionBackend(
                DockerBackendConfig(
                    image="python:3.12-slim",
                    workdir="/app",
                    volumes=[
                        {
                            "host": ".",
                            "container": "/app",
                            "read_only": True,
                        }
                    ],
                    env={"BASE_ENV": "1"},
                )
            )
            session = backend.create_session(
                ["python", "-V"],
                Path(tmp) / "session.cast",
                cwd=tmp,
                env={"RUN_ENV": "2"},
                cols=80,
                rows=24,
            )
            expected_volume = f"{Path(tmp).resolve()}:/app:ro"

        self.assertEqual("docker", session.argv[0])
        self.assertIn("--rm", session.argv)
        self.assertIn("--interactive", session.argv)
        self.assertIn("--tty", session.argv)
        self.assertIn("--env", session.argv)
        self.assertIn("BASE_ENV=1", session.argv)
        self.assertIn("RUN_ENV=2", session.argv)
        self.assertIn("--workdir", session.argv)
        self.assertIn("/app", session.argv)
        self.assertIn(expected_volume, session.argv)
        self.assertEqual(["python:3.12-slim", "python", "-V"], session.argv[-3:])
        self.assertIsNone(session.cwd)

    def test_string_volume_specs_pass_through(self) -> None:
        backend = DockerSessionBackend(
            DockerBackendConfig(
                image="alpine:3.20",
                volumes=["/host/cache:/cache:ro"],
            )
        )
        session = backend.create_session(
            ["echo", "ok"],
            Path(tempfile.mkdtemp()) / "session.cast",
            cwd=None,
            env={},
            cols=80,
            rows=24,
        )

        self.assertIn("/host/cache:/cache:ro", session.argv)

    def test_runner_resolves_docker_session_backend_alias(self) -> None:
        config = replace(
            VerifierConfig.builtin(),
            session_backend="docker",
            docker=DockerBackendConfig(image="alpine:3.20"),
        )

        runner = VerificationRunner(config=config)

        self.assertIsInstance(runner.session_backend, DockerSessionBackend)

    def test_docker_backend_requires_image(self) -> None:
        backend = DockerSessionBackend(DockerBackendConfig())

        with self.assertRaisesRegex(RuntimeError, "docker.image"):
            backend.create_session(
                ["echo", "ok"],
                Path(tempfile.mkdtemp()) / "session.cast",
                cwd=None,
                env={},
                cols=80,
                rows=24,
            )


if __name__ == "__main__":
    unittest.main()
