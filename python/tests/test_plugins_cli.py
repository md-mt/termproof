from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from termproof.cli import main
from termproof.plugins_cli import load_community_plugins

REGISTRY = """# Community plugins

| Name | Description | Install | Author |
| --- | --- | --- | --- |
| termproof-textual | Textual helpers | `pip install termproof-textual` | [@you](https://github.com/you) |
"""


class PluginsCliTest(unittest.TestCase):
    def test_plugins_list_shows_configured_plugins(self) -> None:
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            code = main(["plugins", "list"])

        self.assertEqual(0, code)
        text = output.getvalue()
        self.assertIn("steps\twait_for_text\ttermproof.builtin_steps:WaitForText", text)
        self.assertIn("assertions\tjson_schema\ttermproof.builtin_assertions:JsonSchema", text)
        self.assertIn(
            "session_backend\tactive\ttermproof.builtin_session:PexpectBackend",
            text,
        )

    def test_load_community_plugins_reads_markdown_table(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = Path(tmp) / "plugins.md"
            registry.write_text(REGISTRY, encoding="utf-8")

            plugins = load_community_plugins(registry)

        self.assertEqual("termproof-textual", plugins[0].name)
        self.assertEqual("pip install termproof-textual", plugins[0].install)
        self.assertEqual("@you", plugins[0].author)

    def test_plugins_search_finds_registry_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = Path(tmp) / "plugins.md"
            registry.write_text(REGISTRY, encoding="utf-8")
            output = io.StringIO()

            with contextlib.redirect_stdout(output):
                code = main(["plugins", "search", "textual", "--registry", str(registry)])

        self.assertEqual(0, code)
        self.assertIn("termproof-textual", output.getvalue())

    def test_plugins_install_supports_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = Path(tmp) / "plugins.md"
            registry.write_text(REGISTRY, encoding="utf-8")
            output = io.StringIO()

            with contextlib.redirect_stdout(output):
                code = main(
                    [
                        "plugins",
                        "install",
                        "termproof-textual",
                        "--registry",
                        str(registry),
                        "--dry-run",
                    ]
                )

        self.assertEqual(0, code)
        self.assertIn("pip install termproof-textual", output.getvalue())

    def test_plugins_install_unknown_returns_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = Path(tmp) / "plugins.md"
            registry.write_text(REGISTRY, encoding="utf-8")
            output = io.StringIO()

            with contextlib.redirect_stdout(output):
                code = main(
                    [
                        "plugins",
                        "install",
                        "missing",
                        "--registry",
                        str(registry),
                    ]
                )

        self.assertEqual(1, code)
        self.assertIn("unknown plugin", output.getvalue())


if __name__ == "__main__":
    unittest.main()
