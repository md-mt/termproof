from __future__ import annotations

import re
import shutil
import subprocess
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

# uv is the project's build frontend. Environments without it skip the gate.
_HAVE_TOOLS = shutil.which("uv") is not None

# Suffixes that only ever belong to compiled build output, never to source we
# intend to ship. A new sdist path matching one of these is a packaging bug
# regardless of which toolchain produced it.
_BUILD_OUTPUT_SUFFIXES = frozenset(
    {".so", ".dylib", ".dll", ".a", ".o", ".obj", ".rlib", ".rmeta", ".pyd", ".exe", ".pyc"}
)

# Path components that denote a build directory rather than source.
_BUILD_OUTPUT_DIRS = frozenset({"target", "build", "dist", "__pycache__", ".pytest_cache", ".mypy_cache"})

# Base-revision paths that have since been deliberately removed from the
# repository. `base_sdist_paths.txt` is a historical record of what the base
# revision shipped and is not rewritten, so an intentional deletion is
# registered here instead -- which keeps it a reviewed decision rather than a
# silent edit to the baseline.
_INTENTIONALLY_REMOVED = frozenset(
    {
        # The Rust reimplementation spec belongs to the Rust workspace and
        # lives at rust/docs/rust-reimplementation-spec.md; it is not part of
        # the Python package.
        "docs/rust-reimplementation-spec.md",
    }
)


_DIST_INFO = re.compile(r"^termproof-[^/]+\.dist-info/")


def _normalize_dist_info(paths: set[str]) -> set[str]:
    """Collapse the version out of ``termproof-<version>.dist-info/`` paths.

    The metadata directory is named after the version, so comparing wheel path
    sets across a version bump otherwise reports every metadata file as both
    removed and added.
    """
    return {_DIST_INFO.sub("dist-info/", path) for path in paths}


def _load_fixture(name: str) -> set[str]:
    return {
        line.strip()
        for line in (FIXTURES_DIR / name).read_text(encoding="utf-8").splitlines()
        if line.strip()
    }


