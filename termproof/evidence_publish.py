from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from urllib.parse import quote

IMAGE_SUFFIXES = {".gif", ".jpeg", ".jpg", ".png", ".svg"}


def prepare_screenshot_evidence(
    base_dir: Path,
    head_dir: Path,
    out_dir: Path,
    pr_number: str,
    run_id: str,
) -> list[dict[str, str]]:
    root = out_dir / "pr" / pr_number / run_id
    manifest = [
        *_copy_images(base_dir, root / "base", "base"),
        *_copy_images(head_dir, root / "head", "head"),
    ]
    root.mkdir(parents=True, exist_ok=True)
    (root / "screenshot-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def rewrite_screenshot_links(text: str, root: Path, url_prefix: str) -> str:
    if not url_prefix or not root.exists():
        return text
    prefix = url_prefix.rstrip("/")
    for image in _image_files(root):
        rel = image.relative_to(root).as_posix()
        url = f"{prefix}/{quote(rel, safe='/._-~')}"
        for value in {str(image), image.as_posix()}:
            text = text.replace(value, url)
    return text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m termproof.evidence_publish")
    subparsers = parser.add_subparsers(dest="command", required=True)
    screenshots = subparsers.add_parser("screenshots")
    screenshots.add_argument("--base-dir", type=Path, required=True)
    screenshots.add_argument("--head-dir", type=Path, required=True)
    screenshots.add_argument("--out", type=Path, required=True)
    screenshots.add_argument("--pr-number", required=True)
    screenshots.add_argument("--run-id", required=True)

    args = parser.parse_args(argv)
    if args.command == "screenshots":
        manifest = prepare_screenshot_evidence(
            args.base_dir,
            args.head_dir,
            args.out,
            args.pr_number,
            args.run_id,
        )
        print(f"{len(manifest)} screenshots prepared")
        return 0
    raise AssertionError(args.command)


def _copy_images(source: Path, target: Path, scope: str) -> list[dict[str, str]]:
    if not source.exists():
        return []
    entries: list[dict[str, str]] = []
    for image in _image_files(source):
        rel = image.relative_to(source)
        dest = target / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(image, dest)
        entries.append({"scope": scope, "source": image.as_posix(), "path": rel.as_posix()})
    return entries


def _image_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )


if __name__ == "__main__":
    raise SystemExit(main())
