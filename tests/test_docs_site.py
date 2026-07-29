from __future__ import annotations

import ast
import json
import re
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DOCS_SITE = ROOT / "docs-site"
CONFIG = DOCS_SITE / ".vitepress" / "config.mts"
WORKFLOW = ROOT / ".github" / "workflows" / "docs-site.yml"
LEGACY_PAGES_WORKFLOW = ROOT / ".github" / "workflows" / "pages.yml"


def _evaluate_github_condition(
    cond: str,
    *,
    event_name: str,
    ref: str = "",
    enable_pages: str = "false",
) -> bool:
    """Evaluate the subset of GitHub Actions ``if`` expressions used by
    docs-site.yml (``==``, ``!=``, ``&&``, ``||``, parentheses) against the
    given inputs.

    Only the three variables the workflow references are supported and string
    literals are inert, so evaluation is safe.
    """
    if not cond or not cond.strip():
        return True
    py = re.sub(r"\s+", " ", cond.strip())
    py = py.replace("!=", "__NE__")
    py = py.replace("&&", " and ").replace("||", " or ")
    py = py.replace("==", " == ")
    py = re.sub(r"!", " not ", py)
    py = py.replace("__NE__", " != ")
    py = py.replace("github.event_name", "event_name")
    py = py.replace("github.ref", "ref")
    py = py.replace("vars.ENABLE_PAGES", "enable_pages")
    tree = ast.parse(py, mode="eval")
    namespace = {"event_name": event_name, "ref": ref, "enable_pages": enable_pages}
    return bool(eval(compile(tree, "<condition>", "eval"), {"__builtins__": {}}, namespace))


class DocsSiteTest(unittest.TestCase):
    def test_vitepress_package_and_sections_exist(self) -> None:
        package = json.loads((DOCS_SITE / "package.json").read_text(encoding="utf-8"))

        self.assertEqual("vitepress build .", package["scripts"]["docs:build"])
        for path in (
            "getting-started.md",
            "install/homebrew.md",
            "guides/index.md",
            "api/index.md",
            "plugins.md",
            "ci/index.md",
            "faq.md",
        ):
            self.assertTrue((DOCS_SITE / path).is_file(), path)

    def test_vitepress_nav_has_expected_structure(self) -> None:
        text = CONFIG.read_text(encoding="utf-8")

        self.assertIn("Getting Started", text)
        self.assertIn("Homebrew", text)
        self.assertIn("Guides", text)
        self.assertIn("API Reference", text)
        self.assertIn("Plugins", text)
        self.assertIn("CI Integration", text)
        self.assertIn("FAQ", text)

    def test_docs_site_workflow_builds_artifact(self) -> None:
        workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
        text = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("pull_request", workflow[True])
        self.assertIn("npm run --prefix docs-site docs:build", text)
        self.assertIn("docs-site/.vitepress/dist", text)


