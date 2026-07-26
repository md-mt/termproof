from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from termproof.config import (
    BUILTIN_DEFAULTS,
    GlobalDefaults,
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
        self.assertIsInstance(config.defaults, GlobalDefaults)
        self.assertEqual(config.defaults.timeout_seconds, 30.0)
        self.assertEqual(config.defaults.cols, 100)

    def test_load_config_returns_builtin_when_no_files_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = load_config(
                project_path=Path(tmp),
                user_path=Path(tmp) / "nonexistent.yaml",
            )
            self.assertIn("wait_for_text", config.steps)
            self.assertIn("output_contains", config.assertions)

    def test_load_config_cascades_user_over_builtin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            user_yaml = tmp + "/user.yaml"
            Path(user_yaml).write_text(
                "defaults:\n  timeout_seconds: 60\n",
                encoding="utf-8",
            )
            config = load_config(
                project_path=Path(tmp),
                user_path=Path(user_yaml),
            )
            self.assertEqual(config.defaults.timeout_seconds, 60.0)
            # other defaults unchanged
            self.assertEqual(config.defaults.cols, 100)

    def test_load_config_cascades_project_over_user_and_builtin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "project"
            project_dir.mkdir()
            config_dir = project_dir / ".termproof"
            config_dir.mkdir()
            (config_dir / "config.yaml").write_text(
                "defaults:\n  timeout_seconds: 90\n  cols: 120\n",
                encoding="utf-8",
            )
            user_yaml = tmp + "/user.yaml"
            Path(user_yaml).write_text(
                "defaults:\n  timeout_seconds: 60\n  rows: 40\n",
                encoding="utf-8",
            )
            config = load_config(
                project_path=project_dir,
                user_path=Path(user_yaml),
            )
            self.assertEqual(config.defaults.timeout_seconds, 90.0)  # project wins
            self.assertEqual(config.defaults.cols, 120)  # project wins
            self.assertEqual(config.defaults.rows, 40)  # user supplies, project doesn't

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
