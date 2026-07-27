#!/usr/bin/env python3
"""Stage a pinned agg release binary for inclusion in a platform wheel."""

from __future__ import annotations

import argparse
import hashlib
import platform
import shutil
import urllib.request
from pathlib import Path


VERSION = "v1.9.0"
BASE_URL = f"https://github.com/asciinema/agg/releases/download/{VERSION}"
ASSETS = {
    "linux-x86_64": (
        "agg-x86_64-unknown-linux-gnu",
        "f111e315cd71056b116302342553dd765b7297579ed511f111d0cedb442aeda6",
    ),
    "macos-arm64": (
        "agg-aarch64-apple-darwin",
        "742b2b6230529b72f310acb835e9479496000f2eabc97b0993cabe1d7fe70171",
    ),
    "macos-x86_64": (
        "agg-x86_64-apple-darwin",
        "1462150b611d231d2950d10a676303eaeb1019ff330735882aaae09b52e2e1c1",
    ),
}


def host_target() -> str:
    system = {"Darwin": "macos", "Linux": "linux"}.get(
        platform.system(), platform.system().lower()
    )
    machine = {"amd64": "x86_64", "x64": "x86_64", "aarch64": "arm64"}.get(
        platform.machine().lower(), platform.machine().lower()
    )
    return f"{system}-{machine}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", default=host_target(), choices=tuple(ASSETS))
    parser.add_argument("--out", type=Path, default=Path(".termproof-build/agg"))
    args = parser.parse_args()

    asset, expected_sha256 = ASSETS[args.target]
    url = f"{BASE_URL}/{asset}"
    output = args.out / args.target / "agg"
    output.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as response, output.open("wb") as binary:
        shutil.copyfileobj(response, binary)
    actual_sha256 = hashlib.sha256(output.read_bytes()).hexdigest()
    if actual_sha256 != expected_sha256:
        output.unlink(missing_ok=True)
        raise SystemExit(f"agg binary checksum mismatch for {args.target}")
    output.chmod(0o755)
    (args.out / "PROVENANCE.md").write_text(
        "\n".join(
            [
                f"agg {VERSION}",
                f"target: {args.target}",
                f"asset: {asset}",
                f"source: {url}",
                f"sha256: {expected_sha256}",
                "license: MIT",
                "",
            ]
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
