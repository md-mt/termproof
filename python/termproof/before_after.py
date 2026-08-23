"""What changed between two runs of the same suite.

Where :mod:`termproof.parity` asks "do these two agree?", this asks the
narrower and more actionable question: **which outcomes flipped?**

The usual shape is a change under review verified twice — once against a
baseline build, once against the candidate — so a reviewer sees exactly which
behaviours the change altered rather than a wall of results they have to diff
by eye.

A recipe present in only one pass is reported as ``SKIP`` on the missing side.
That is a real signal, not a gap to hide: a recipe that stopped running is
usually more interesting than one that changed verdict, and silently omitting
it would make a shrinking suite look like a stable one.

This module is the mirror of ``termproof::before_after`` in the Rust crate:
the field names, the two markdown forms and the ordering rule are the same on
both sides, because a consumer running a validator in each language reads one
report format, not two.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import RunResult

#: The run passed.
PASS = "PASS"
#: The run failed.
FAIL = "FAIL"
#: The recipe did not run on this side.
SKIP = "SKIP"


@dataclass(frozen=True)
class BehaviorDelta:
    """One recipe/renderer whose outcome changed."""

    #: Recipe name.
    recipe: str
    #: Renderer the recipe ran under.
    renderer: str
    #: :data:`PASS`, :data:`FAIL` or :data:`SKIP` before.
    before_outcome: str
    #: :data:`PASS`, :data:`FAIL` or :data:`SKIP` after.
    after_outcome: str

    def explanation(self) -> str:
        """One line a reviewer can read without context."""
        return f"{self.recipe} [{self.renderer}]: {self.before_outcome} -> {self.after_outcome}"


@dataclass(frozen=True)
class BeforeAfterResult:
    """Two runs and what changed between them."""

    before: list[RunResult]
    after: list[RunResult]
    #: Outcomes that differ, in ``before`` order then new arrivals.
    deltas: list[BehaviorDelta]

    def to_markdown(self) -> str:
        """Render the deltas as markdown.

        States "none" explicitly rather than emitting nothing: an empty section
        and a missing section look identical in a report, and only one of them
        means the comparison ran.
        """
        if not self.deltas:
            return "**Behavioral deltas:** none — before/after outcomes match.\n"
        lines = ["**Behavioral deltas:**", ""]
        for delta in self.deltas:
            lines.append(f"- {delta.explanation()}")
        return "\n".join(lines) + "\n"


def build_before_after(
    before: list[RunResult],
    after: list[RunResult],
) -> BeforeAfterResult:
    """Assemble a :class:`BeforeAfterResult` with its deltas computed."""
    return BeforeAfterResult(before=before, after=after, deltas=compute_deltas(before, after))


def compute_deltas(
    before: list[RunResult],
    after: list[RunResult],
) -> list[BehaviorDelta]:
    """The outcome changes from *before* to *after*.

    Matched by ``(recipe_name, renderer)``. Ordering follows *before*, with
    recipes that appear only in *after* appended — so a report reads in a
    stable order rather than a hash order. Sorting the key union instead would
    read alphabetically, which is not the order the recipes ran in and is not
    the order the two reports either side of a change can be diffed in.
    """
    before_keys = [_key(result) for result in before]
    after_keys = [_key(result) for result in after]

    ordered_keys = list(before_keys)
    for key in after_keys:
        if key not in before_keys:
            ordered_keys.append(key)

    before_by_key = {_key(result): result for result in before}
    after_by_key = {_key(result): result for result in after}
    deltas: list[BehaviorDelta] = []
    for key in ordered_keys:
        before_outcome = _outcome(before_by_key.get(key))
        after_outcome = _outcome(after_by_key.get(key))
        if before_outcome != after_outcome:
            recipe, renderer = key
            deltas.append(BehaviorDelta(recipe, renderer, before_outcome, after_outcome))
    return deltas


def _key(result: RunResult) -> tuple[str, str]:
    return (result.recipe_name, result.renderer)


def _outcome(result: RunResult | None) -> str:
    if result is None:
        return SKIP
    return PASS if result.passed else FAIL
