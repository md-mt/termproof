"""Contract tests for ``.github/dependabot.yml``.

The consumer of this file is Dependabot, which we cannot run locally, so the
tests parse the config into a semantic model and replay Dependabot's documented
grouping rules over it: every pending update is matched against the declared
groups (first match wins, wildcard patterns, ``update-types`` filter), grouped
updates collapse into one pull request per group, and anything left ungrouped
gets a pull request of its own.

What is pinned here is the *stream shape* each ecosystem produces:

* ``github-actions`` batches every action bump -- patch, minor and major --
  into a single pull request, so the six-PR first sweep cannot recur.
* ``pip`` stays deliberately ungrouped: one pull request per dependency. The
  asymmetry between the two ecosystems is intentional.

Run: uv run python -m unittest tests.test_dependabot_config -v
"""

from __future__ import annotations

import fnmatch
import unittest
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DEPENDABOT_YML = ROOT / ".github" / "dependabot.yml"
WORKFLOW_DIR = ROOT / ".github" / "workflows"

UPDATE_TYPES = ("patch", "minor", "major")


@dataclass(frozen=True)
class Update:
    """A single pending dependency bump Dependabot has detected."""

    dependency: str
    update_type: str


@dataclass
class PullRequest:
    """A pull request Dependabot would open for one ecosystem entry."""

    group: str | None
    updates: list[Update] = field(default_factory=list)

    @property
    def title(self) -> str:
        if self.group is not None:
            return f"bump the {self.group} group with {len(self.updates)} updates"
        only = self.updates[0]
        return f"bump {only.dependency}"


def load_config() -> dict:
    with DEPENDABOT_YML.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def entry_for(config: dict, ecosystem: str) -> dict:
    matches = [e for e in config["updates"] if e["package-ecosystem"] == ecosystem]
    if len(matches) != 1:
        raise AssertionError(f"expected exactly one {ecosystem!r} entry, found {len(matches)}")
    return matches[0]


def _matches_group(group: dict, update: Update) -> bool:
    """Replay Dependabot's group matching for one pending update."""
    patterns = group.get("patterns") or ["*"]
    if not any(fnmatch.fnmatch(update.dependency, pattern) for pattern in patterns):
        return False
    excludes = group.get("exclude-patterns") or []
    if any(fnmatch.fnmatch(update.dependency, pattern) for pattern in excludes):
        return False
    update_types = group.get("update-types")
    return update_types is None or update.update_type in update_types


def _is_ignored(entry: dict, update: Update) -> bool:
    for rule in entry.get("ignore") or []:
        if fnmatch.fnmatch(update.dependency, rule.get("dependency-name", "*")):
            return True
    return False


def plan_pull_requests(entry: dict, updates: list[Update]) -> list[PullRequest]:
    """Return the pull requests Dependabot would open for ``updates``.

    Grouped updates collapse into one pull request per group (declaration
    order, first match wins); ungrouped updates each get their own.
    """
    groups: dict[str, dict] = entry.get("groups") or {}
    grouped: dict[str, PullRequest] = {}
    solo: list[PullRequest] = []

    for update in updates:
        if _is_ignored(entry, update):
            continue
        for name, group in groups.items():
            if _matches_group(group, update):
                grouped.setdefault(name, PullRequest(group=name)).updates.append(update)
                break
        else:
            solo.append(PullRequest(group=None, updates=[update]))

    return list(grouped.values()) + solo


def workflow_actions() -> list[str]:
    """Every action referenced by ``uses:`` across the shipped workflows."""
    names: set[str] = set()
    for path in sorted(WORKFLOW_DIR.glob("*.yml")):
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        for job in (workflow.get("jobs") or {}).values():
            for step in job.get("steps") or []:
                uses = step.get("uses")
                if uses and not uses.startswith("./"):
                    names.add(uses.split("@", 1)[0])
    return sorted(names)


