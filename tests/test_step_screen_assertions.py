from __future__ import annotations

import sys
import tempfile
import textwrap
import types
import unittest
from dataclasses import replace
from pathlib import Path
from typing import Any

from termproof.builtin_assertions import StepScreenContains
from termproof.config import VerifierConfig
from termproof.models import AssertionResult, CommandSpec, Recipe, StepResult
from termproof.runner import VerificationRunner


def _recipe(**overrides: Any) -> Recipe:
    defaults: dict[str, Any] = {
        "name": "r",
        "command": CommandSpec(argv=["echo", "hi"]),
    }
    return Recipe(**{**defaults, **overrides})


def _steps(*pairs: tuple[str, str]) -> list[StepResult]:
    return [StepResult(name, True, "", screen) for name, screen in pairs]


class LegacyAssertion:
    """An assertion written against the 0.2.1 signature, verbatim.

    The point of this fixture is that it is never updated. Every test that
    exercises it is a test that a plugin published before per-step screens
    existed still runs, unmodified, on the current runner.
    """

    name = "legacy_probe"

    def evaluate(
        self,
        recipe: Recipe,
        assertion: dict[str, Any],
        screen: str,
        raw_output: str,
        exit_code: int | None,
    ) -> AssertionResult:
        return AssertionResult(
            assertion.get("name", self.name), True, f"saw final screen {screen!r}"
        )


class ForwardingAssertion:
    """A wrapper that forwards whatever it is handed to a legacy assertion.

    ``**kwargs`` is deliberately not treated as opting in: if the runner passed
    ``steps`` here, the forwarded call to ``LegacyAssertion.evaluate`` would
    raise ``TypeError``.
    """

    name = "forwarding_probe"

    def __init__(self) -> None:
        self.inner = LegacyAssertion()

    def evaluate(self, *args: Any, **kwargs: Any) -> AssertionResult:
        return self.inner.evaluate(*args, **kwargs)


class StepAwareAssertion:
    """An assertion that opts into per-step screens by declaring ``steps``."""

    name = "step_aware_probe"

    def evaluate(
        self,
        recipe: Recipe,
        assertion: dict[str, Any],
        screen: str,
        raw_output: str,
        exit_code: int | None,
        *,
        steps: list[StepResult] | None = None,
    ) -> AssertionResult:
        names = "none" if steps is None else ",".join(step.name for step in steps)
        return AssertionResult(assertion.get("name", self.name), True, names)


def _config_with(**assertions: type) -> tuple[VerifierConfig, str]:
    module = types.ModuleType("termproof_step_screen_fixture")
    for attribute, member in assertions.items():
        setattr(module, attribute, member)
    sys.modules[module.__name__] = module
    config = VerifierConfig.builtin()
    mapping = dict(config.assertions)
    for attribute, member in assertions.items():
        mapping[member.name] = f"{module.__name__}:{attribute}"
    return replace(config, assertions=mapping), module.__name__


class StepScreenContainsTest(unittest.TestCase):
    def test_reads_the_screen_of_the_named_step(self) -> None:
        result = StepScreenContains().evaluate(
            _recipe(),
            {"type": "step_screen_contains", "step": "open", "value": "palette"},
            "final screen",
            "",
            0,
            steps=_steps(("open", "the palette is open"), ("close", "final screen")),
        )
        self.assertTrue(result.passed)

    def test_fails_when_the_named_step_screen_lacks_the_value(self) -> None:
        result = StepScreenContains().evaluate(
            _recipe(),
            {"type": "step_screen_contains", "step": "close", "value": "palette"},
            "final screen",
            "",
            0,
            steps=_steps(("open", "the palette is open"), ("close", "final screen")),
        )
        self.assertFalse(result.passed)
        self.assertEqual("screen after 'close' contains 'palette'", result.detail)

    def test_matches_the_first_step_sharing_a_name(self) -> None:
        """Duplicate step names resolve to the first, as the recipe format says."""
        steps = _steps(("retry", "first attempt"), ("retry", "second attempt"))
        first = StepScreenContains().evaluate(
            _recipe(),
            {"type": "step_screen_contains", "step": "retry", "value": "first"},
            "final screen",
            "",
            0,
            steps=steps,
        )
        last = StepScreenContains().evaluate(
            _recipe(),
            {"type": "step_screen_contains", "step": "retry", "value": "second"},
            "final screen",
            "",
            0,
            steps=steps,
        )
        self.assertTrue(first.passed)
        self.assertFalse(last.passed)

    def test_reports_the_steps_that_ran_when_the_name_does_not_match(self) -> None:
        result = StepScreenContains().evaluate(
            _recipe(),
            {"type": "step_screen_contains", "step": "typo", "value": "palette"},
            "final screen",
            "",
            0,
            steps=_steps(("open", "the palette is open")),
        )
        self.assertFalse(result.passed)
        self.assertIn("no step named 'typo'", result.detail)
        self.assertIn("'open'", result.detail)

    def test_reports_when_per_step_screens_were_not_supplied(self) -> None:
        result = StepScreenContains().evaluate(
            _recipe(),
            {"type": "step_screen_contains", "step": "open", "value": "palette"},
            "final screen",
            "",
            0,
        )
        self.assertFalse(result.passed)
        self.assertIn("not supplied", result.detail)

    def test_custom_name_is_used_for_the_result(self) -> None:
        result = StepScreenContains().evaluate(
            _recipe(),
            {
                "type": "step_screen_contains",
                "name": "palette opened",
                "step": "open",
                "value": "palette",
            },
            "",
            "",
            0,
            steps=_steps(("open", "the palette is open")),
        )
        self.assertEqual("palette opened", result.name)

    def test_registered_as_a_builtin(self) -> None:
        runner = VerificationRunner()
        self.assertIn("step_screen_contains", runner.assertion_registry.names())


