from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import quote

from .config import VerifierConfig, load_config
from .models import PublishedArtifact
from .registry import import_class

if TYPE_CHECKING:
    from .protocols import ArtifactPublisher

IMAGE_SUFFIXES = {".gif", ".jpeg", ".jpg", ".png", ".svg"}
VIDEO_SUFFIXES = {".mp4", ".webm", ".mov"}

DEFAULT_VIDEO_PREFIX = "termproof/videos"


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


def prepare_video_evidence(
    base_dir: Path,
    head_dir: Path,
    out_dir: Path,
    pr_number: str,
    run_id: str,
) -> list[dict[str, str]]:
    """Copy video files (mp4 etc.) from base/head dirs into branch payload.

    Mirrors prepare_screenshot_evidence but for VIDEO_SUFFIXES.  Videos are
    too large for the GitHub evidence branch by default, but the same helper
    is useful for local staging and for S3/R2 manifests.
    """
    root = out_dir / "pr" / pr_number / run_id
    manifest = [
        *_copy_videos(base_dir, root / "base", "base"),
        *_copy_videos(head_dir, root / "head", "head"),
    ]
    root.mkdir(parents=True, exist_ok=True)
    manifest_path = root / "video-manifest.json"
    # merge with screenshot manifest if present
    existing: list[dict[str, str]] = []
    screenshot_manifest = root / "screenshot-manifest.json"
    if screenshot_manifest.is_file():
        try:
            existing = json.loads(screenshot_manifest.read_text(encoding="utf-8"))
        except Exception:
            existing = []
    (manifest_path).write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    # Also write a combined manifest for convenience
    combined = existing + manifest
    if combined:
        (root / "evidence-manifest.json").write_text(
            json.dumps(combined, indent=2) + "\n",
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


def rewrite_video_links(text: str, root: Path, url_prefix: str) -> str:
    """Rewrite local video file paths to hosted URLs.

    Mirrors rewrite_screenshot_links but for VIDEO_SUFFIXES.  Used to replace
    ``.termproof/ci/.../session.mp4`` paths in report.md with
    ``https://<bucket>.<endpoint>/prefix/...`` URLs after S3/R2 publishing.
    """
    if not url_prefix or not root.exists():
        return text
    prefix = url_prefix.rstrip("/")
    for video in _video_files(root):
        rel = video.relative_to(root).as_posix()
        url = f"{prefix}/{quote(rel, safe='/._-~')}"
        for value in {str(video), video.as_posix()}:
            text = text.replace(value, url)
    return text


# ---------------------------------------------------------------------------
# Artifact publishing
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PublishTarget:
    """Where a publisher should put artifacts, as supplied by CLI or environment.

    These are deployment credentials and addresses rather than project
    settings, so they are passed at publish time instead of being read from
    ``.termproof/config.yaml``, which is checked in.
    """

    bucket: str = ""
    endpoint_url: str | None = None
    base_url: str = ""
    dry_run: bool = False


class S3ArtifactPublisher:
    """Publish artifacts to an S3-compatible bucket (AWS S3, Cloudflare R2, ...).

    Uses ``aws s3 cp`` via subprocess when available so no Python dependency is
    required. Falls back to ``boto3`` when the CLI is absent.

    ``base_url`` is the public URL prefix the bucket is served under, e.g.
    ``https://pub-xxx.r2.dev`` or ``https://s3.amazonaws.com/my-bucket``. It is
    separate from ``endpoint_url``, the S3 API endpoint used to write: a bucket
    is commonly written through one host and read through another, and only the
    read host belongs in a report link. Without it an upload still happens and
    the result simply carries no URL.
    """

    name = "s3"

    def __init__(
        self,
        bucket: str = "",
        endpoint_url: str | None = None,
        base_url: str = "",
        dry_run: bool = False,
    ) -> None:
        self.bucket = bucket
        self.endpoint_url = endpoint_url
        self.base_url = base_url.rstrip("/")
        self.dry_run = dry_run

    @classmethod
    def from_target(cls, target: PublishTarget) -> S3ArtifactPublisher:
        return cls(
            bucket=target.bucket,
            endpoint_url=target.endpoint_url,
            base_url=target.base_url,
            dry_run=target.dry_run,
        )

    def publish(self, source: Path, key: str) -> PublishedArtifact:
        url = f"{self.base_url}/{quote(key, safe='/._-~')}" if self.base_url else ""
        if self.dry_run:
            return PublishedArtifact(
                source=source,
                key=key,
                url=url,
                published=False,
                detail="dry run: not uploaded",
            )
        _upload_file(source, self.bucket, key, endpoint_url=self.endpoint_url)
        return PublishedArtifact(source=source, key=key, url=url)


def resolve_artifact_publisher(
    name: str,
    target: PublishTarget,
    config: VerifierConfig | None = None,
) -> ArtifactPublisher:
    """Build the configured publisher named ``name``.

    Publishers opt into deployment settings by exposing ``from_target``, the
    same way renderers opt into evidence config with ``from_config``. One that
    does not is constructed with no arguments.
    """
    config = config or load_config()
    qualname = config.artifact_publishers.get(name)
    if qualname is None:
        available = ", ".join(sorted(config.artifact_publishers))
        raise KeyError(f"unknown artifact publisher {name!r}; available: {available}")
    cls = import_class(qualname)
    factory = getattr(cls, "from_target", None)
    return cls() if factory is None else factory(target)


def url_map_from_published(published: Iterable[PublishedArtifact]) -> dict[str, str]:
    """Map every published artifact's local path onto its hosted URL.

    Reports link evidence by local path, so this is the bridge between
    publishing and :func:`rewrite_report_video_links`. Artifacts the publisher
    could not address are skipped: rewriting a link to an empty URL would break
    a report that currently points at a file the reader can still open.
    """
    url_map: dict[str, str] = {}
    for artifact in published:
        if not artifact.url:
            continue
        for local in {str(artifact.source), artifact.source.as_posix()}:
            url_map[local] = artifact.url
    return url_map


def _video_manifest_entries(
    base_dir: Path,
    head_dir: Path,
    prefix: str = DEFAULT_VIDEO_PREFIX,
    pr_number: str = "",
    run_id: str = "",
) -> list[dict[str, str]]:
    """Enumerate video evidence and assign each file its destination key.

    The key layout ``{prefix}/pr/{pr_number}/{run_id}/{base|head}/...`` is the
    caller's evidence layout, not a property of any store, which is why it is
    computed here and handed to the publisher rather than left to it.
    """
    prefix = prefix.strip("/")
    entries: list[dict[str, str]] = []
    for scope, source_root in (("base", base_dir), ("head", head_dir)):
        if not source_root.exists():
            continue
        for video in _video_files(source_root):
            rel = video.relative_to(source_root).as_posix()
            key = (
                f"{prefix}/pr/{pr_number}/{run_id}/{scope}/{rel}" if pr_number and run_id else f"{prefix}/{scope}/{rel}"
            )
            # Normalise double slashes if pr/run omitted
            key = key.replace("//", "/")
            entries.append({"scope": scope, "source": video.as_posix(), "path": rel, "key": key})
    return entries


def publish_videos_to_s3(
    base_dir: Path,
    head_dir: Path,
    bucket: str,
    prefix: str = DEFAULT_VIDEO_PREFIX,
    pr_number: str = "",
    run_id: str = "",
    endpoint_url: str | None = None,
    dry_run: bool = False,
) -> list[dict[str, str]]:
    """Upload video evidence to an S3-compatible bucket.

    Shorthand for driving :class:`S3ArtifactPublisher` over the video evidence
    under ``base_dir``/``head_dir``.

    Args:
        base_dir, head_dir: Evidence roots containing ``session.mp4`` files.
        bucket: S3 bucket name.
        prefix: Key prefix inside the bucket (e.g. ``termproof/videos``).
        pr_number, run_id: Used to build the object key layout
            ``{prefix}/pr/{pr_number}/{run_id}/{base|head}/...``.
        endpoint_url: S3-compatible endpoint, passed as ``--endpoint-url`` to
            the AWS CLI or as ``endpoint_url`` to boto3.
        dry_run: When True, build the manifest without uploading.

    Returns:
        Manifest entries ``{scope, source, path, key}``.
    """
    entries = _video_manifest_entries(base_dir, head_dir, prefix, pr_number, run_id)
    if dry_run or not entries:
        return entries
    publisher = S3ArtifactPublisher(bucket=bucket, endpoint_url=endpoint_url)
    for entry in entries:
        publisher.publish(Path(entry["source"]), entry["key"])
    return entries


def build_video_url_map(
    base_dir: Path,
    head_dir: Path,
    base_url: str,
    pr_number: str = "",
    run_id: str = "",
    prefix: str = DEFAULT_VIDEO_PREFIX,
) -> dict[str, str]:
    """Build a mapping from local video path -> hosted URL, without publishing.

    Used to rewrite ``report.md`` / ``latest-report.md`` links when the videos
    are known to be hosted already. After a publish, prefer
    :func:`url_map_from_published`, which reads the URLs the publisher actually
    reported instead of predicting them.
    """
    # A dry run is precisely "name the URL without moving the bytes", which is
    # what this asks for.
    publisher = S3ArtifactPublisher(base_url=base_url, dry_run=True)
    return url_map_from_published(
        publisher.publish(Path(entry["source"]), entry["key"])
        for entry in _video_manifest_entries(base_dir, head_dir, prefix, pr_number, run_id)
    )


def rewrite_report_video_links(text: str, url_map: dict[str, str]) -> str:
    """Replace local video paths in a report with hosted URLs using a pre-built map."""
    for local, url in url_map.items():
        text = text.replace(local, url)
    return text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m termproof.evidence_publish")
    subparsers = parser.add_subparsers(dest="command", required=True)
    screenshots = subparsers.add_parser("screenshots", help="prepare screenshot evidence for the evidence branch")
    screenshots.add_argument("--base-dir", type=Path, required=True)
    screenshots.add_argument("--head-dir", type=Path, required=True)
    screenshots.add_argument("--out", type=Path, required=True)
    screenshots.add_argument("--pr-number", required=True)
    screenshots.add_argument("--run-id", required=True)

    videos = subparsers.add_parser("videos", help="prepare video evidence (local staging + manifest)")
    videos.add_argument("--base-dir", type=Path, required=True)
    videos.add_argument("--head-dir", type=Path, required=True)
    videos.add_argument("--out", type=Path, required=True)
    videos.add_argument("--pr-number", required=True)
    videos.add_argument("--run-id", required=True)

    publish = subparsers.add_parser("publish-videos", help="publish video evidence to S3/R2")
    publish.add_argument("--base-dir", type=Path, required=True)
    publish.add_argument("--head-dir", type=Path, required=True)
    publish.add_argument("--bucket", default=os.environ.get("TERM_PROOF_VIDEO_BUCKET", ""))
    publish.add_argument("--prefix", default=os.environ.get("TERM_PROOF_VIDEO_PREFIX", DEFAULT_VIDEO_PREFIX))
    publish.add_argument("--pr-number", default=os.environ.get("PR_NUMBER", ""))
    publish.add_argument("--run-id", default=os.environ.get("RUN_ID", os.environ.get("GITHUB_RUN_ID", "")))
    publish.add_argument(
        "--endpoint-url", default=os.environ.get("AWS_ENDPOINT_URL_S3", os.environ.get("R2_ENDPOINT_URL", "")) or None
    )
    publish.add_argument("--video-base-url", default=os.environ.get("TERM_PROOF_VIDEO_BASE_URL", ""))
    publish.add_argument("--out", type=Path, default=None, help="optional out dir to stage + write video-manifest.json")
    publish.add_argument("--dry-run", action="store_true")
    publish.add_argument(
        "--publisher",
        default=os.environ.get("TERM_PROOF_ARTIFACT_PUBLISHER", "s3"),
        help="name of a publisher registered under 'artifact_publishers' in config",
    )

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
    if args.command == "videos":
        manifest = prepare_video_evidence(
            args.base_dir,
            args.head_dir,
            args.out,
            args.pr_number,
            args.run_id,
        )
        print(f"{len(manifest)} videos prepared")
        return 0
    if args.command == "publish-videos":
        if not args.bucket and not args.dry_run:
            parser.error("--bucket is required (or set TERM_PROOF_VIDEO_BUCKET) unless --dry-run")
        publisher = resolve_artifact_publisher(
            args.publisher,
            PublishTarget(
                bucket=args.bucket,
                endpoint_url=args.endpoint_url,
                base_url=args.video_base_url,
                dry_run=args.dry_run,
            ),
        )
        entries = _video_manifest_entries(
            args.base_dir,
            args.head_dir,
            args.prefix,
            args.pr_number,
            args.run_id,
        )
        published = [publisher.publish(Path(entry["source"]), entry["key"]) for entry in entries]
        if args.out is not None:
            root = args.out / "pr" / args.pr_number / args.run_id if args.pr_number and args.run_id else args.out
            root.mkdir(parents=True, exist_ok=True)
            (root / "video-manifest.json").write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
        # Rewrite video links in reports for whatever the publisher could address
        url_map = url_map_from_published(published)
        if url_map:
            for report_path in [
                *args.base_dir.rglob("report.md"),
                *args.head_dir.rglob("report.md"),
                args.base_dir / "latest-report.md",
                args.head_dir / "latest-report.md",
            ]:
                if report_path.is_file():
                    text = report_path.read_text(encoding="utf-8")
                    new_text = rewrite_report_video_links(text, url_map)
                    if new_text != text:
                        report_path.write_text(new_text, encoding="utf-8")
        print(
            f"{len(entries)} videos {'(dry-run) ' if args.dry_run else ''}published"
            + (f" to s3://{args.bucket}/{args.prefix}" if args.bucket else "")
        )
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


def _copy_videos(source: Path, target: Path, scope: str) -> list[dict[str, str]]:
    if not source.exists():
        return []
    entries: list[dict[str, str]] = []
    for video in _video_files(source):
        rel = video.relative_to(source)
        dest = target / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(video, dest)
        entries.append({"scope": scope, "source": video.as_posix(), "path": rel.as_posix()})
    return entries


def _image_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES)


