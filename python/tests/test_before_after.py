"""What `before_after` reports, and in what words and what order.

The three things pinned here — the delta field names, both markdown forms and
the ordering rule — are the three the Python module and ``termproof::before_after``
disagreed on until #204. They are asserted literally rather than by substring
so that a change to either side has to be a deliberate one: this is a report a
human reviewer reads and a consumer's published output.
"""

from __future__ import annotations

import unittest

from termproof.before_after import (
    FAIL,
    PASS,
    SKIP,
    BehaviorDelta,
    build_before_after,
    compute_deltas,
)
from termproof.models import RunResult


class BehaviorDeltaFieldsTest(unittest.TestCase):
    """The field names, which are what make the two modules swappable."""

    def test_a_delta_names_the_recipe_renderer_and_both_outcomes(self) -> None:
        delta = compute_deltas([_run("login", "default", True)], [_run("login", "default", False)])[0]
        self.assertEqual("login", delta.recipe)
        self.assertEqual("default", delta.renderer)
        self.assertEqual(PASS, delta.before_outcome)
        self.assertEqual(FAIL, delta.after_outcome)

    def test_explanation_is_one_line_a_reviewer_can_read_without_context(self) -> None:
        delta = BehaviorDelta("login", "default", PASS, FAIL)
        self.assertEqual("login [default]: PASS -> FAIL", delta.explanation())


class DeltaDetectionTest(unittest.TestCase):
    def test_identical_runs_have_no_deltas(self) -> None:
        runs = [_run("login", "default", True)]
        self.assertEqual([], compute_deltas(runs, runs))

    def test_a_regression_is_reported(self) -> None:
        deltas = compute_deltas([_run("login", "default", True)], [_run("login", "default", False)])
        self.assertEqual(["login [default]: PASS -> FAIL"], [d.explanation() for d in deltas])

    def test_a_fix_is_reported_too(self) -> None:
        # Not only regressions: a change that fixes something is a behavioural
        # delta a reviewer wants to see confirmed.
        deltas = compute_deltas([_run("login", "default", False)], [_run("login", "default", True)])
        self.assertEqual(["login [default]: FAIL -> PASS"], [d.explanation() for d in deltas])

    def test_the_same_recipe_under_two_renderers_is_two_entries(self) -> None:
        deltas = compute_deltas(
            [_run("login", "alpha", True), _run("login", "beta", True)],
            [_run("login", "alpha", True), _run("login", "beta", False)],
        )
        self.assertEqual(1, len(deltas))
        self.assertEqual("beta", deltas[0].renderer)

    def test_a_recipe_that_stopped_running_is_a_delta_not_a_gap(self) -> None:
        # Silently dropping it would make a shrinking suite look stable.
        deltas = compute_deltas([_run("login", "default", True)], [])
        self.assertEqual(["login [default]: PASS -> SKIP"], [d.explanation() for d in deltas])
        self.assertEqual(SKIP, deltas[0].after_outcome)

    def test_a_newly_added_recipe_is_reported(self) -> None:
        deltas = compute_deltas([], [_run("login", "default", True)])
        self.assertEqual(["login [default]: SKIP -> PASS"], [d.explanation() for d in deltas])


class OrderingTest(unittest.TestCase):
    """The rule a later cosmetic refactor is most likely to undo.

    A ``sorted()`` over the key union looks tidier and passes every other test
    in this file. It is wrong: a reviewer wants the deltas in the order the
    recipes ran, and a report that reshuffles between runs is hard to read and
    harder to diff.
    """

    def test_ordering_follows_before_then_new_arrivals(self) -> None:
        deltas = compute_deltas(
            [_run("b", "d", True), _run("a", "d", True)],
            [_run("a", "d", False), _run("b", "d", False), _run("c", "d", True)],
        )
        self.assertEqual(["b", "a", "c"], [d.recipe for d in deltas])

    def test_before_order_is_kept_even_when_it_is_not_sorted(self) -> None:
        # Every name here is out of alphabetical order in `before`, so a sort
        # anywhere in the pipeline reverses the list rather than leaving it be.
        deltas = compute_deltas(
            [_run(name, "d", True) for name in ("zulu", "yankee", "xray")],
            [_run(name, "d", False) for name in ("xray", "yankee", "zulu")],
        )
        self.assertEqual(["zulu", "yankee", "xray"], [d.recipe for d in deltas])

    def test_new_arrivals_keep_their_after_order_rather_than_being_sorted(self) -> None:
        deltas = compute_deltas([], [_run("zulu", "d", True), _run("alpha", "d", True)])
        self.assertEqual(["zulu", "alpha"], [d.recipe for d in deltas])


class MarkdownTest(unittest.TestCase):
    """Both forms, byte for byte: this is published report text."""

    def test_no_deltas_says_so_rather_than_rendering_nothing(self) -> None:
        # An empty section and a missing section look the same in a report, and
        # only one of them means the comparison ran.
        result = build_before_after([_run("login", "default", True)], [_run("login", "default", True)])
        self.assertEqual(
            "**Behavioral deltas:** none — before/after outcomes match.\n",
            result.to_markdown(),
        )

    def test_markdown_lists_every_delta_in_order(self) -> None:
        result = build_before_after(
            [_run("b", "d", True), _run("a", "d", True)],
            [_run("a", "d", False), _run("b", "d", False)],
        )
        self.assertEqual(
            "**Behavioral deltas:**\n\n- b [d]: PASS -> FAIL\n- a [d]: PASS -> FAIL\n",
            result.to_markdown(),
        )


class BuildBeforeAfterTest(unittest.TestCase):
    def test_build_keeps_both_sides_alongside_the_deltas(self) -> None:
        result = build_before_after([_run("a", "d", True)], [_run("a", "d", False)])
        self.assertEqual(1, len(result.before))
        self.assertEqual(1, len(result.after))
        self.assertEqual(1, len(result.deltas))


def _run(recipe: str, renderer: str, passed: bool) -> RunResult:
    return RunResult(
        recipe_name=recipe,
        passed=passed,
        exit_code=0 if passed else 1,
        duration_seconds=0.0,
        priority="P0",
        execution="scripted",
        renderer=renderer,
        score=1.0 if passed else 0.0,
        steps=[],
        assertions=[],
        artifacts={},
    )


if __name__ == "__main__":
    unittest.main()
