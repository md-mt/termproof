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


class EvidenceConfigTest(unittest.TestCase):
    def test_builtin_evidence_defaults_reproduce_the_previous_literals(self) -> None:
        evidence = VerifierConfig.builtin().evidence
        self.assertEqual(
            (9, 20, 18, 14, "#e6edf3", "#101418"),
            (
                evidence.svg.char_width,
                evidence.svg.line_height,
                evidence.svg.padding,
                evidence.svg.font_size,
                evidence.svg.fg,
                evidence.svg.bg,
            ),
        )
        self.assertEqual(
            "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace",
            evidence.svg.font_family,
        )
        self.assertEqual((1, 18, None), (evidence.png.scale, evidence.png.padding, evidence.png.font_path))
        self.assertEqual((60, None, "yuv420p"), (evidence.video.fps, evidence.video.fps_cap, evidence.video.pix_fmt))
        # None means "omit the flag", which is what the pipeline did before.
        self.assertEqual(
            [None] * 8,
            [
                evidence.video.crf,
                evidence.video.preset,
                evidence.video.tune,
                evidence.video.idle_time_limit,
                evidence.video.last_frame_duration,
                evidence.video.theme,
                evidence.video.font_size,
                evidence.video.font_family,
            ],
        )

    def test_evidence_values_load_from_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            user_yaml = Path(tmp) / "user.yaml"
            user_yaml.write_text(
                "evidence:\n"
                "  svg:\n    char_width: 8\n    fg: '#ffffff'\n"
                "  png:\n    scale: 2\n    font_path: /fonts/mono.ttf\n"
                "  video:\n    pix_fmt: yuv444p\n    crf: 20\n",
                encoding="utf-8",
            )
            config = load_config(project_path=Path(tmp), user_path=user_yaml)
        self.assertEqual(8, config.evidence.svg.char_width)
        self.assertEqual("#ffffff", config.evidence.svg.fg)
        self.assertEqual(20, config.evidence.svg.line_height)  # untouched key keeps its default
        self.assertEqual(2, config.evidence.png.scale)
        self.assertEqual("/fonts/mono.ttf", config.evidence.png.font_path)
        self.assertEqual("yuv444p", config.evidence.video.pix_fmt)
        self.assertEqual(20, config.evidence.video.crf)

    def test_project_evidence_config_wins_over_user(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "project"
            (project_dir / ".termproof").mkdir(parents=True)
            (project_dir / ".termproof" / "config.yaml").write_text(
                "evidence:\n  video:\n    crf: 18\n",
                encoding="utf-8",
            )
            user_yaml = Path(tmp) / "user.yaml"
            user_yaml.write_text(
                "evidence:\n  video:\n    crf: 30\n    preset: slow\n",
                encoding="utf-8",
            )
            config = load_config(project_path=project_dir, user_path=user_yaml)
        self.assertEqual(18, config.evidence.video.crf)  # project wins
        self.assertEqual("slow", config.evidence.video.preset)  # user supplies, project doesn't
        self.assertEqual("yuv420p", config.evidence.video.pix_fmt)  # builtin survives

    def test_unknown_evidence_option_is_rejected(self) -> None:
        """A misspelled rendering knob that silently does nothing is worse than an error."""
        with tempfile.TemporaryDirectory() as tmp:
            user_yaml = Path(tmp) / "user.yaml"
            user_yaml.write_text(
                "evidence:\n  svg:\n    charwidth: 8\n", encoding="utf-8"
            )
            with self.assertRaises(ValueError):
                load_config(project_path=Path(tmp), user_path=user_yaml)

    def test_quoted_number_is_rejected_naming_the_offending_key(self) -> None:
        """A YAML scalar of the wrong type must fail here, not inside a renderer."""
        with tempfile.TemporaryDirectory() as tmp:
            user_yaml = Path(tmp) / "user.yaml"
            user_yaml.write_text(
                "evidence:\n  svg:\n    padding: '18'\n", encoding="utf-8"
            )
            with self.assertRaises(ValueError) as caught:
                load_config(project_path=Path(tmp), user_path=user_yaml)
        self.assertIn("evidence.svg.padding", str(caught.exception))
        self.assertIn("int", str(caught.exception))

    def test_wrong_type_is_rejected_for_each_evidence_section(self) -> None:
        cases = {
            "  png:\n    font_path: 3\n": "evidence.png.font_path",
            "  video:\n    crf: fast\n": "evidence.video.crf",
            "  svg:\n    font_family: 12\n": "evidence.svg.font_family",
        }
        for body, key in cases.items():
            with self.subTest(key=key), tempfile.TemporaryDirectory() as tmp:
                user_yaml = Path(tmp) / "user.yaml"
                user_yaml.write_text(f"evidence:\n{body}", encoding="utf-8")
                with self.assertRaises(ValueError) as caught:
                    load_config(project_path=Path(tmp), user_path=user_yaml)
                self.assertIn(key, str(caught.exception))

    def test_optional_and_widening_values_still_load(self) -> None:
        """Validation must not reject values that loaded fine before it existed."""
        with tempfile.TemporaryDirectory() as tmp:
            user_yaml = Path(tmp) / "user.yaml"
            user_yaml.write_text(
                "evidence:\n"
                "  png:\n    font_path: null\n"
                # A float field written as a YAML integer is still a valid float.
                "  video:\n    idle_time_limit: 2\n    theme: asciinema\n",
                encoding="utf-8",
            )
            config = load_config(project_path=Path(tmp), user_path=user_yaml)
        self.assertIsNone(config.evidence.png.font_path)
        self.assertEqual(2, config.evidence.video.idle_time_limit)
        self.assertEqual("asciinema", config.evidence.video.theme)

    def test_unknown_evidence_section_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            user_yaml = Path(tmp) / "user.yaml"
            user_yaml.write_text("evidence:\n  gif:\n    scale: 2\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_config(project_path=Path(tmp), user_path=user_yaml)


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
