#!/usr/bin/env python3
"""Durable evidence hosting: publish screenshots/video to R2/S3 with stable links (RUST-025).

Uploads `.termproof/ci` and `.termproof/pr-base` artifacts to an S3-compatible
bucket (Cloudflare R2 or AWS S3) and rewrites PR comment links to stable URLs.

Environment:
  EVIDENCE_BUCKET       - R2/S3 bucket name
  EVIDENCE_ENDPOINT     - S3 endpoint URL (e.g. https://<account>.r2.cloudflarestorage.com)
  EVIDENCE_PREFIX       - prefix within bucket (default: termproof)
  AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY
  EVIDENCE_BASE_URL     - public base URL for stable links (e.g. https://evidence.termproof.dev)

Usage:
  python scripts/publish_evidence.py --head-dir .termproof/ci --base-dir .termproof/pr-base \
      --pr-number 123 --run-id 456 --out .termproof/evidence-links.json
  python scripts/publish_evidence.py --head-dir .termproof/ci --pr-number 123 --run-id 456 --dry-run

If bucket env is not set, runs in dry-run mode and prints what would be uploaded.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

IMAGE_SUFFIXES = {".gif", ".jpeg", ".jpg", ".png", ".svg"}
VIDEO_SUFFIXES = {".mp4", ".webm"}


def collect_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES | VIDEO_SUFFIXES)


def stable_url(base_url: str, prefix: str, pr_number: str, run_id: str, rel: str) -> str:
    # Stable link: {base_url}/{prefix}/pr/{pr_number}/{run_id}/{rel}
    base = base_url.rstrip("/")
    return f"{base}/{prefix}/pr/{pr_number}/{run_id}/{rel}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--head-dir", type=Path, required=True)
    parser.add_argument("--base-dir", type=Path, default=Path(".termproof/pr-base"))
    parser.add_argument("--pr-number", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--out", type=Path, default=Path(".termproof/evidence-links.json"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    bucket = os.environ.get("EVIDENCE_BUCKET", "")
    endpoint = os.environ.get("EVIDENCE_ENDPOINT", "")
    prefix = os.environ.get("EVIDENCE_PREFIX", "termproof")
    base_url = os.environ.get("EVIDENCE_BASE_URL", "")

    if not bucket or args.dry_run:
        print("Dry-run: would upload to bucket", bucket or "(not configured)")
        files = collect_files(args.head_dir) + collect_files(args.base_dir)
        print(f"Found {len(files)} evidence files")
        for f in files[:10]:
            rel = f.relative_to(
                args.head_dir if f.is_relative_to(args.head_dir) else args.base_dir
            )
            if base_url or bucket:
                url = stable_url(
                    base_url or f"https://{bucket}.r2.dev",
                    prefix,
                    args.pr_number,
                    args.run_id,
                    rel.as_posix(),
                )
            else:
                url = f"r2://{prefix}/pr/{args.pr_number}/{args.run_id}/{rel.as_posix()}"
            print(f"  {f} -> {url}")
        return 0

    # Real upload via boto3 if available, else aws cli fallback.
    try:
        import boto3  # type: ignore

        s3 = boto3.client("s3", endpoint_url=endpoint or None)
        for root in (args.head_dir, args.base_dir):
            for f in collect_files(root):
                rel = f.relative_to(root).as_posix()
                key = f"{prefix}/pr/{args.pr_number}/{args.run_id}/{rel}"
                s3.upload_file(str(f), bucket, key)
                print(f"uploaded {f} -> s3://{bucket}/{key}")
    except ImportError:
        print("boto3 not installed, falling back to aws cli", flush=True)
        import subprocess

        for root in (args.head_dir, args.base_dir):
            for f in collect_files(root):
                rel = f.relative_to(root).as_posix()
                key = f"{prefix}/pr/{args.pr_number}/{args.run_id}/{rel}"
                cmd = [
                    "aws",
                    "s3",
                    "cp",
                    str(f),
                    f"s3://{bucket}/{key}",
                ]
                if endpoint:
                    cmd += ["--endpoint-url", endpoint]
                subprocess.run(cmd, check=True)

    # Write links manifest for PR comment rewriting.
    links = {}
    for root in (args.head_dir, args.base_dir):
        for f in collect_files(root):
            rel = f.relative_to(root).as_posix()
            links[f.as_posix()] = stable_url(base_url, prefix, args.pr_number, args.run_id, rel)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(links, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(links)} links to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
