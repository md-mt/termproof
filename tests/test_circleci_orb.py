from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
ORB = ROOT / ".circleci" / "orb.yml"
DOCS = ROOT / "docs" / "ci" / "circleci.md"


class CircleCiOrbTest(unittest.TestCase):
    def test_orb_defines_verify_job_and_command(self) -> None:
        orb = yaml.safe_load(ORB.read_text(encoding="utf-8"))

        self.assertEqual(2.1, orb["version"])
        self.assertIn("verify", orb["commands"])
        self.assertIn("verify", orb["jobs"])
        self.assertEqual("cimg/python:3.12", orb["executors"]["python"]["docker"][0]["image"])

    def test_orb_runs_termproof_and_stores_evidence(self) -> None:
        text = ORB.read_text(encoding="utf-8")

        self.assertIn('uvx --from "<< parameters.termproof-source >>"', text)
        self.assertIn('termproof run "<< parameters.recipe-path >>"', text)
        self.assertIn("--xml-path", text)
        self.assertIn(".termproof-exit-code", text)
        self.assertIn("store_artifacts", text)
        self.assertIn("store_test_results", text)

    def test_docs_show_registry_usage(self) -> None:
        text = DOCS.read_text(encoding="utf-8")

        self.assertIn("md-mt/termproof@1.0.0", text)
        self.assertIn("circleci orb validate .circleci/orb.yml", text)
        self.assertIn("termproof-source", text)


if __name__ == "__main__":
    unittest.main()
