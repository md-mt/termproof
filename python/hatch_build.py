from __future__ import annotations

import os
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

_WHEEL_TAGS = {
    "linux-x86_64": "py3-none-manylinux_2_17_x86_64",
    "macos-arm64": "py3-none-macosx_11_0_arm64",
    "macos-x86_64": "py3-none-macosx_10_15_x86_64",
}


class CustomBuildHook(BuildHookInterface):
    """Embed exactly one native agg binary and emit a matching platform wheel."""

    def initialize(self, version: str, build_data: dict[str, object]) -> None:
        target = os.environ.get("TERMPROOF_AGG_TARGET")
        if not target:
            return
        binary = Path(self.root) / ".termproof-build" / "agg" / target / "agg"
        provenance = binary.parents[1] / "PROVENANCE.md"
        if not binary.is_file() or not provenance.is_file():
            raise RuntimeError(f"Build agg first: python scripts/build_agg.py --target {target}")
        try:
            build_data["tag"] = _WHEEL_TAGS[target]
        except KeyError as error:
            raise RuntimeError(f"Unsupported TERMPROOF_AGG_TARGET: {target}") from error
        build_data["force_include"] = {
            str(binary): f"termproof/_vendor/agg/{target}/agg",
            str(provenance): "termproof/_vendor/agg/PROVENANCE.md",
        }
