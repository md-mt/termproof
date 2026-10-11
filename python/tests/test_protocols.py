from __future__ import annotations

import importlib.util
import inspect
import unittest
from pathlib import Path

import termproof
from termproof import protocols


class ProtocolApiTests(unittest.TestCase):
    def test_public_protocol_exports_are_stable(self) -> None:
        self.assertEqual(
            [
                "AgentRunner",
                "ArtifactPublisher",
                "AssertionType",
                "EvidenceConfig",
                "ExecutionMode",
                "PngRenderConfig",
                "PublishedArtifact",
                "PublishTarget",
                "Reporter",
                "ScreenRenderer",
                "SessionBackend",
                "StepAction",
                "StepAwareAssertionType",
                "SvgRenderConfig",
                "VideoBackend",
                "VideoConfig",
            ],
            protocols.__all__,
        )
        for name in protocols.__all__:
            self.assertIs(getattr(termproof, name), getattr(protocols, name))

    def test_protocol_signatures_are_locked(self) -> None:
        cases = {
            protocols.StepAction.execute: (
                ["self", "session", "step", "index"],
                "StepResult",
            ),
            protocols.AssertionType.evaluate: (
                ["self", "recipe", "assertion", "screen", "raw_output", "exit_code"],
                "AssertionResult",
            ),
            protocols.StepAwareAssertionType.evaluate: (
                [
                    "self",
                    "recipe",
                    "assertion",
                    "screen",
                    "raw_output",
                    "exit_code",
                    "steps",
                ],
                "AssertionResult",
            ),
            protocols.ExecutionMode.execute: (
                ["self", "runner", "recipe", "run_dir"],
                "tuple[list[StepResult], list[AssertionResult], str, int | None, str]",
            ),
            protocols.Reporter.generate: (
                ["self", "results", "build_info", "before_after"],
                "str",
            ),
            protocols.ScreenRenderer.render: (
                ["self", "text", "output_path", "cols", "rows"],
                "None",
            ),
            protocols.VideoBackend.render: (
                ["self", "cast_path", "output_path", "fps"],
                "None",
            ),
            protocols.AgentRunner.run: (
                ["self", "recipe", "prompt", "run_dir"],
                "AgentOutcome",
            ),
            protocols.SessionBackend.create_session: (
                ["self", "argv", "cast_path", "cwd", "env", "cols", "rows"],
                "TerminalSession",
            ),
            protocols.ArtifactPublisher.publish: (
                ["self", "source", "key"],
                "PublishedArtifact",
            ),
        }
        for method, (parameters, return_annotation) in cases.items():
            signature = inspect.signature(method)
            self.assertEqual(parameters, list(signature.parameters))
            self.assertEqual(return_annotation, signature.return_annotation)

    def test_step_aware_assertions_extend_the_assertion_protocol_additively(self) -> None:
        """``steps`` must be optional, and only on the extended protocol.

        An assertion implementing ``StepAwareAssertionType`` also satisfies
        ``AssertionType``, so it keeps working on a TermProof that never passes
        ``steps``; and ``AssertionType`` itself is untouched, so an assertion
        written against it needs no source change.
        """
        steps = inspect.signature(protocols.StepAwareAssertionType.evaluate).parameters[
            "steps"
        ]
        self.assertIs(inspect.Parameter.KEYWORD_ONLY, steps.kind)
        self.assertIsNone(steps.default)
        self.assertNotIn(
            "steps", inspect.signature(protocols.AssertionType.evaluate).parameters
        )

    def test_publish_target_is_one_object_across_its_import_locations(self) -> None:
        """``PublishTarget`` is the ``from_target`` payload, so it lives where
        the docs say protocol types live (#165).

        A third-party publisher types its hook against
        ``termproof.protocols``; the CLI builds the target through
        ``termproof.evidence_publish``. The two locations must name the
        same class or ``isinstance`` reasoning about a target the CLI
        handed over would silently disagree with the plugin's annotation.
        """
        from termproof.evidence_publish import PublishTarget as CliPublishTarget
        from termproof.models import PublishTarget as ModelPublishTarget
        from termproof.protocols import PublishTarget as ProtocolPublishTarget

        self.assertIs(ProtocolPublishTarget, CliPublishTarget)
        self.assertIs(ProtocolPublishTarget, ModelPublishTarget)
        self.assertIs(termproof.PublishTarget, ProtocolPublishTarget)

    def test_plugin_template_publisher_imports_resolve(self) -> None:
        """The shipped template is the worked example of the import policy.

        Its publisher used to reach into ``termproof.evidence_publish``
        for ``PublishTarget`` because no public surface exported it (#165).
        Loading the module proves the ``termproof.protocols`` import it
        now carries resolves against this tree.
        """
        template = (
            Path(__file__).resolve().parents[1]
            / "plugin-template"
            / "src"
            / "termproof_my_plugin"
            / "publishers.py"
        )
        if not template.is_file():
            self.skipTest("plugin template is not part of this checkout")
        self.assertIn(
            "from termproof.protocols import PublishTarget",
            template.read_text(encoding="utf-8"),
        )
        spec = importlib.util.spec_from_file_location(
            "termproof_my_plugin_publishers_under_test", template
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertIs(module.PublishTarget, protocols.PublishTarget)

    def test_legacy_protocol_import_locations_reexport_public_protocols(self) -> None:
        from termproof.agent_driven import AgentRunner
        from termproof.builtin_assertions import AssertionType
        from termproof.builtin_modes import ExecutionMode
        from termproof.builtin_renderers import ScreenRenderer
        from termproof.builtin_reporters import Reporter
        from termproof.builtin_session import SessionBackend
        from termproof.builtin_steps import StepAction
        from termproof.builtin_video import VideoBackend

        self.assertIs(AgentRunner, protocols.AgentRunner)
        self.assertIs(AssertionType, protocols.AssertionType)
        self.assertIs(ExecutionMode, protocols.ExecutionMode)
        self.assertIs(Reporter, protocols.Reporter)
        self.assertIs(ScreenRenderer, protocols.ScreenRenderer)
        self.assertIs(SessionBackend, protocols.SessionBackend)
        self.assertIs(StepAction, protocols.StepAction)
        self.assertIs(VideoBackend, protocols.VideoBackend)


if __name__ == "__main__":
    unittest.main()
