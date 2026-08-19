"""CI gets ffmpeg from the package's own dependency, not from a mirror.

Issue #183 stalled on `sudo apt-get update && sudo apt-get install -y ffmpeg`,
which ran in three jobs. It turned out to be redundant in all three:
:func:`termproof.evidence.find_ffmpeg` prefers an ffmpeg on ``PATH`` and falls
back to ``imageio_ffmpeg.get_ffmpeg_exe()``, and ``imageio-ffmpeg`` is a hard
runtime dependency whose Linux wheel carries the binary. `uv sync` therefore
already put a working ffmpeg on every one of those runners, and the apt step
bought nothing but exposure to a mirror.

Deleting the step is only safe while the fallback stays real, so this holds the
two halves of that argument in place: the dependency stays declared, and the
workflows stay off the mirror. Whether the resolved binary actually runs is
checked on the runner itself, by the `Confirm ffmpeg resolves without a package
mirror` step in the jobs that render video.
"""

from __future__ import annotations

import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
PYPROJECT = ROOT / "pyproject.toml"
WORKFLOWS = REPO_ROOT / ".github" / "workflows"


class FfmpegComesFromTheDependencyTest(unittest.TestCase):
    def test_imageio_ffmpeg_is_a_hard_runtime_dependency(self) -> None:
        """Not an extra and not a dev dependency — the fallback must always be there."""
        data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
        dependencies = data["project"]["dependencies"]
        self.assertTrue(
            any(dep.split(">=")[0].split("[")[0].strip() == "imageio-ffmpeg" for dep in dependencies),
            f"imageio-ffmpeg must stay in project.dependencies (#183); got {dependencies}",
        )

    def test_find_ffmpeg_falls_back_to_the_bundled_binary(self) -> None:
        """The PATH lookup is a preference; the dependency is the guarantee."""
        import inspect

        from termproof.evidence import find_ffmpeg

        source = inspect.getsource(find_ffmpeg)
        self.assertIn("shutil.which", source)
        self.assertIn("imageio_ffmpeg", source)

    def test_the_resolved_ffmpeg_exists_on_this_machine(self) -> None:
        from termproof.evidence import find_ffmpeg

        self.assertTrue(Path(find_ffmpeg()).is_file())


class WorkflowsStayOffTheMirrorTest(unittest.TestCase):
    def test_no_workflow_installs_ffmpeg_from_a_package_mirror(self) -> None:
        offenders = []
        for path in sorted(WORKFLOWS.glob("*.yml")):
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if "apt-get" in stripped:
                    offenders.append(f"{path.name}:{number}: {stripped}")
        self.assertEqual(
            [],
            offenders,
            "ffmpeg comes from imageio-ffmpeg; an apt install puts a mirror back on "
            "the critical path (#183)",
        )


if __name__ == "__main__":
    unittest.main()
