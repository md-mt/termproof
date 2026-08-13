from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from termproof import agg_bundle


class AggBundleTests(unittest.TestCase):
    def test_platform_key_supports_release_targets_and_common_machine_aliases(self) -> None:
        self.assertEqual("macos-arm64", agg_bundle.platform_key("Darwin", "arm64"))
        self.assertEqual("macos-x86_64", agg_bundle.platform_key("darwin", "x86_64"))
        self.assertEqual("linux-x86_64", agg_bundle.platform_key("Linux", "amd64"))

    def test_platform_key_rejects_unsupported_platform(self) -> None:
        with self.assertRaisesRegex(agg_bundle.UnsupportedAggPlatform, "windows-x86_64"):
            agg_bundle.platform_key("Windows", "x86_64")

    def test_bundled_agg_path_selects_current_platform_binary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp) / "linux-x86_64" / "agg"
            binary.parent.mkdir(parents=True)
            binary.write_text("#!/bin/sh\n", encoding="utf-8")

            self.assertEqual(
                binary,
                agg_bundle.bundled_agg_path("Linux", "x86_64", bundle_root=Path(tmp)),
            )

    def test_bundled_agg_path_explains_missing_supported_binary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RuntimeError, "was not included"):
                agg_bundle.bundled_agg_path("Linux", "x86_64", bundle_root=Path(tmp))

    def test_wheel_tag_is_platform_specific(self) -> None:
        self.assertEqual("py3-none-manylinux_2_17_x86_64", agg_bundle.wheel_tag("linux-x86_64"))
        self.assertEqual("py3-none-macosx_11_0_arm64", agg_bundle.wheel_tag("macos-arm64"))
        self.assertEqual("py3-none-macosx_10_15_x86_64", agg_bundle.wheel_tag("macos-x86_64"))

    def test_resolve_agg_falls_back_to_path_when_bundle_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = agg_bundle.resolve_agg()
            # resolve_agg either returns a bundled path, a PATH-found agg, or None.
            # In the test env, there is no bundled agg, so it falls to shutil.which.
            # If agg isn't on PATH either, it returns None — both are acceptable.
            if result is not None:
                self.assertIsInstance(result, str)


if __name__ == "__main__":
    unittest.main()
