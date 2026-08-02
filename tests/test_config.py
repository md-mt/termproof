from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from termproof.config import (
    DockerBackendConfig,
    VerifierConfig,
    load_config,
)
from termproof.registry import Registry


class ConfigTest(unittest.TestCase):
    def test_builtin_config_has_all_fields(self) -> None:
        config = VerifierConfig.builtin()
        self.assertIn("wait_for_text", config.steps)
        self.assertIn("send_text", config.steps)
        self.assertIn("output_contains", config.assertions)
        self.assertIn("exit_code", config.assertions)
        self.assertIsInstance(config.docker, DockerBackendConfig)
        self.assertEqual(config.docker.image, "")
        self.assertEqual(config.docker.workdir, "/workspace")

    def test_load_config_returns_builtin_when_no_files_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = load_config(
                project_path=Path(tmp),
                user_path=Path(tmp) / "nonexistent.yaml",
            )
            self.assertIn("wait_for_text", config.steps)
            self.assertIn("output_contains", config.assertions)

    def test_builtin_config_defaults_idle_cap_seconds(self) -> None:
        """The post-script idle wait cap is a documented, configurable default."""
        config = VerifierConfig.builtin()
        self.assertEqual(config.defaults.idle_cap_seconds, 3.0)

    def test_load_config_parses_idle_cap_seconds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            user_yaml = tmp + "/user.yaml"
            Path(user_yaml).write_text(
                "defaults:\n  idle_cap_seconds: 7.5\n",
                encoding="utf-8",
            )
            config = load_config(
                project_path=Path(tmp),
                user_path=Path(user_yaml),
            )
            self.assertEqual(config.defaults.idle_cap_seconds, 7.5)
            # other config unchanged
            self.assertEqual(config.docker.image, "")

    def test_load_config_allows_null_idle_cap(self) -> None:
        """Null idle cap means wait for quiescence up to the recipe timeout."""
        with tempfile.TemporaryDirectory() as tmp:
            user_yaml = tmp + "/user.yaml"
            Path(user_yaml).write_text(
                "defaults:\n  idle_cap_seconds:\n",
                encoding="utf-8",
            )
            config = load_config(
                project_path=Path(tmp),
                user_path=Path(user_yaml),
            )
            self.assertIsNone(config.defaults.idle_cap_seconds)

    def test_load_config_rejects_negative_idle_cap(self) -> None:
        """A negative idle cap would silently eliminate idle waiting; reject it."""
        with tempfile.TemporaryDirectory() as tmp:
            user_yaml = tmp + "/user.yaml"
            Path(user_yaml).write_text(
                "defaults:\n  idle_cap_seconds: -1\n",
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                load_config(
                    project_path=Path(tmp),
                    user_path=Path(user_yaml),
                )

    def test_load_config_rejects_nan_idle_cap(self) -> None:
        """NaN is not a finite number of seconds; reject it."""
        with tempfile.TemporaryDirectory() as tmp:
            user_yaml = tmp + "/user.yaml"
            Path(user_yaml).write_text(
                "defaults:\n  idle_cap_seconds: .nan\n",
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                load_config(
                    project_path=Path(tmp),
                    user_path=Path(user_yaml),
                )

    def test_load_config_rejects_infinite_idle_cap(self) -> None:
        """Infinity is not a finite number of seconds; reject it."""
        with tempfile.TemporaryDirectory() as tmp:
            user_yaml = tmp + "/user.yaml"
            Path(user_yaml).write_text(
                "defaults:\n  idle_cap_seconds: .inf\n",
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                load_config(
                    project_path=Path(tmp),
                    user_path=Path(user_yaml),
                )

    def test_load_config_accepts_zero_idle_cap(self) -> None:
        """A zero idle cap is finite and nonnegative; it is a valid explicit choice."""
        with tempfile.TemporaryDirectory() as tmp:
            user_yaml = tmp + "/user.yaml"
            Path(user_yaml).write_text(
                "defaults:\n  idle_cap_seconds: 0\n",
                encoding="utf-8",
            )
            config = load_config(
                project_path=Path(tmp),
                user_path=Path(user_yaml),
            )
            self.assertEqual(config.defaults.idle_cap_seconds, 0.0)

    def test_load_config_preserves_idle_cap_when_key_absent(self) -> None:
        """A defaults block that omits idle_cap_seconds keeps the builtin cap."""
        with tempfile.TemporaryDirectory() as tmp:
            user_yaml = tmp + "/user.yaml"
            Path(user_yaml).write_text(
                "defaults:\n  video_fps: 30\n",
                encoding="utf-8",
            )
            config = load_config(
                project_path=Path(tmp),
                user_path=Path(user_yaml),
            )
            self.assertEqual(config.defaults.idle_cap_seconds, 3.0)

    def test_load_config_cascades_user_over_builtin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            user_yaml = tmp + "/user.yaml"
            Path(user_yaml).write_text(
                "docker:\n  image: user-image\n",
                encoding="utf-8",
            )
            config = load_config(
                project_path=Path(tmp),
                user_path=Path(user_yaml),
            )
            self.assertEqual(config.docker.image, "user-image")
            # other docker settings unchanged
            self.assertEqual(config.docker.workdir, "/workspace")

    def test_load_config_cascades_project_over_user_and_builtin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "project"
            project_dir.mkdir()
            config_dir = project_dir / ".termproof"
            config_dir.mkdir()
            (config_dir / "config.yaml").write_text(
                "docker:\n  image: project-image\n  workdir: /project\n",
                encoding="utf-8",
            )
            user_yaml = tmp + "/user.yaml"
            Path(user_yaml).write_text(
                "docker:\n  image: user-image\n  env:\n    FROM_USER: \"1\"\n",
                encoding="utf-8",
            )
            config = load_config(
                project_path=project_dir,
                user_path=Path(user_yaml),
            )
            self.assertEqual(config.docker.image, "project-image")  # project wins
            self.assertEqual(config.docker.workdir, "/project")  # project wins
            self.assertEqual(
                config.docker.env, {"FROM_USER": "1"}
            )  # user supplies, project doesn't

    def test_custom_step_registration_in_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "project"
            project_dir.mkdir()
            config_dir = project_dir / ".termproof"
            config_dir.mkdir()
            (config_dir / "config.yaml").write_text(
                "steps:\n  my_custom: termproof.builtin_steps:Sleep\n",
                encoding="utf-8",
            )
            config = load_config(project_path=project_dir)
            self.assertIn("my_custom", config.steps)
            self.assertEqual(
                config.steps["my_custom"],
                "termproof.builtin_steps:Sleep",
            )

    def test_docker_backend_config_loads_from_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "project"
            project_dir.mkdir()
            config_dir = project_dir / ".termproof"
            config_dir.mkdir()
            (config_dir / "config.yaml").write_text(
                """session_backend: docker
docker:
  image: python:3.12-slim
  workdir: /app
  volumes:
    - host: .
      container: /app
      read_only: true
  env:
    PYTHONUNBUFFERED: "1"
""",
                encoding="utf-8",
            )

            config = load_config(project_path=project_dir)

        self.assertEqual("docker", config.session_backend)
        self.assertEqual("python:3.12-slim", config.docker.image)
        self.assertEqual("/app", config.docker.workdir)
        self.assertEqual(
            [{"host": ".", "container": "/app", "read_only": True}],
            config.docker.volumes,
        )
        self.assertEqual({"PYTHONUNBUFFERED": "1"}, config.docker.env)


class RegistryTest(unittest.TestCase):
    def test_register_and_get(self) -> None:
        registry: Registry[str] = Registry()
        registry.register("hello", lambda: "world")
        self.assertEqual(registry.get("hello"), "world")

    def test_get_unknown_raises_key_error(self) -> None:
        registry: Registry[int] = Registry()
        with self.assertRaises(KeyError):
            registry.get("missing")

    def test_names_returns_sorted(self) -> None:
        registry: Registry[int] = Registry()
        registry.register("b", lambda: 2)
        registry.register("a", lambda: 1)
        self.assertEqual(registry.names(), ["a", "b"])

    def test_register_overwrites(self) -> None:
        registry: Registry[str] = Registry()
        registry.register("x", lambda: "first")
        registry.register("x", lambda: "second")
        self.assertEqual(registry.get("x"), "second")