class DocsSiteDeployTest(unittest.TestCase):
    """Acceptance tests for the VitePress Pages deployment remediation (PR #91
    replacement). Each test corresponds to a review finding from the formal
    mw-ding CHANGES_REQUESTED review or the md-mt blocking comment."""

    @staticmethod
    def _workflow() -> dict:
        return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))

    def test_vitepress_base_path_for_github_pages(self) -> None:
        text = CONFIG.read_text(encoding="utf-8")
        self.assertIn('base: "/termproof/"', text)

    def test_docs_site_lockfile_committed(self) -> None:
        lockfile = DOCS_SITE / "package-lock.json"
        self.assertTrue(lockfile.is_file(), "docs-site/package-lock.json must be committed")
        lock = json.loads(lockfile.read_text(encoding="utf-8"))
        self.assertEqual(lock["name"], "docs-site")
        self.assertIn("vitepress", lock.get("packages", {}).get("", {}).get("devDependencies", {}))

    def test_docs_site_workflow_uses_npm_ci(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("npm ci --prefix docs-site", text)
        self.assertNotIn("npm install --prefix docs-site --no-package-lock", text)

    def test_docs_site_workflow_pins_pages_actions(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("uses: actions/configure-pages@v5", text)
        self.assertIn("uses: actions/upload-pages-artifact@v3", text)
        self.assertIn("uses: actions/deploy-pages@v4", text)

    def test_docs_site_workflow_has_deploy_job(self) -> None:
        workflow = self._workflow()
        self.assertIn("deploy", workflow["jobs"])

    def test_docs_site_deploy_gated_on_enable_pages(self) -> None:
        workflow = self._workflow()
        deploy = workflow["jobs"]["deploy"]
        self.assertIn("vars.ENABLE_PAGES", deploy["if"])

    def test_docs_site_deploy_job_least_privilege(self) -> None:
        workflow = self._workflow()
        deploy = workflow["jobs"]["deploy"]
        self.assertEqual(
            {"contents": "read", "pages": "write", "id-token": "write"},
            deploy["permissions"],
            "deploy job must request only contents:read, pages:write, id-token:write",
        )
        self.assertEqual("github-pages", deploy["environment"]["name"])

    def test_docs_site_build_job_stays_pr_safe(self) -> None:
        workflow = self._workflow()
        build = workflow["jobs"]["build"]
        steps = build["steps"]
        upload = next(s for s in steps if "upload-pages-artifact" in s.get("uses", ""))
        self.assertEqual(
            "github.event_name != 'pull_request' && vars.ENABLE_PAGES == 'true'",
            upload["if"],
        )

    def test_docs_site_pages_steps_enumerated_and_gated(self) -> None:
        """Every Pages-specific step (Configure Pages, Upload Pages artifact)
        must be gated on BOTH non-PR events AND ``vars.ENABLE_PAGES == 'true'``
        so a repository with Pages disabled never reaches the Pages API."""
        workflow = self._workflow()
        steps = workflow["jobs"]["build"]["steps"]

        pages_steps = [
            s
            for s in steps
            if "actions/configure-pages@" in s.get("uses", "")
            or "actions/upload-pages-artifact@" in s.get("uses", "")
        ]
        self.assertGreaterEqual(len(pages_steps), 2)
        for step in pages_steps:
            cond = step.get("if", "")
            self.assertIn("github.event_name != 'pull_request'", cond)
            self.assertIn("vars.ENABLE_PAGES == 'true'", cond)

    def test_docs_site_disabled_opt_out_runs_no_pages_steps(self) -> None:
        """Structurally simulate the disabled opt-out path: a main push with
        ``ENABLE_PAGES != 'true'`` must skip every Pages-specific step so the
        build job succeeds and the deploy-skipped notice can run."""
        workflow = self._workflow()
        steps = workflow["jobs"]["build"]["steps"]

        pages_steps = [
            s
            for s in steps
            if "actions/configure-pages@" in s.get("uses", "")
            or "actions/upload-pages-artifact@" in s.get("uses", "")
        ]
        self.assertTrue(pages_steps, "expected Pages-specific steps in build job")
        for step in pages_steps:
            self.assertFalse(
                _evaluate_github_condition(
                    step.get("if", ""),
                    event_name="push",
                    ref="refs/heads/main",
                    enable_pages="false",
                ),
                f"{step.get('name')} must be skipped when ENABLE_PAGES is not 'true'",
            )

        # deploy job must not run and the skipped notice must run.
        self.assertFalse(
            _evaluate_github_condition(
                workflow["jobs"]["deploy"]["if"],
                event_name="push",
                ref="refs/heads/main",
                enable_pages="false",
            )
        )
        self.assertTrue(
            _evaluate_github_condition(
                workflow["jobs"]["deploy-skipped"]["if"],
                event_name="push",
                ref="refs/heads/main",
                enable_pages="false",
            )
        )

    def test_docs_site_enabled_path_still_runs_pages_steps(self) -> None:
        """When Pages is enabled, Configure Pages and Upload Pages artifact run
        on non-PR events and never on pull requests."""
        workflow = self._workflow()
        steps = workflow["jobs"]["build"]["steps"]
        pages_steps = [
            s
            for s in steps
            if "actions/configure-pages@" in s.get("uses", "")
            or "actions/upload-pages-artifact@" in s.get("uses", "")
        ]
        for step in pages_steps:
            self.assertTrue(
                _evaluate_github_condition(
                    step.get("if", ""),
                    event_name="push",
                    ref="refs/heads/main",
                    enable_pages="true",
                ),
                f"{step.get('name')} should run on main push when ENABLE_PAGES is 'true'",
            )
            self.assertFalse(
                _evaluate_github_condition(
                    step.get("if", ""),
                    event_name="pull_request",
                    ref="refs/heads/main",
                    enable_pages="true",
                ),
                f"{step.get('name')} must never run on pull_request",
            )

    def test_docs_site_generic_preview_artifact_stays_unconditional(self) -> None:
        """The generic preview artifact (upload-artifact) must remain available
        even when Pages is disabled or on pull requests."""
        workflow = self._workflow()
        steps = workflow["jobs"]["build"]["steps"]
        preview = next(
            s
            for s in steps
            if "actions/upload-artifact@" in s.get("uses", "")
            and "pages" not in s.get("uses", "")
        )
        self.assertNotIn("if", preview, "generic preview artifact must be unconditional")
        self.assertEqual("termproof-docs-site", preview["with"]["name"])

    def test_docs_site_workflow_yaml_parses(self) -> None:
        workflow = self._workflow()
        self.assertIn("build", workflow["jobs"])
        self.assertIn("pull_request", workflow[True])


class CrossWorkflowPagesDeployerTest(unittest.TestCase):
    """Cross-workflow regression coverage for the dual-deployer Pages race.

    When ENABLE_PAGES=true, exactly one authoritative workflow/deployer may
    target the ``github-pages`` environment for the shared ``docs/**`` and
    ``README.md`` triggers across ``.github/workflows/docs-site.yml`` and
    ``.github/workflows/pages.yml``.  The VitePress ``docs-site.yml`` is the
    authoritative deployer; the legacy ``pages.yml`` is build-validation only
    and must not deploy to Pages.
    """

    @staticmethod
    def _workflows() -> dict[str, dict]:
        return {
            "docs-site.yml": yaml.safe_load(WORKFLOW.read_text(encoding="utf-8")),
            "pages.yml": yaml.safe_load(LEGACY_PAGES_WORKFLOW.read_text(encoding="utf-8")),
        }

    def test_exactly_one_authoritative_enable_pages_deployer(self) -> None:
        """Across both workflows, at most one job may deploy to the
        github-pages environment when ENABLE_PAGES=true.  The single
        authoritative deployer must be docs-site.yml."""
        workflows = self._workflows()
        deployers: list[str] = []
        for workflow_name, workflow in workflows.items():
            for job_name, job in workflow.get("jobs", {}).items():
                environment = job.get("environment")
                if isinstance(environment, dict) and environment.get("name") == "github-pages":
                    deployers.append(f"{workflow_name}:{job_name}")
        self.assertEqual(
            len(deployers),
            1,
            "expected exactly one authoritative github-pages deployer across "
            f"docs-site.yml and pages.yml, found: {deployers}",
        )
        self.assertEqual(
            deployers[0],
            "docs-site.yml:deploy",
            "the authoritative github-pages deployer must be docs-site.yml:deploy",
        )

    def test_authoritative_deployer_gated_on_enable_pages_and_main_push(self) -> None:
        workflows = self._workflows()
        deploy = workflows["docs-site.yml"]["jobs"]["deploy"]
        condition = deploy["if"]
        self.assertIn("vars.ENABLE_PAGES == 'true'", condition)
        self.assertIn("github.event_name == 'push'", condition)
        self.assertIn("github.ref == 'refs/heads/main'", condition)
        self.assertEqual("github-pages", deploy["environment"]["name"])

    def test_legacy_pages_workflow_is_build_validation_only(self) -> None:
        """pages.yml must retain build validation but must not contain a
        deploy job, a Pages artifact upload, or a github-pages environment."""
        workflow = self._workflows()["pages.yml"]
        jobs = workflow["jobs"]
        # Build validation stays.
        self.assertIn("build", jobs)
        text = LEGACY_PAGES_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("Validate relative links", text)
        self.assertIn("Build site preview", text)
        # No deploy job and no Pages environment.
        self.assertNotIn("deploy", jobs)
        self.assertNotIn("actions/deploy-pages@", text)
        self.assertNotIn("actions/upload-pages-artifact@", text)
        self.assertNotIn("name: github-pages", text)

    def test_legacy_pages_workflow_uses_least_privilege_permissions(self) -> None:
        """Without a Pages deployer, pages.yml must not request pages:write or
        id-token:write at workflow scope."""
        workflow = self._workflows()["pages.yml"]
        permissions = workflow.get("permissions", {})
        self.assertEqual(
            {"contents": "read"},
            permissions,
            "pages.yml (build-validation only) must request only contents:read",
        )

    def test_single_concurrency_regime(self) -> None:
        """The authoritative deployer uses one concurrency group; the legacy
        workflow must not share a Pages deploy concurrency group."""
        workflows = self._workflows()
        docs_concurrency = workflows["docs-site.yml"].get("concurrency")
        self.assertIsNotNone(docs_concurrency)
        self.assertIn("group", docs_concurrency)
        pages_text = LEGACY_PAGES_WORKFLOW.read_text(encoding="utf-8")
        # Legacy workflow must not reference the authoritative deploy group.
        self.assertNotIn(docs_concurrency["group"], pages_text)

    def test_shared_triggers_covered_by_authoritative_workflow(self) -> None:
        """Shared docs/** and README.md triggers must be covered by the
        authoritative docs-site.yml push trigger."""
        workflow = self._workflows()["docs-site.yml"]
        push_paths = workflow.get(True, {}).get("push", {}).get("paths", [])
        self.assertIn("docs/**", push_paths)
        self.assertIn("README.md", push_paths)


if __name__ == "__main__":
    unittest.main()
