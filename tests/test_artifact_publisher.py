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


class DecliningPublisher:
    """Declines every artifact, but names the URL it would have used."""

    name = "declining"

    def publish(self, source: Path, key: str) -> PublishedArtifact:
        return PublishedArtifact(
            source=source,
            key=key,
            url=f"https://cdn.example/{key}",
            published=False,
            detail="store unavailable",
        )


class PartialPublisher:
    """Stores head evidence and declines base evidence."""

    name = "partial"

    def publish(self, source: Path, key: str) -> PublishedArtifact:
        if "/base/" in key:
            return PublishedArtifact(source=source, key=key, published=False, detail="store unavailable")
        return PublishedArtifact(source=source, key=key, url=f"https://cdn.example/{key}")


class TenantPublisher:
    """Maps keys into its own namespace, and spells URLs its own way."""

    name = "tenant"

    def __init__(self, base_url: str = "", dry_run: bool = False) -> None:
        self.base_url = base_url.rstrip("/")
        self.dry_run = dry_run

    @classmethod
    def from_target(cls, target: PublishTarget) -> TenantPublisher:
        return cls(base_url=target.base_url, dry_run=target.dry_run)

    def publish(self, source: Path, key: str) -> PublishedArtifact:
        url = f"{self.base_url}/tenant/{key}" if self.base_url else ""
        if self.dry_run:
            return PublishedArtifact(
                source=source,
                key=key,
                url=url,
                published=False,
                detail="dry run: not uploaded",
            )
        return PublishedArtifact(source=source, key=key, url=url)


class UnaddressablePublisher:
    """Takes the bytes but cannot name a public address for them."""

    name = "silent"

    @classmethod
    def from_target(cls, target: PublishTarget) -> UnaddressablePublisher:
        return cls()

    def publish(self, source: Path, key: str) -> PublishedArtifact:
        return PublishedArtifact(source=source, key=key)


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

    def test_registry_resolves_a_publisher_only_when_it_is_asked_for(self) -> None:
        config = replace(
            VerifierConfig.builtin(),
            artifact_publishers={"absent": "termproof_absent_dependency.publishers:Store"},
        )

        runner = VerificationRunner(config=config)

        self.assertIn("absent", runner.artifact_publisher_registry.names())
        with self.assertRaises(ModuleNotFoundError):
            runner.artifact_publisher_registry.get("absent")

    def test_url_map_skips_an_artifact_that_was_never_transferred(self) -> None:
        published = [DecliningPublisher().publish(Path("/tmp/a.mp4"), "a")]

        self.assertEqual("https://cdn.example/a", published[0].url)
        self.assertEqual({}, url_map_from_published(published))

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


