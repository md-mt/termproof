#!/usr/bin/env python3
"""Build the pinned agg source into the target-specific wheel staging directory."""
from __future__ import annotations
import argparse, hashlib, os, platform, shutil, subprocess, tarfile, tempfile, urllib.request
from pathlib import Path

COMMIT = "26ca84c02523973198fca28533369edcfc7ed929"
SHA256 = "cc8855ddac53df52955365469ce8a3c84c42d74e5470598b31ad172aa3030b0d"
URL = f"https://github.com/asciinema/agg/archive/{COMMIT}.tar.gz"

def host_target() -> str:
    system = {"Darwin":"macos", "Linux":"linux"}.get(platform.system(), platform.system().lower())
    machine = {"amd64":"x86_64", "x64":"x86_64", "aarch64":"arm64"}.get(platform.machine().lower(), platform.machine().lower())
    return f"{system}-{machine}"

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", default=host_target(), choices=("linux-x86_64","macos-arm64","macos-x86_64"))
    parser.add_argument("--out", type=Path, default=Path(".termproof-build/agg"))
    args = parser.parse_args()
    if args.target != host_target(): raise SystemExit(f"native build required: requested {args.target}, host is {host_target()}")
    with tempfile.TemporaryDirectory() as temp:
        temp = Path(temp); archive = temp / "agg.tar.gz"
        with urllib.request.urlopen(URL) as response, archive.open("wb") as output: shutil.copyfileobj(response, output)
        if hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256: raise SystemExit("agg source checksum mismatch")
        with tarfile.open(archive) as source: source.extractall(temp, filter="data")
        source_dir = next(temp.glob("agg-*"))
        subprocess.run(["cargo", "build", "--release", "--locked"], cwd=source_dir, check=True)
        output = args.out / args.target / "agg"; output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_dir / "target/release/agg", output); output.chmod(0o755)
        (args.out / "PROVENANCE.md").write_text(f"agg v1.9.0\ncommit: {COMMIT}\nsource: {URL}\nsha256: {SHA256}\nlicense: MIT\n", encoding="utf-8")
if __name__ == "__main__": main()
