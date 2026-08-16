from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from termproof_my_plugin.publishers import MyStore

from termproof.evidence_publish import PublishTarget, url_map_from_published


class MyStorePublisherTest(unittest.TestCase):
    def test_publish_copies_the_file_and_names_its_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "session.mp4"
            source.write_bytes(b"video")
            store = MyStore.from_target(
                PublishTarget(bucket=str(root / "store"), base_url="https://evidence.example/")
            )

            published = store.publish(source, "pr/7/head/session.mp4")

            self.assertTrue(published.published)
            self.assertEqual("https://evidence.example/pr/7/head/session.mp4", published.url)
            self.assertEqual(b"video", (root / "store" / "pr/7/head/session.mp4").read_bytes())

    def test_publish_reports_a_missing_file_without_raising(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MyStore(root=Path(tmp) / "store")

            published = store.publish(Path(tmp) / "absent.mp4", "key")

            self.assertFalse(published.published)
            self.assertIn("no such file", published.detail)

    def test_dry_run_names_the_url_without_copying_anything(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "session.mp4"
            source.write_bytes(b"video")
            store = MyStore.from_target(
                PublishTarget(
                    bucket=str(root / "store"),
                    base_url="https://evidence.example/",
                    dry_run=True,
                )
            )

            published = store.publish(source, "pr/7/head/session.mp4")

            self.assertFalse(published.published)
            self.assertEqual("dry run: not uploaded", published.detail)
            self.assertEqual("https://evidence.example/pr/7/head/session.mp4", published.url)
            self.assertFalse((root / "store").exists())

    def test_unaddressable_artifacts_are_left_out_of_the_url_map(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "session.mp4"
            source.write_bytes(b"video")
            store = MyStore(root=root / "store")

            published = store.publish(source, "key")

            self.assertTrue(published.published)
            self.assertEqual({}, url_map_from_published([published]))


if __name__ == "__main__":
    unittest.main()
