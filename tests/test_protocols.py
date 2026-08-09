from __future__ import annotations

import inspect
import unittest

import termproof
from termproof import protocols


class ProtocolApiTests(unittest.TestCase):
    def test_public_protocol_exports_are_stable(self) -> None:
        self.assertEqual(
            [
                "AgentRunner",
                "AssertionType",
                "EvidenceConfig",
                "ExecutionMode",
                "PngRenderConfig",
                "Reporter",
                "ScreenRenderer",
                "SessionBackend",
                "StepAction",
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
        }
        for method, (parameters, return_annotation) in cases.items():
            signature = inspect.signature(method)
            self.assertEqual(parameters, list(signature.parameters))
            self.assertEqual(return_annotation, signature.return_annotation)

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