def _video_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in VIDEO_SUFFIXES)


def _upload_file(source: Path, bucket: str, key: str, endpoint_url: str | None = None) -> None:
    # Prefer AWS CLI (works for both S3 and R2 with --endpoint-url)
    aws_cli = shutil.which("aws")
    if aws_cli:
        cmd = [aws_cli, "s3", "cp", str(source), f"s3://{bucket}/{key}", "--content-type", _content_type(source)]
        if endpoint_url:
            cmd.extend(["--endpoint-url", endpoint_url])
        subprocess.run(cmd, check=True)
        return
    # Fallback to boto3
    try:
        import boto3  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "Neither 'aws' CLI nor boto3 is available; install awscli or boto3 to publish videos. "
            "Use --dry-run to generate the manifest without uploading."
        ) from exc
    kwargs: dict[str, str] = {}
    if endpoint_url:
        kwargs["endpoint_url"] = endpoint_url
    s3 = boto3.client("s3", **kwargs)
    extra = {"ContentType": _content_type(source)}
    s3.upload_file(str(source), bucket, key, ExtraArgs=extra)


def _content_type(path: Path) -> str:
    return {
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".mov": "video/quicktime",
    }.get(path.suffix.lower(), "application/octet-stream")


if __name__ == "__main__":
    raise SystemExit(main())
