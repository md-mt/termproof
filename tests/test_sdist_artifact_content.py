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

# The RUST-002 regression gate needs both the Rust toolchain (to generate
# Cargo build/doc outputs) and uv (the project's build frontend). Environments
# without either tool skip the gate; CI and Rust-enabled dev machines enforce it.
_HAVE_TOOLS = shutil.which("cargo") is not None and shutil.which("uv") is not None


@unittest.skipUnless(_HAVE_TOOLS, "requires cargo and uv to build the Rust workspace and Python sdist")
class SdistRustIsolationTest(unittest.TestCase):
    """RUST-002 regression: the Python source distribution must never contain
    Rust workspace build artifacts (host-built executables, generated rustdoc)
    or any ``rust/`` tree until Rust is intentionally part of the Python
    release artifact.

    The historical failure mode: Hatch's sdist include patterns are matched
    with gitignore semantics, so bare names like ``termproof``, ``docs``,
    ``tests``, and ``README.md`` also matched nested ``rust/`` paths. Building
    the sdist *after* ``cargo build``/``cargo doc`` therefore shipped
    ``rust/target/debug/termproof``, ``rust/target/release/termproof``, and
    generated rustdoc in the release artifact. This test rebuilds Cargo outputs
    first and then asserts the sdist (and wheel) stay free of Rust content.
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

    def test_sdist_contains_no_rust_entries_after_cargo_build(self) -> None:
        rust_entries = [
            name
            for name in self._sdist_names()
            if any(part == "rust" for part in name.split("/")[1:])
        ]
        self.assertEqual(
            [],
            rust_entries,
            "sdist must not contain any rust/ entries after Cargo outputs exist: "
            f"{rust_entries}",
        )

    def test_wheel_contains_no_rust_entries_after_cargo_build(self) -> None:
        rust_entries = [
            name for name in self._wheel_names() if any(part == "rust" for part in name.split("/"))
        ]
        self.assertEqual(
            [],
            rust_entries,
            "wheel must not contain any rust/ entries after Cargo outputs exist: "
            f"{rust_entries}",
        )


if __name__ == "__main__":
    unittest.main()
