from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from termproof.config import VerifierConfig
from termproof.evidence_publish import (
    PublishTarget,
    S3ArtifactPublisher,
    build_video_url_map,
    main,
    publish_videos_to_s3,
    resolve_artifact_publisher,
    rewrite_report_video_links,
    url_map_from_published,
)
from termproof.models import PublishedArtifact
from termproof.protocols import ArtifactPublisher
from termproof.runner import VerificationRunner

REPORT = """# Report

| video | {head}/session.mp4 |
| video | {base}/session.mp4 |
"""


class RecordingPublisher:
    """A minimal third-party publisher: records what it was asked to publish."""

    name = "recording"

    def __init__(self, base_url: str = "https://artifacts.example/store") -> None:
        self.base_url = base_url
        self.calls: list[tuple[Path, str]] = []

    @classmethod
    def from_target(cls, target: PublishTarget) -> RecordingPublisher:
        return cls(base_url=target.base_url)

    def publish(self, source: Path, key: str) -> PublishedArtifact:
        self.calls.append((source, key))
        return PublishedArtifact(source=source, key=key, url=f"{self.base_url}/{key}")


class RefusingPublisher:
    """A publisher that declines a file instead of raising."""

    name = "refusing"

    def publish(self, source: Path, key: str) -> PublishedArtifact:
        return PublishedArtifact(
            source=source,
            key=key,
            published=False,
            detail="unsupported artifact",
        )


def _evidence_tree(root: Path) -> tuple[Path, Path]:
    base = root / "base"
    head = root / "head"
    for scope in (base, head):
        run = scope / "run-1"
        run.mkdir(parents=True)
        (run / "session.mp4").write_bytes(b"video")
    return base, head


class ArtifactPublisherProtocolTests(unittest.TestCase):
    def test_builtin_publisher_is_registered_and_resolvable(self) -> None:
        runner = VerificationRunner()

        publisher = runner.artifact_publisher_registry.get("s3")

        self.assertEqual(["s3"], runner.artifact_publisher_registry.names())
        self.assertIsInstance(publisher, S3ArtifactPublisher)
        self.assertEqual("s3", publisher.name)

    def test_publisher_satisfies_the_protocol(self) -> None:
        publishers: list[ArtifactPublisher] = [
            S3ArtifactPublisher(),
            RecordingPublisher(),
        ]

        for publisher in publishers:
            self.assertTrue(callable(publisher.publish))
            self.assertIsInstance(publisher.name, str)

    def test_third_party_publisher_round_trips_through_config(self) -> None:
        config = replace(
            VerifierConfig.builtin(),
            artifact_publishers={
                "recording": f"{__name__}:RecordingPublisher",
            },
        )

        publisher = resolve_artifact_publisher(
            "recording",
            PublishTarget(base_url="https://artifacts.example/store"),
            config=config,
        )
        published = publisher.publish(Path("/tmp/run/session.mp4"), "videos/head/session.mp4")

        self.assertIsInstance(publisher, RecordingPublisher)
        self.assertEqual([(Path("/tmp/run/session.mp4"), "videos/head/session.mp4")], publisher.calls)
        self.assertEqual(
            "https://artifacts.example/store/videos/head/session.mp4",
            published.url,
        )
        self.assertTrue(published.published)

    def test_publisher_without_from_target_is_constructed_bare(self) -> None:
        config = replace(
            VerifierConfig.builtin(),
            artifact_publishers={"refusing": f"{__name__}:RefusingPublisher"},
        )

        publisher = resolve_artifact_publisher(
            "refusing",
            PublishTarget(bucket="ignored"),
            config=config,
        )

        self.assertIsInstance(publisher, RefusingPublisher)

    def test_unknown_publisher_names_the_available_ones(self) -> None:
        with self.assertRaises(KeyError) as caught:
            resolve_artifact_publisher(
                "nope",
                PublishTarget(),
                config=VerifierConfig.builtin(),
            )

        self.assertIn("s3", str(caught.exception))

    def test_url_map_skips_artifacts_the_publisher_could_not_address(self) -> None:
        published = [
            PublishedArtifact(source=Path("/tmp/a.mp4"), key="a", url="https://host/a"),
            RefusingPublisher().publish(Path("/tmp/b.mp4"), "b"),
        ]

        url_map = url_map_from_published(published)

        self.assertEqual({"/tmp/a.mp4": "https://host/a"}, url_map)

    def test_url_map_drives_report_rewriting(self) -> None:
        published = [
            PublishedArtifact(
                source=Path("/tmp/head/session.mp4"),
                key="videos/head/session.mp4",
                url="https://host/videos/head/session.mp4",
            )
        ]

        rewritten = rewrite_report_video_links(
            "see /tmp/head/session.mp4 for evidence",
            url_map_from_published(published),
        )

        self.assertEqual(
            "see https://host/videos/head/session.mp4 for evidence",
            rewritten,
        )


