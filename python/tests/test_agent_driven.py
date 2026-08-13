from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from termproof.agent_driven import _load_json, build_agent_prompt, parse_agent_output
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


class LoadJsonTest(unittest.TestCase):
    def test_clean_json_object(self) -> None:
        data = _load_json('{"assertions": {"ok": true}, "transcript": "done"}')

        self.assertEqual({"assertions": {"ok": True}, "transcript": "done"}, data)

    def test_json_wrapped_in_prose(self) -> None:
        output = 'Here is the result: {"assertions": {"ok": true}} thanks!'

        data = _load_json(output)

        self.assertEqual({"assertions": {"ok": True}}, data)

    def test_json_inside_fenced_block(self) -> None:
        output = 'Some notes\n```json\n{"assertions": {"ok": true}, "transcript": "x"}\n```\n'

        data = _load_json(output)

        self.assertEqual({"assertions": {"ok": True}, "transcript": "x"}, data)

    def test_json_on_last_line_after_logs(self) -> None:
        output = "\n".join(
            [
                "starting agent...",
                "[info] running command",
                "[info] finished",
                '{"assertions": {"ok": true}, "transcript": "last"}',
            ]
        )

        data = _load_json(output)

        self.assertEqual({"assertions": {"ok": True}, "transcript": "last"}, data)

    def test_object_with_assertions_wins_over_plain_object(self) -> None:
        # Two JSON-looking fragments: only the one carrying "assertions"/"transcript"
        # should be selected regardless of its position in the output.
        output = "\n".join(
            [
                '{"unrelated": 1}',
                '{"assertions": {"ok": true}}',
                '{"also": 2}',
            ]
        )

        data = _load_json(output)

        self.assertEqual({"assertions": {"ok": True}}, data)

    def test_trailing_text_after_object(self) -> None:
        output = '{"assertions": {"ok": true}} trailing commentary that is not json'

        data = _load_json(output)

        self.assertEqual({"assertions": {"ok": True}}, data)

    def test_falls_back_to_first_object_without_marker_keys(self) -> None:
        # No fragment has "assertions"/"transcript"; the first collected dict wins.
        output = '{"foo": 1}'

        data = _load_json(output)

        self.assertEqual({"foo": 1}, data)

    def test_malformed_json_returns_none(self) -> None:
        self.assertIsNone(_load_json('{"assertions": {"ok": true'))

    def test_no_json_returns_none(self) -> None:
        self.assertIsNone(_load_json("just some plain text, no json here"))

    def test_empty_input_returns_none(self) -> None:
        self.assertIsNone(_load_json(""))

    def test_non_object_json_is_ignored(self) -> None:
        # A top-level JSON array is valid JSON but not a dict, so it is skipped.
        self.assertIsNone(_load_json("[1, 2, 3]"))
