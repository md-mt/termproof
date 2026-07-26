from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from termproof.agent_driven import build_agent_prompt, parse_agent_output
from termproof.models import CommandSpec, Recipe
from termproof.runner import VerificationRunner


class AgentDrivenTest(unittest.TestCase):
    def test_prompt_includes_target_and_checks(self) -> None:
        recipe = Recipe(
            name="pi-agent",
            command=CommandSpec(argv=["pi", "--help"], pty=False),
            checks=["Pi launcher banner renders"],
            execution="agent-driven",
        )

        prompt = build_agent_prompt(recipe)

        self.assertIn("pi --help", prompt)
        self.assertIn("Pi launcher banner renders", prompt)
        self.assertIn("Return JSON only", prompt)

    def test_parse_agent_output_accepts_fenced_json(self) -> None:
        assertions, transcript, metadata = parse_agent_output(
            '```json\n{"assertions":{"ok":true},"transcript":"done","notes":"n"}\n```'
        )

        self.assertEqual({"ok": True}, assertions)
        self.assertEqual("done", transcript)
        self.assertEqual("n", metadata["notes"])

    def test_agent_driven_run_records_operator_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake_operator = Path(tmp) / "fake_codex.py"
            fake_operator.write_text(
                "\n".join(
                    [
                        "import json",
                        "import sys",
                        "prompt = sys.stdin.read()",
                        "print(json.dumps({",
                        "  'assertions': {'Pi launcher banner renders': True},",
                        "  'transcript': 'Pi at Meta\\nMeta Launcher Options\\n' + prompt[:20],",
                        "}))",
                    ]
                ),
                encoding="utf-8",
            )
            recipe = Recipe(
                name="pi-agent",
                command=CommandSpec(argv=["pi", "--help"], pty=False),
                checks=["Pi launcher banner renders"],
                execution="agent-driven",
                operator={
                    "command": [sys.executable, str(fake_operator)],
                    "timeout_seconds": 5,
                },
            )

            result = VerificationRunner().run(recipe, Path(tmp), render_video=False)

            self.assertTrue(result.passed)
            self.assertTrue(Path(result.artifacts["cast"]).exists())
            self.assertTrue(Path(result.artifacts["agent_prompt"]).exists())
            self.assertTrue(Path(result.artifacts["agent_transcript"]).exists())
            self.assertTrue(Path(result.artifacts["agent_outcome"]).exists())
            self.assertTrue(Path(result.artifacts["step_screenshots"]).exists())