@unittest.skipUnless(_HAVE_TOOLS, "requires uv to build the Python sdist and wheel")
class SdistArtifactContentTest(unittest.TestCase):
    """The Python release artifact must contain source and only source.

    This gate used to assert that the sdist's path set was *exactly* the base
    revision's set plus a hand-maintained allowlist of every file added since.
    That enumeration guarded one real invariant — no Rust build output leaking
    into the release artifact — and otherwise only ever caught "a human forgot
    to register a new file", at the cost of being a merge-conflict point in four
    consecutive changes. The Rust workspace lives beside the Python package
    rather than inside it, so `uv build` never sees it and that invariant is
    satisfied by the layout — invariant 1 below is the cheap insurance that it
    stays that way.

    What replaces it are the invariants the enumeration was standing in for:

    1. no ``rust/`` content (cheap insurance, now trivially satisfied);
    2. ``base ⊆ head`` — the sdist never *drops* payload it used to ship. This
       is the failure that actually happened: anchoring the include patterns to
       the repository root silently dropped 13 ``plugin-template/**`` and
       ``site/README.md`` paths. A file deleted on purpose is registered in
       ``_INTENTIONALLY_REMOVED`` rather than edited out of the baseline;
    3. ``head − base`` contains no compiled build output — no build directory,
       no object/library suffix, no executable bit.

    Adding a source file under ``termproof/``, ``tests/``, ``examples/`` or
    ``docs/`` now ships it without needing to be registered anywhere, which is
    the intended workflow. Adding a *binary* still fails the gate.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls._out_dir = Path(cls._tmp.name)
        cls._build_python_artifacts()

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

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
    def _sdist_path(cls) -> Path:
        return next(cls._out_dir.glob("*.tar.gz"))

    @classmethod
    def _sdist_names(cls) -> list[str]:
        with tarfile.open(cls._sdist_path(), "r:gz") as archive:
            return archive.getnames()

    @classmethod
    def _wheel_names(cls) -> list[str]:
        wheel = next(cls._out_dir.glob("*.whl"))
        with zipfile.ZipFile(wheel) as archive:
            return archive.namelist()

    @classmethod
    def _root_prefix(cls) -> str:
        return cls._sdist_path().name.removesuffix(".tar.gz") + "/"

    @classmethod
    def _sdist_relative_names(cls) -> set[str]:
        """Sdist member names with the leading ``termproof-<version>/`` root stripped."""
        prefix = cls._root_prefix()
        return {name[len(prefix):] for name in cls._sdist_names() if name.startswith(prefix)}

    @classmethod
    def _executable_relative_names(cls) -> set[str]:
        """Relative names of sdist members that carry an executable bit."""
        prefix = cls._root_prefix()
        with tarfile.open(cls._sdist_path(), "r:gz") as archive:
            return {
                member.name[len(prefix):]
                for member in archive.getmembers()
                if member.isfile() and member.mode & 0o111 and member.name.startswith(prefix)
            }

    @staticmethod
    def _build_output_reason(path: str) -> str | None:
        """Why ``path`` looks like build output, or ``None`` if it looks like source."""
        parts = path.split("/")
        offending = _BUILD_OUTPUT_DIRS.intersection(parts)
        if offending:
            return f"build directory component {sorted(offending)[0]!r}"
        suffix = Path(path).suffix
        if suffix in _BUILD_OUTPUT_SUFFIXES:
            return f"compiled-artifact suffix {suffix!r}"
        return None

    def test_sdist_contains_no_rust_entries(self) -> None:
        rust_entries = [name for name in self._sdist_names() if any(part == "rust" for part in name.split("/"))]
        self.assertEqual([], rust_entries, f"sdist must not contain any rust/ entries: {rust_entries}")

    def test_wheel_contains_no_rust_entries(self) -> None:
        rust_entries = [name for name in self._wheel_names() if any(part == "rust" for part in name.split("/"))]
        self.assertEqual([], rust_entries, f"wheel must not contain any rust/ entries: {rust_entries}")

    def test_sdist_preserves_base_non_rust_payload_paths(self) -> None:
        base_paths = _load_fixture("base_sdist_paths.txt") - _INTENTIONALLY_REMOVED
        head_paths = self._sdist_relative_names()
        missing = sorted(base_paths - head_paths)
        self.assertEqual(
            [],
            missing,
            "sdist dropped pre-existing payload paths present in the base revision's sdist: " f"{missing}",
        )

    def test_intentional_removals_are_accurate(self) -> None:
        """Stop `_INTENTIONALLY_REMOVED` from rotting into a blanket exemption."""
        base_paths = _load_fixture("base_sdist_paths.txt")

        not_in_base = sorted(_INTENTIONALLY_REMOVED - base_paths)
        self.assertEqual([], not_in_base, f"registered removals that the base revision never shipped: {not_in_base}")

        still_shipping = sorted(_INTENTIONALLY_REMOVED & self._sdist_relative_names())
        self.assertEqual(
            [],
            still_shipping,
            f"registered removals that the sdist still ships -- drop them from the set: {still_shipping}",
        )

    def test_sdist_adds_no_build_output(self) -> None:
        base_paths = _load_fixture("base_sdist_paths.txt")
        added = self._sdist_relative_names() - base_paths
        offenders = sorted(
            f"{path} ({reason})" for path in added if (reason := self._build_output_reason(path)) is not None
        )
        self.assertEqual(
            [],
            offenders,
            "sdist gained paths that look like build output rather than source: " f"{offenders}",
        )

    def test_sdist_adds_no_executable_files(self) -> None:
        base_paths = _load_fixture("base_sdist_paths.txt")
        added_executables = sorted(self._executable_relative_names() - base_paths)
        self.assertEqual(
            [],
            added_executables,
            "sdist gained executable files, which are build output rather than source: " f"{added_executables}",
        )

    def test_wheel_preserves_base_payload_paths(self) -> None:
        base = _normalize_dist_info(_load_fixture("base_wheel_paths.txt"))
        head = _normalize_dist_info(set(self._wheel_names()))
        missing = sorted(base - head)
        self.assertEqual([], missing, f"wheel dropped paths the base revision shipped: {missing}")

    def test_wheel_adds_only_package_source(self) -> None:
        """The wheel is the package and nothing else.

        This replaces a strict set equality against the base revision. That
        assertion could not survive a version bump -- the `dist-info` directory
        is named after the version, so every path in it changed -- and it failed
        for every new module besides. Both are routine, neither is a packaging
        defect, and the sdist gates above already gave up enumeration for the
        same reason.

        What is worth catching is the wheel gaining something that is not the
        package: a stray `tests/`, `examples/` or `docs/` tree, or build output.
        """
        base = _normalize_dist_info(_load_fixture("base_wheel_paths.txt"))
        added = _normalize_dist_info(set(self._wheel_names())) - base
        offenders = sorted(
            path
            for path in added
            if not path.startswith("termproof/") or self._build_output_reason(path) is not None
        )
        self.assertEqual(
            [],
            offenders,
            f"wheel gained paths that are not package source: {offenders}",
        )


if __name__ == "__main__":
    unittest.main()