class PublishVideosResultReportingTests(unittest.TestCase):
    """What the command reports has to be what the publisher actually did."""

    def test_a_wholly_declined_batch_fails_and_says_why(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, head = _evidence_tree(Path(tmp))
            out = Path(tmp) / "out"
            original = REPORT.format(base=base / "run-1", head=head / "run-1")
            (head / "latest-report.md").write_text(original, encoding="utf-8")

            with (
                _publishers(declining=f"{__name__}:DecliningPublisher"),
                contextlib.redirect_stdout(io.StringIO()) as stdout,
            ):
                code = main(
                    [
                        "publish-videos",
                        "--base-dir",
                        str(base),
                        "--head-dir",
                        str(head),
                        "--publisher",
                        "declining",
                        "--out",
                        str(out),
                    ]
                )

            manifest = json.loads((out / "video-manifest.json").read_text(encoding="utf-8"))
            report = (head / "latest-report.md").read_text(encoding="utf-8")

        self.assertEqual(1, code)
        self.assertEqual([], manifest)
        self.assertIn("store unavailable", stdout.getvalue())
        self.assertIn("0 videos published", stdout.getvalue())
        self.assertEqual(original, report)

    def test_a_partly_declined_batch_fails_and_stores_the_rest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, head = _evidence_tree(Path(tmp))
            out = Path(tmp) / "out"
            (head / "latest-report.md").write_text(
                REPORT.format(base=base / "run-1", head=head / "run-1"),
                encoding="utf-8",
            )

            with (
                _publishers(partial=f"{__name__}:PartialPublisher"),
                contextlib.redirect_stdout(io.StringIO()) as stdout,
            ):
                code = main(
                    [
                        "publish-videos",
                        "--base-dir",
                        str(base),
                        "--head-dir",
                        str(head),
                        "--publisher",
                        "partial",
                        "--out",
                        str(out),
                    ]
                )

            manifest = json.loads((out / "video-manifest.json").read_text(encoding="utf-8"))
            report = (head / "latest-report.md").read_text(encoding="utf-8")

        # One video silently missing is the same false success as none stored,
        # so a partial decline fails the command too.
        self.assertEqual(1, code)
        self.assertEqual(["termproof/videos/head/run-1/session.mp4"], [entry["key"] for entry in manifest])
        self.assertIn("1 videos published", stdout.getvalue())
        self.assertIn("store unavailable", stdout.getvalue())
        self.assertIn("https://cdn.example/termproof/videos/head/run-1/session.mp4", report)
        self.assertIn(str(base / "run-1" / "session.mp4"), report)


class PublishVideosPublisherSelectionTests(unittest.TestCase):
    def test_s3_still_demands_a_bucket_outside_a_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, head = _evidence_tree(Path(tmp))

            with contextlib.redirect_stderr(io.StringIO()) as stderr:
                with self.assertRaises(SystemExit) as caught:
                    main(["publish-videos", "--base-dir", str(base), "--head-dir", str(head)])

        self.assertEqual(2, caught.exception.code)
        self.assertIn("--bucket is required (or set TERM_PROOF_VIDEO_BUCKET) unless --dry-run", stderr.getvalue())

    def test_another_publisher_does_not_inherit_the_bucket_requirement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, head = _evidence_tree(Path(tmp))
            (head / "latest-report.md").write_text(
                REPORT.format(base=base / "run-1", head=head / "run-1"),
                encoding="utf-8",
            )

            with _publishers(recording=f"{__name__}:RecordingPublisher"), contextlib.redirect_stdout(io.StringIO()):
                code = main(
                    [
                        "publish-videos",
                        "--base-dir",
                        str(base),
                        "--head-dir",
                        str(head),
                        "--publisher",
                        "recording",
                        "--video-base-url",
                        "https://artifacts.example/store",
                    ]
                )

            report = (head / "latest-report.md").read_text(encoding="utf-8")

        self.assertEqual(0, code)
        self.assertIn(
            "https://artifacts.example/store/termproof/videos/head/run-1/session.mp4",
            report,
        )


class DryRunSpeaksForItsOwnStoreTests(unittest.TestCase):
    """A dry run must report where the *selected* publisher would put evidence."""

    def test_report_links_use_the_publishers_own_urls_not_the_s3_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "base"
            head = root / "head"
            for scope in (base, head):
                run = scope / "run one"
                run.mkdir(parents=True)
                (run / "session.mp4").write_bytes(b"video")
            (head / "latest-report.md").write_text(
                REPORT.format(base=base / "run one", head=head / "run one"),
                encoding="utf-8",
            )

            with _publishers(tenant=f"{__name__}:TenantPublisher"), contextlib.redirect_stdout(io.StringIO()):
                code = main(
                    [
                        "publish-videos",
                        "--base-dir",
                        str(base),
                        "--head-dir",
                        str(head),
                        "--publisher",
                        "tenant",
                        "--video-base-url",
                        "https://evidence.example",
                        "--dry-run",
                    ]
                )

            report = (head / "latest-report.md").read_text(encoding="utf-8")

        self.assertEqual(0, code)
        # The store's own namespace, with the space left exactly as the store
        # spelled it - not the percent-encoded s3 key layout.
        self.assertIn("https://evidence.example/tenant/termproof/videos/head/run one/session.mp4", report)
        self.assertNotIn("run%20one", report)

    def test_a_publisher_that_cannot_address_an_artifact_keeps_the_local_link(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, head = _evidence_tree(Path(tmp))
            (head / "latest-report.md").write_text(
                REPORT.format(base=base / "run-1", head=head / "run-1"),
                encoding="utf-8",
            )

            with _publishers(silent=f"{__name__}:UnaddressablePublisher"), contextlib.redirect_stdout(io.StringIO()):
                code = main(
                    [
                        "publish-videos",
                        "--base-dir",
                        str(base),
                        "--head-dir",
                        str(head),
                        "--publisher",
                        "silent",
                        "--video-base-url",
                        "https://evidence.example",
                        "--dry-run",
                    ]
                )

            report = (head / "latest-report.md").read_text(encoding="utf-8")

        self.assertEqual(0, code)
        self.assertIn(str(head / "run-1" / "session.mp4"), report)
        self.assertNotIn("https://evidence.example", report)

    def test_dry_run_is_refused_by_a_publisher_that_cannot_see_the_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, head = _evidence_tree(Path(tmp))

            with (
                _publishers(refusing=f"{__name__}:RefusingPublisher"),
                contextlib.redirect_stderr(io.StringIO()) as stderr,
            ):
                with self.assertRaises(SystemExit) as caught:
                    main(
                        [
                            "publish-videos",
                            "--base-dir",
                            str(base),
                            "--head-dir",
                            str(head),
                            "--publisher",
                            "refusing",
                            "--dry-run",
                        ]
                    )

        self.assertEqual(2, caught.exception.code)
        self.assertIn("--dry-run cannot be honoured by publisher 'refusing'", stderr.getvalue())

    def test_the_destination_line_names_the_publisher_instead_of_guessing_a_scheme(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, head = _evidence_tree(Path(tmp))

            with (
                _publishers(recording=f"{__name__}:RecordingPublisher"),
                contextlib.redirect_stdout(io.StringIO()) as stdout,
            ):
                code = main(
                    [
                        "publish-videos",
                        "--base-dir",
                        str(base),
                        "--head-dir",
                        str(head),
                        "--publisher",
                        "recording",
                        "--bucket",
                        "evidence-dir",
                    ]
                )

        self.assertEqual(0, code)
        self.assertIn("2 videos published via recording", stdout.getvalue())
        self.assertNotIn("s3://", stdout.getvalue())


@contextlib.contextmanager
def _publishers(**publishers: str):
    """Register extra publishers for the duration of a CLI invocation."""
    from termproof import evidence_publish

    builtin = VerifierConfig.builtin()
    config = replace(
        builtin,
        artifact_publishers={**builtin.artifact_publishers, **publishers},
    )
    original = evidence_publish.load_config
    evidence_publish.load_config = lambda *args, **kwargs: config
    try:
        yield
    finally:
        evidence_publish.load_config = original


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