class S3ArtifactPublisherTests(unittest.TestCase):
    def test_dry_run_names_the_url_without_uploading(self) -> None:
        publisher = S3ArtifactPublisher(
            bucket="evidence",
            base_url="https://cdn.example/",
            dry_run=True,
        )

        # An upload would raise, since _upload_file is not stubbed here.
        published = publisher.publish(Path("/tmp/session.mp4"), "videos/head/session.mp4")

        self.assertFalse(published.published)
        self.assertEqual("dry run: not uploaded", published.detail)
        self.assertEqual("https://cdn.example/videos/head/session.mp4", published.url)

    def test_upload_passes_bucket_key_and_endpoint_through(self) -> None:
        uploads: list[tuple[Path, str, str, str | None]] = []
        publisher = S3ArtifactPublisher(
            bucket="evidence",
            endpoint_url="https://api.example",
            base_url="https://cdn.example",
        )

        with _stub_upload(uploads):
            published = publisher.publish(Path("/tmp/session.mp4"), "videos/head/session.mp4")

        self.assertEqual(
            [(Path("/tmp/session.mp4"), "evidence", "videos/head/session.mp4", "https://api.example")],
            uploads,
        )
        self.assertTrue(published.published)
        self.assertEqual("https://cdn.example/videos/head/session.mp4", published.url)

    def test_upload_without_a_base_url_reports_no_url(self) -> None:
        publisher = S3ArtifactPublisher(bucket="evidence")

        with _stub_upload([]):
            published = publisher.publish(Path("/tmp/session.mp4"), "key")

        self.assertTrue(published.published)
        self.assertEqual("", published.url)


class RefactoredS3PathTests(unittest.TestCase):
    """The S3/R2 publishing path must behave exactly as it did before."""

    def test_manifest_entries_keep_their_shape_and_key_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, head = _evidence_tree(Path(tmp))

            entries = publish_videos_to_s3(
                base,
                head,
                bucket="evidence",
                pr_number="7",
                run_id="99",
                dry_run=True,
            )

        self.assertEqual(
            [
                {
                    "scope": "base",
                    "source": (base / "run-1" / "session.mp4").as_posix(),
                    "path": "run-1/session.mp4",
                    "key": "termproof/videos/pr/7/99/base/run-1/session.mp4",
                },
                {
                    "scope": "head",
                    "source": (head / "run-1" / "session.mp4").as_posix(),
                    "path": "run-1/session.mp4",
                    "key": "termproof/videos/pr/7/99/head/run-1/session.mp4",
                },
            ],
            entries,
        )

    def test_key_layout_omits_pr_and_run_when_they_are_unset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, head = _evidence_tree(Path(tmp))

            entries = publish_videos_to_s3(base, head, bucket="evidence", dry_run=True)

        self.assertEqual(
            ["termproof/videos/base/run-1/session.mp4", "termproof/videos/head/run-1/session.mp4"],
            [entry["key"] for entry in entries],
        )

    def test_missing_evidence_root_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, head = _evidence_tree(Path(tmp))

            entries = publish_videos_to_s3(
                Path(tmp) / "absent",
                head,
                bucket="evidence",
                dry_run=True,
            )

        self.assertEqual(["head"], [entry["scope"] for entry in entries])

    def test_dry_run_uploads_nothing(self) -> None:
        uploads: list[tuple[Path, str, str, str | None]] = []
        with tempfile.TemporaryDirectory() as tmp:
            base, head = _evidence_tree(Path(tmp))

            with _stub_upload(uploads):
                publish_videos_to_s3(base, head, bucket="evidence", dry_run=True)

        self.assertEqual([], uploads)

    def test_every_video_is_uploaded_to_its_key(self) -> None:
        uploads: list[tuple[Path, str, str, str | None]] = []
        with tempfile.TemporaryDirectory() as tmp:
            base, head = _evidence_tree(Path(tmp))

            with _stub_upload(uploads):
                publish_videos_to_s3(
                    base,
                    head,
                    bucket="evidence",
                    prefix="/custom/prefix/",
                    pr_number="7",
                    run_id="99",
                    endpoint_url="https://api.example",
                )

        self.assertEqual(
            [
                "custom/prefix/pr/7/99/base/run-1/session.mp4",
                "custom/prefix/pr/7/99/head/run-1/session.mp4",
            ],
            [key for _, _, key, _ in uploads],
        )
        self.assertEqual({"evidence"}, {bucket for _, bucket, _, _ in uploads})
        self.assertEqual({"https://api.example"}, {endpoint for *_, endpoint in uploads})

    def test_url_map_covers_both_path_spellings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, head = _evidence_tree(Path(tmp))

            url_map = build_video_url_map(
                base,
                head,
                "https://cdn.example/",
                pr_number="7",
                run_id="99",
            )

        video = head / "run-1" / "session.mp4"
        expected = "https://cdn.example/termproof/videos/pr/7/99/head/run-1/session.mp4"
        self.assertEqual(expected, url_map[str(video)])
        self.assertEqual(expected, url_map[video.as_posix()])

    def test_url_map_percent_encodes_the_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "base"
            (base / "run one").mkdir(parents=True)
            (base / "run one" / "session.mp4").write_bytes(b"video")

            url_map = build_video_url_map(base, Path(tmp) / "absent", "https://cdn.example")

        self.assertEqual(
            ["https://cdn.example/termproof/videos/base/run%20one/session.mp4"],
            sorted(set(url_map.values())),
        )

    def test_missing_upload_tooling_still_raises(self) -> None:
        publisher = S3ArtifactPublisher(bucket="evidence")

        with _no_upload_tooling():
            with self.assertRaises(RuntimeError) as caught:
                publisher.publish(Path("/tmp/session.mp4"), "key")

        self.assertIn("boto3", str(caught.exception))


