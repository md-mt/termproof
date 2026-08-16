"""Run the test modules that need nothing but the standard library.

The full suite needs pexpect, pyte and Pillow. Some environments — CI images
that only lint, or a reviewer's shell — have none of them, but the pure-model
modules are still worth running there. This loads those modules directly,
bypassing ``termproof/__init__.py`` so the third-party imports never happen.

    python3 scripts/run_stdlib_tests.py

It is a convenience, not a substitute: ``pytest`` over ``tests/`` remains the
real suite.
"""

from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Modules whose only imports are stdlib, paired with the tests that cover them.
STDLIB_ONLY = {
    "termproof.attributed": "tests/test_attributed.py",
}


def _load(module_name: str, path: Path) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {module_name} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    # A namespace-only stand-in for the real package, so `termproof.attributed`
    # resolves without executing `termproof/__init__.py`.
    package = types.ModuleType("termproof")
    package.__path__ = [str(ROOT / "termproof")]
    sys.modules["termproof"] = package

    suite = unittest.TestSuite()
    for module_name, test_path in STDLIB_ONLY.items():
        _load(module_name, ROOT / (module_name.replace(".", "/") + ".py"))
        test_module = _load(Path(test_path).stem, ROOT / test_path)
        suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(test_module))

    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
