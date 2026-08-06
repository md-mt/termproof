from __future__ import annotations

import shutil
import subprocess
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUST_DIR = ROOT / "rust"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

# The RUST-002 regression gate needs both the Rust toolchain (to generate
# Cargo build/test/doc outputs) and uv (the project's build frontend). Environments
# without either tool skip the gate; CI and Rust-enabled dev machines enforce it.
_HAVE_TOOLS = shutil.which("cargo") is not None and shutil.which("uv") is not None

# Paths added by the RUST-002 regression suite itself and the RUST-023
# version/drift + RUST-025 evidence-hosting docs. Everything else in the
# sdist must be byte-for-byte identical to the pre-Rust base revision.
_NEW_TEST_PATHS = {
    "tests/test_sdist_artifact_content.py",
    "tests/fixtures/base_sdist_paths.txt",
    "tests/fixtures/base_wheel_paths.txt",
    "docs/rust-gates.md",
    "docs/case-studies/CONSENT.md",
    "docs/case-studies/README.md",
    "docs/case-studies/TEMPLATE.md",
    "docs/case-studies/_meta.json",
}


def _load_fixture(name: str) -> set[str]:
    return {
        line.strip()
        for line in (FIXTURES_DIR / name).read_text(encoding="utf-8").splitlines()
        if line.strip()
    }


@unittest.skipUnless(_HAVE_TOOLS, "requires cargo and uv to build the Rust workspace and Python sdist")
class SdistRustIsolationTest(unittest.TestCase):
    """RUST-002 regression: the Python source distribution must never contain
    Rust workspace build artifacts (host-built executables, generated rustdoc)
    or any ``rust/`` tree until Rust is intentionally part of the Python
    release artifact.

    The historical failure modes, both now covered:

    1. Hatch's sdist include patterns are matched with gitignore semantics, so
       bare names like ``termproof``, ``docs``, ``tests``, and ``README.md``
       also matched nested ``rust/`` paths. Building the sdist *after* ``cargo
       build``/``cargo doc`` shipped ``rust/target/debug/termproof``,
       ``rust/target/release/termproof``, and generated rustdoc in the release
       artifact.

    2. Anchoring every include to the repository root (leading ``/``) to fix
       #1 silently dropped 13 pre-existing non-Rust payload paths
       (``plugin-template/**`` and ``site/README.md``). The narrow fix keeps the
       original unanchored include list and adds only the explicit ``/rust/``
       exclusion, so the non-Rust payload stays unchanged.

    This test rebuilds Cargo outputs first and then asserts both invariants:
    zero Rust content in sdist/wheel, and the sdist's non-Rust path set is
    exactly the base revision's path set plus the new regression test files.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls._out_dir = Path(cls._tmp.name)
        cls._generate_cargo_outputs()
        cls._build_python_artifacts()

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    @classmethod
    def _generate_cargo_outputs(cls) -> None:
        if not RUST_DIR.is_dir():
            raise unittest.SkipTest("rust workspace not present")
        subprocess.run(
            ["cargo", "build", "--workspace"],
            cwd=RUST_DIR,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["cargo", "test", "--workspace"],
            cwd=RUST_DIR,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["cargo", "doc", "--workspace", "--no-deps"],
            cwd=RUST_DIR,
            check=True,
            capture_output=True,
            text=True,
        )
        debug_binary = RUST_DIR / "target" / "debug" / "termproof"
        if not debug_binary.is_file():
            raise unittest.SkipTest("cargo build did not produce a debug binary")

    @classmethod
    def _build_python_artifacts(cls) -> None:
        subprocess.run(
            ["uv", "build", "--out-dir", str(cls._out_dir)],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

    @classmethod
    def _sdist_names(cls) -> list[str]:
        sdist = next(cls._out_dir.glob("*.tar.gz"))
        with tarfile.open(sdist, "r:gz") as archive:
            return archive.getnames()

    @classmethod
    def _wheel_names(cls) -> list[str]:
        wheel = next(cls._out_dir.glob("*.whl"))
        with zipfile.ZipFile(wheel) as archive:
            return archive.namelist()

    @classmethod
    def _sdist_relative_names(cls) -> set[str]:
        """Sdist member names with the leading ``termproof-<version>/`` root stripped."""
        root_prefix = next(cls._out_dir.glob("*.tar.gz")).name.removesuffix(".tar.gz") + "/"
        return {name[len(root_prefix):] for name in cls._sdist_names() if name.startswith(root_prefix)}

    @classmethod
    def _rust_entries(cls, names: list[str]) -> list[str]:
        return [name for name in names if any(part == "rust" for part in name.split("/"))]

    def test_sdist_contains_no_rust_entries_after_cargo_build_test_doc(self) -> None:
        rust_entries = self._rust_entries(self._sdist_names())
        self.assertEqual(
            [],
            rust_entries,
            "sdist must not contain any rust/ entries after Cargo build/test/doc outputs exist: "
            f"{rust_entries}",
        )

    def test_wheel_contains_no_rust_entries_after_cargo_build_test_doc(self) -> None:
        rust_entries = self._rust_entries(self._wheel_names())
        self.assertEqual(
            [],
            rust_entries,
            "wheel must not contain any rust/ entries after Cargo build/test/doc outputs exist: "
            f"{rust_entries}",
        )

    def test_sdist_preserves_base_non_rust_payload_paths(self) -> None:
        base_paths = _load_fixture("base_sdist_paths.txt")
        head_paths = self._sdist_relative_names()
        missing = sorted(base_paths - head_paths)
        self.assertEqual(
            [],
            missing,
            "sdist dropped pre-existing non-Rust payload paths present in the base "
            f"revision's sdist: {missing}",
        )

    def test_sdist_adds_only_regression_test_paths(self) -> None:
        base_paths = _load_fixture("base_sdist_paths.txt")
        head_paths = self._sdist_relative_names()
        unexpected = sorted((head_paths - base_paths) - _NEW_TEST_PATHS)
        self.assertEqual(
            [],
            unexpected,
            "sdist gained non-Rust paths beyond the RUST-002 regression tests: "
            f"{unexpected}",
        )

    def test_wheel_path_set_matches_base(self) -> None:
        base_wheel = _load_fixture("base_wheel_paths.txt")
        head_wheel = set(self._wheel_names())
        self.assertEqual(
            base_wheel,
            head_wheel,
            "wheel path set must be byte-for-byte identical to the base revision",
        )


if __name__ == "__main__":
    unittest.main()
