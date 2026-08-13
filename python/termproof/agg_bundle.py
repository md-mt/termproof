"""Platform-specific selection for the agg binary embedded in TermProof wheels."""

from __future__ import annotations

import platform
from pathlib import Path


class UnsupportedAggPlatform(RuntimeError):
    """Raised when no bundled agg binary is available for this platform."""


_WHEEL_TAGS = {
    "linux-x86_64": "py3-none-manylinux_2_17_x86_64",
    "macos-arm64": "py3-none-macosx_11_0_arm64",
    "macos-x86_64": "py3-none-macosx_10_15_x86_64",
}


def platform_key(system: str | None = None, machine: str | None = None) -> str:
    """Return TermProof's supported binary target for a system and CPU."""
    normalized_system = (system or platform.system()).lower()
    normalized_machine = (machine or platform.machine()).lower()
    system_name = {"darwin": "macos", "linux": "linux"}.get(normalized_system, normalized_system)
    machine_name = {"amd64": "x86_64", "x64": "x86_64", "aarch64": "arm64"}.get(
        normalized_machine, normalized_machine
    )
    target = f"{system_name}-{machine_name}"
    if target not in _WHEEL_TAGS:
        supported = ", ".join(sorted(_WHEEL_TAGS))
        raise UnsupportedAggPlatform(
            f"TermProof bundles agg for {supported}; current platform is {target}. "
            "Install agg yourself and use a source checkout, or render without --video."
        )
    return target


def wheel_tag(target: str) -> str:
    """Return the PEP 425 wheel tag used by a binary-bearing target wheel."""
    try:
        return _WHEEL_TAGS[target]
    except KeyError as error:
        raise UnsupportedAggPlatform(f"No TermProof agg wheel tag exists for {target}") from error


def bundled_agg_path(
    system: str | None = None,
    machine: str | None = None,
    *,
    bundle_root: Path | None = None,
) -> Path:
    """Locate the agg executable embedded for the current supported platform."""
    target = platform_key(system, machine)
    root = bundle_root or Path(__file__).with_name("_vendor") / "agg"
    binary = root / target / "agg"
    if not binary.is_file():
        raise RuntimeError(
            f"The bundled agg binary for {target} was not included in this TermProof wheel. "
            "Reinstall a platform wheel for this system."
        )
    return binary


def resolve_agg() -> str | None:
    """Resolve an agg executable, preferring the bundled binary, falling back to PATH.

    Returns the path to the agg binary as a string, or None if no agg is
    available.  This allows source installs and dev environments to use a
    system-installed agg (e.g. via ``cargo install agg``) while platform wheels
    use the embedded binary.
    """
    try:
        return str(bundled_agg_path())
    except (RuntimeError, UnsupportedAggPlatform):
        import shutil

        return shutil.which("agg")
