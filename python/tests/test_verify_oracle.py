"""The oracle-freshness comparison in ``conformance/verify_oracle.py``.

Only the pure comparison is tested here: running the eight probes end to end
belongs to ``conformance/README.md``'s freshness check, not to the unit
suite, which must stay fast and must pass on interpreters whose recorded
expectations legitimately differ (see the checker's environment policy).
What this pins is the policy itself — payload differences fail, environment
differences are reported rather than dropped, and the four header-less
documents compare whole.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from types import ModuleType

CHECKER = Path(__file__).resolve().parents[2] / "conformance" / "verify_oracle.py"


def _load_checker() -> ModuleType:
    spec = importlib.util.spec_from_file_location("verify_oracle", CHECKER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


verify = _load_checker()


def _document(detail: str, python: str) -> dict:
    return {
        "_comment": "generated",
        "environment": {"python": python, "platform": "Darwin"},
        "cases": [{"id": "only/case", "expected": {"passed": False, "detail": detail}}],
    }


class CompareDocumentsTest(unittest.TestCase):
    def test_identical_documents_pass(self) -> None:
        result = verify.compare_documents(_document("same", "3.13.2"), _document("same", "3.13.2"))
        self.assertTrue(result.ok)
        self.assertEqual(result.payload_diffs, [])
        self.assertEqual(result.environment_diffs, [])

    def test_environment_difference_is_reported_not_dropped(self) -> None:
        result = verify.compare_documents(_document("same", "3.12.13"), _document("same", "3.13.2"))
        self.assertTrue(result.ok)
        self.assertEqual(result.payload_diffs, [])
        self.assertEqual(len(result.environment_diffs), 1)
        self.assertIn("environment.python", result.environment_diffs[0])

    def test_strict_environment_fails_on_environment_difference(self) -> None:
        result = verify.compare_documents(
            _document("same", "3.12.13"), _document("same", "3.13.2"), strict_environment=True
        )
        self.assertFalse(result.ok)

    def test_payload_difference_fails_and_names_the_case(self) -> None:
        result = verify.compare_documents(_document("old", "3.13.2"), _document("new", "3.13.2"))
        self.assertFalse(result.ok)
        self.assertEqual(len(result.payload_diffs), 1)
        self.assertIn("only/case", result.payload_diffs[0])

    def test_comment_difference_alone_passes(self) -> None:
        stored, fresh = _document("same", "3.13.2"), _document("same", "3.13.2")
        fresh["_comment"] = "reworded generator prose"
        self.assertTrue(verify.compare_documents(stored, fresh).ok)

    def test_list_document_compares_whole(self) -> None:
        stored = [{"name": "a", "markdown": "x"}]
        self.assertTrue(verify.compare_documents(stored, [{"name": "a", "markdown": "x"}]).ok)
        changed = verify.compare_documents(stored, [{"name": "a", "markdown": "y"}])
        self.assertFalse(changed.ok)
        self.assertEqual(changed.environment_diffs, [])

    def test_headerless_object_document_compares_whole(self) -> None:
        stored = {"manifest": {"steps": []}, "files": {"a.txt": "x"}}
        self.assertTrue(verify.compare_documents(stored, dict(stored)).ok)
        changed = verify.compare_documents(stored, {"manifest": {"steps": []}, "files": {"a.txt": "y"}})
        self.assertFalse(changed.ok)

    def test_explicit_null_differs_from_absent_key(self) -> None:
        self.assertFalse(verify.compare_documents({"a": None, "b": 1}, {"b": 1}).ok)
        self.assertFalse(verify.compare_documents({"b": 1}, {"a": None, "b": 1}).ok)
        stored, fresh = _document("same", "3.13.2"), _document("same", "3.13.2")
        stored["extra"] = None
        self.assertFalse(verify.compare_documents(stored, fresh).ok)

    def test_explicit_null_inside_a_case_differs_from_absent(self) -> None:
        stored, fresh = _document("same", "3.13.2"), _document("same", "3.13.2")
        stored["cases"][0]["expected"]["note"] = None
        result = verify.compare_documents(stored, fresh)
        self.assertFalse(result.ok)
        self.assertTrue(result.payload_diffs)

    def test_json_types_are_not_conflated(self) -> None:
        self.assertFalse(verify.compare_documents({"passed": True}, {"passed": 1}).ok)
        self.assertFalse(verify.compare_documents({"score": 1}, {"score": 1.0}).ok)
        stored, fresh = _document("same", "3.13.2"), _document("same", "3.13.2")
        fresh["cases"][0]["expected"]["passed"] = 0
        self.assertFalse(verify.compare_documents(stored, fresh).ok)

    def test_probes_cover_every_corpus_expectation(self) -> None:
        probed = {expected_name for _, expected_name in verify.PROBES}
        on_disk = {path.name for path in verify.CORPUS.glob("*.expected.json")}
        self.assertEqual(probed, on_disk)


if __name__ == "__main__":
    unittest.main()