class GitHubActionsStreamTest(unittest.TestCase):
    """The actions stream must arrive as exactly one pull request."""

    def setUp(self) -> None:
        self.entry = entry_for(load_config(), "github-actions")

    def test_every_action_in_the_repo_lands_in_one_pull_request(self) -> None:
        """The real first sweep opened six PRs; the same bumps must now open one."""
        actions = workflow_actions()
        self.assertGreaterEqual(len(actions), 6, "expected the workflows to reference several actions")
        # Cycle the update types so patch, minor and major are all represented.
        updates = [
            Update(name, UPDATE_TYPES[index % len(UPDATE_TYPES)])
            for index, name in enumerate(actions)
        ]

        plan = plan_pull_requests(self.entry, updates)

        self.assertEqual(len(plan), 1, f"expected one pull request, got {[pr.title for pr in plan]}")
        self.assertIsNotNone(plan[0].group, "the single pull request must be a grouped one")
        self.assertEqual(
            sorted(u.dependency for u in plan[0].updates),
            actions,
            "every action bump must be batched into the group",
        )

    def test_the_six_pr_sweep_collapses_to_one(self) -> None:
        """The concrete bumps from the ungrouped sweep (#151-#155) batch together."""
        sweep = [
            Update("actions/upload-artifact", "major"),
            Update("actions/setup-python", "major"),
            Update("docker/build-push-action", "major"),
            Update("actions/checkout", "minor"),
            Update("astral-sh/setup-uv", "minor"),
            Update("actions/cache", "patch"),
        ]

        plan = plan_pull_requests(self.entry, sweep)

        self.assertEqual([pr.title for pr in plan], ["bump the github-actions group with 6 updates"])

    def test_no_update_type_escapes_the_group(self) -> None:
        for update_type in UPDATE_TYPES:
            with self.subTest(update_type=update_type):
                plan = plan_pull_requests(self.entry, [Update("some-org/some-action", update_type)])
                self.assertEqual(len(plan), 1)
                self.assertIsNotNone(
                    plan[0].group,
                    f"a {update_type} bump must be grouped, not opened on its own",
                )

    def test_no_bump_is_silently_dropped(self) -> None:
        """Grouping must batch the stream, not suppress parts of it."""
        updates = [Update(name, "major") for name in workflow_actions()]

        planned = [u for pr in plan_pull_requests(self.entry, updates) for u in pr.updates]

        self.assertCountEqual(planned, updates, "no action bump may be filtered out of the stream")

    def test_plan_fits_within_the_open_pull_request_limit(self) -> None:
        limit = self.entry["open-pull-requests-limit"]
        self.assertLessEqual(limit, 10, "the open-pull-requests-limit must not be raised")

        updates = [Update(name, "major") for name in workflow_actions()]

        self.assertLessEqual(len(plan_pull_requests(self.entry, updates)), limit)

    def test_stream_stays_enabled_and_weekly(self) -> None:
        self.assertEqual(self.entry["schedule"]["interval"], "weekly")
        self.assertNotEqual(self.entry.get("open-pull-requests-limit"), 0, "the stream must not be disabled")


class PipStreamTest(unittest.TestCase):
    """pip is deliberately left ungrouped -- one pull request per dependency."""

    def setUp(self) -> None:
        self.entry = entry_for(load_config(), "pip")

    def test_each_dependency_still_gets_its_own_pull_request(self) -> None:
        updates = [
            Update("pyyaml", "minor"),
            Update("jsonschema", "patch"),
            Update("ruff", "major"),
        ]

        plan = plan_pull_requests(self.entry, updates)

        self.assertEqual(len(plan), 3, "grouping pip is a separate judgement; it must stay ungrouped")
        self.assertEqual([pr.group for pr in plan], [None, None, None])

    def test_limit_is_untouched(self) -> None:
        self.assertEqual(self.entry["open-pull-requests-limit"], 10)


if __name__ == "__main__":
    unittest.main()
