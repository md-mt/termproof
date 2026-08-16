from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from termproof.build_info import BuildInfo


class FromBinaryTest(unittest.TestCase):
    def test_it_describes_a_binary_at_a_known_path(self) -> None:
        info = BuildInfo.from_binary(sys.executable)
        self.assertEqual("installed", info.mode)
        self.assertEqual(sys.executable, info.binary_path)
        self.assertIn("Python", info.version)
        self.assertTrue(info.verify_provenance())

    def test_a_path_that_does_not_exist_is_not_verified(self) -> None:
        info = BuildInfo.from_binary("/nonexistent/binary")
        self.assertEqual("unknown", info.version)
        self.assertFalse(info.verify_provenance())


class FromSourceBuildTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.binary = Path(self._tmp.name) / "built"
        self.binary.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")

    def test_a_target_and_a_ref_and_a_real_binary_verify(self) -> None:
        info = BuildInfo.from_source_build(
            "//app:cli",
            binary_path=str(self.binary),
            source_ref="PR-42",
        )
        self.assertEqual("source", info.mode)
        self.assertEqual("//app:cli", info.build_target)
        self.assertEqual("PR-42", info.source_ref)
        self.assertTrue(info.verify_provenance())

    def test_a_commit_stands_in_for_a_ref(self) -> None:
        info = BuildInfo.from_source_build(
            "//app:cli",
            binary_path=str(self.binary),
            git_commit="abc123",
        )
        self.assertTrue(info.verify_provenance())

    def test_a_source_build_with_no_revision_is_not_verified(self) -> None:
        """It names what it built, but not what it built it from."""
        info = BuildInfo.from_source_build(
            "//app:cli",
            binary_path=str(self.binary),
            git_commit="",
        )
        self.assertFalse(info.verify_provenance())

    def test_a_source_build_with_no_binary_is_not_verified(self) -> None:
        info = BuildInfo.from_source_build("//app:cli", source_ref="PR-42", git_commit="abc")
        self.assertFalse(info.verify_provenance())

    def test_a_source_build_with_no_target_is_not_verified(self) -> None:
        info = BuildInfo.from_source_build(
            "",
            binary_path=str(self.binary),
            source_ref="PR-42",
        )
        self.assertFalse(info.verify_provenance())

    def test_an_explicit_commit_is_not_overwritten_by_the_working_tree(self) -> None:
        info = BuildInfo.from_source_build(
            "//app:cli",
            binary_path=str(self.binary),
            git_commit="deadbeef",
        )
        self.assertEqual("deadbeef", info.git_commit)


class SerialisationTest(unittest.TestCase):
    def test_the_new_fields_reach_the_dict(self) -> None:
        info = BuildInfo.from_source_build("//app:cli", source_ref="PR-42", git_commit="abc")
        payload = info.to_dict()
        self.assertEqual("//app:cli", payload["build_target"])
        self.assertEqual("PR-42", payload["source_ref"])
        self.assertIn("provenance_verified", payload)

    def test_an_unknown_mode_is_never_verified(self) -> None:
        info = BuildInfo(
            mode="handwave",
            command=[],
            binary_path=sys.executable,
            version="1",
            git_commit="abc",
            timestamp="now",
        )
        self.assertFalse(info.verify_provenance())


if __name__ == "__main__":
    unittest.main()