class PublishVideosCommandTests(unittest.TestCase):
    def test_command_writes_the_manifest_and_rewrites_reports(self) -> None:
        uploads: list[tuple[Path, str, str, str | None]] = []
        with tempfile.TemporaryDirectory() as tmp:
            base, head = _evidence_tree(Path(tmp))
            out = Path(tmp) / "out"
            (head / "latest-report.md").write_text(
                REPORT.format(base=base / "run-1", head=head / "run-1"),
                encoding="utf-8",
            )

            with _stub_upload(uploads), contextlib.redirect_stdout(io.StringIO()):
                code = main(
                    [
                        "publish-videos",
                        "--base-dir",
                        str(base),
                        "--head-dir",
                        str(head),
                        "--bucket",
                        "evidence",
                        "--pr-number",
                        "7",
                        "--run-id",
                        "99",
                        "--video-base-url",
                        "https://cdn.example",
                        "--out",
                        str(out),
                    ]
                )

            manifest = json.loads((out / "pr" / "7" / "99" / "video-manifest.json").read_text(encoding="utf-8"))
            report = (head / "latest-report.md").read_text(encoding="utf-8")

        self.assertEqual(0, code)
        self.assertEqual(2, len(uploads))
        self.assertEqual(
            ["termproof/videos/pr/7/99/base/run-1/session.mp4", "termproof/videos/pr/7/99/head/run-1/session.mp4"],
            [entry["key"] for entry in manifest],
        )
        self.assertIn("https://cdn.example/termproof/videos/pr/7/99/head/run-1/session.mp4", report)
        self.assertIn("https://cdn.example/termproof/videos/pr/7/99/base/run-1/session.mp4", report)
        self.assertNotIn(str(head / "run-1" / "session.mp4"), report)

    def test_dry_run_still_rewrites_reports_without_uploading(self) -> None:
        uploads: list[tuple[Path, str, str, str | None]] = []
        with tempfile.TemporaryDirectory() as tmp:
            base, head = _evidence_tree(Path(tmp))
            (head / "latest-report.md").write_text(
                REPORT.format(base=base / "run-1", head=head / "run-1"),
                encoding="utf-8",
            )

            with _stub_upload(uploads), contextlib.redirect_stdout(io.StringIO()) as stdout:
                code = main(
                    [
                        "publish-videos",
                        "--base-dir",
                        str(base),
                        "--head-dir",
                        str(head),
                        "--video-base-url",
                        "https://cdn.example",
                        "--dry-run",
                    ]
                )

            report = (head / "latest-report.md").read_text(encoding="utf-8")

        self.assertEqual(0, code)
        self.assertEqual([], uploads)
        self.assertIn("(dry-run)", stdout.getvalue())
        self.assertIn("https://cdn.example/termproof/videos/head/run-1/session.mp4", report)

    def test_reports_are_untouched_without_a_base_url(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, head = _evidence_tree(Path(tmp))
            original = REPORT.format(base=base / "run-1", head=head / "run-1")
            (head / "latest-report.md").write_text(original, encoding="utf-8")

            with _stub_upload([]), contextlib.redirect_stdout(io.StringIO()):
                code = main(
                    [
                        "publish-videos",
                        "--base-dir",
                        str(base),
                        "--head-dir",
                        str(head),
                        "--bucket",
                        "evidence",
                    ]
                )

            report = (head / "latest-report.md").read_text(encoding="utf-8")

        self.assertEqual(0, code)
        self.assertEqual(original, report)


@contextlib.contextmanager
def _stub_upload(uploads: list[tuple[Path, str, str, str | None]]):
    from termproof import evidence_publish

    original = evidence_publish._upload_file

    def record(source: Path, bucket: str, key: str, endpoint_url: str | None = None) -> None:
        uploads.append((source, bucket, key, endpoint_url))

    evidence_publish._upload_file = record
    try:
        yield
    finally:
        evidence_publish._upload_file = original


@contextlib.contextmanager
def _no_upload_tooling():
    """Hide both the AWS CLI and boto3, as an unprovisioned machine would."""
    import builtins

    from termproof import evidence_publish

    original_which = evidence_publish.shutil.which
    original_import = builtins.__import__

    def blocked_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "boto3":
            raise ImportError("no boto3")
        return original_import(name, *args, **kwargs)  # type: ignore[arg-type]

    evidence_publish.shutil.which = lambda _name: None
    builtins.__import__ = blocked_import
    try:
        yield
    finally:
        evidence_publish.shutil.which = original_which
        builtins.__import__ = original_import


if __name__ == "__main__":
    unittest.main()