class EvaluateAssertionsDispatchTest(unittest.TestCase):
    """Which assertions the runner hands ``steps`` to, and which it does not."""

    def _runner(self, **assertions: type) -> VerificationRunner:
        config, module_name = _config_with(**assertions)
        self.addCleanup(sys.modules.pop, module_name, None)
        return VerificationRunner(config=config)

    def test_legacy_assertion_is_called_with_the_original_signature(self) -> None:
        runner = self._runner(LegacyAssertion=LegacyAssertion)
        results = runner.evaluate_assertions(
            _recipe(assertions=[{"type": "legacy_probe"}], expect_exit_code=None),
            "final",
            "",
            0,
            steps=_steps(("open", "mid")),
        )
        self.assertEqual(["saw final screen 'final'"], [r.detail for r in results])

    def test_forwarding_assertion_does_not_receive_steps(self) -> None:
        runner = self._runner(ForwardingAssertion=ForwardingAssertion)
        results = runner.evaluate_assertions(
            _recipe(assertions=[{"type": "forwarding_probe"}], expect_exit_code=None),
            "final",
            "",
            0,
            steps=_steps(("open", "mid")),
        )
        self.assertEqual(["saw final screen 'final'"], [r.detail for r in results])

    def test_step_aware_assertion_receives_steps(self) -> None:
        runner = self._runner(StepAwareAssertion=StepAwareAssertion)
        results = runner.evaluate_assertions(
            _recipe(assertions=[{"type": "step_aware_probe"}], expect_exit_code=None),
            "final",
            "",
            0,
            steps=_steps(("open", "mid"), ("close", "final")),
        )
        self.assertEqual(["open,close"], [r.detail for r in results])

    def test_caller_that_omits_steps_yields_none(self) -> None:
        """An execution mode written against 0.2.1 calls with four arguments."""
        runner = self._runner(StepAwareAssertion=StepAwareAssertion)
        results = runner.evaluate_assertions(
            _recipe(assertions=[{"type": "step_aware_probe"}], expect_exit_code=None),
            "final",
            "",
            0,
        )
        self.assertEqual(["none"], [r.detail for r in results])

    def test_deprecated_private_alias_threads_steps(self) -> None:
        runner = self._runner(StepAwareAssertion=StepAwareAssertion)
        results = runner._evaluate_assertions(
            _recipe(assertions=[{"type": "step_aware_probe"}], expect_exit_code=None),
            "final",
            "",
            0,
            steps=_steps(("open", "mid")),
        )
        self.assertEqual(["open"], [r.detail for r in results])


# A target that shows one screen, then clears it and shows another, so the
# intermediate state is genuinely absent from the final screen.
_TWO_SCREENS = textwrap.dedent(
    """
    import sys, time
    sys.stdout.write("PALETTE OPEN\\n")
    sys.stdout.flush()
    time.sleep(0.4)
    sys.stdout.write("\\x1b[2J\\x1b[HSAVED\\n")
    sys.stdout.flush()
    time.sleep(0.4)
    """
)


class StepScreenEndToEndTest(unittest.TestCase):
    """The wiring, exercised through a real run rather than a direct call."""

    def _recipe(self, assertions: list[dict[str, Any]]) -> Recipe:
        return Recipe(
            name="two-screens",
            command=CommandSpec(argv=[sys.executable, "-c", _TWO_SCREENS]),
            steps=[
                {
                    "name": "open palette",
                    "action": "wait_for_text",
                    "text": "PALETTE OPEN",
                    "timeout_seconds": 5,
                },
                {
                    "name": "save",
                    "action": "wait_for_text",
                    "text": "SAVED",
                    "timeout_seconds": 5,
                },
            ],
            assertions=assertions,
            expect_exit_code=None,
        )

    def _run(self, assertions: list[dict[str, Any]]) -> dict[str, bool]:
        with tempfile.TemporaryDirectory() as tmp:
            result = VerificationRunner().run(
                self._recipe(assertions), Path(tmp), render_video=False
            )
        return {assertion.name: assertion.passed for assertion in result.assertions}

    def test_intermediate_screen_is_assertable_and_the_final_one_is_not(self) -> None:
        outcome = self._run(
            [
                {
                    "type": "step_screen_contains",
                    "name": "palette was open",
                    "step": "open palette",
                    "value": "PALETTE OPEN",
                },
                {
                    "type": "screen_contains",
                    "name": "final screen still shows the palette",
                    "value": "PALETTE OPEN",
                },
                {
                    "type": "screen_contains",
                    "name": "final screen shows the save",
                    "value": "SAVED",
                },
            ]
        )
        self.assertTrue(outcome["palette was open"])
        self.assertFalse(outcome["final screen still shows the palette"])
        self.assertTrue(outcome["final screen shows the save"])

    def test_process_mode_also_supplies_step_screens(self) -> None:
        recipe = replace(
            self._recipe(
                [
                    {
                        "type": "step_screen_contains",
                        "name": "palette was open",
                        "step": "open palette",
                        "value": "PALETTE OPEN",
                    }
                ]
            ),
            command=CommandSpec(argv=[sys.executable, "-c", _TWO_SCREENS], pty=False),
        )
        with tempfile.TemporaryDirectory() as tmp:
            result = VerificationRunner().run(recipe, Path(tmp), render_video=False)
        outcome = {a.name: a.passed for a in result.assertions}
        self.assertTrue(outcome["palette was open"])


if __name__ == "__main__":
    unittest.main()
