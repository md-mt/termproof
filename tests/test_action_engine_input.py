from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
ACTION = ROOT / "action.yml"


class ActionEngineInputTest(unittest.TestCase):
    """The Rust engine moved to md-mt/termproof-rust and no longer publishes releases.

    `engine: rust` used to download `termproof-linux-x86_64.tar.gz` from this
    repository's releases. Leaving that path in place would fail with a 404 from
    `curl` partway through the install step, so it is rejected up front instead.
    """

    def setUp(self) -> None:
        self.text = ACTION.read_text(encoding="utf-8")
        self.action = yaml.safe_load(self.text)

    def test_rust_version_input_is_gone(self) -> None:
        self.assertNotIn("rust-version", self.action["inputs"])

    def test_no_release_archive_download(self) -> None:
        self.assertNotIn("termproof-linux-x86_64.tar.gz", self.text)

    def test_rust_engine_is_rejected_with_an_explanation(self) -> None:
        install = next(s for s in self.action["runs"]["steps"] if s.get("name") == "Install TermProof")
        run = install["run"]

        self.assertIn("::error::", run)
        self.assertIn("https://github.com/md-mt/termproof-rust", run)
        self.assertIn("exit 1", run)

    def test_supported_engines_still_install(self) -> None:
        install = next(s for s in self.action["runs"]["steps"] if s.get("name") == "Install TermProof")
        run = install["run"]

        self.assertIn("auto|python", run)
        self.assertIn("uv tool install termproof", run)
        self.assertEqual("auto", self.action["inputs"]["engine"]["default"])


if __name__ == "__main__":
    unittest.main()
