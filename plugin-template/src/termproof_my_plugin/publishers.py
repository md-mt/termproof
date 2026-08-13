"""Example custom artifact publisher for TermProof.

Implements a publisher that copies evidence into a local directory tree and
serves it under a base URL. Register it in config:

.. code-block:: yaml

   artifact_publishers:
     my_store: termproof_my_plugin.publishers:MyStore
"""

from __future__ import annotations

import shutil
from pathlib import Path

from termproof.evidence_publish import PublishTarget
from termproof.models import PublishedArtifact


class MyStore:
    """Copy evidence into a directory that is served over HTTP.

    CLI usage::

        python -m termproof.evidence_publish publish-videos \\
            --base-dir .termproof/pr-base --head-dir .termproof/ci \\
            --publisher my_store --video-base-url https://evidence.example

    Protocol compatibility:
    - Requires a TermProof with the ``artifact_publishers`` config key
    - ``name`` attribute must match config ``artifact_publishers`` key
    - ``publish(source, key) -> PublishedArtifact`` required
    - ``from_target(target)`` is optional; without it the publisher is
      constructed with no arguments
    """

    name = "my_store"

    def __init__(self, root: Path = Path("published"), base_url: str = "") -> None:
        self.root = root
        self.base_url = base_url.rstrip("/")

    @classmethod
    def from_target(cls, target: PublishTarget) -> MyStore:
        # ``bucket`` names the destination; this store reads it as a directory.
        return cls(
            root=Path(target.bucket or "published"),
            base_url=target.base_url,
        )

    def publish(self, source: Path, key: str) -> PublishedArtifact:
        if not source.is_file():
            return PublishedArtifact(
                source=source,
                key=key,
                published=False,
                detail=f"no such file: {source}",
            )
        destination = self.root / key
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        # An empty base URL means the bytes are stored but not addressable, so
        # reports keep pointing at the local file rather than a broken link.
        url = f"{self.base_url}/{key}" if self.base_url else ""
        return PublishedArtifact(source=source, key=key, url=url)
