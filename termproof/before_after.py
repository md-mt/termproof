from __future__ import annotations

from dataclasses import dataclass

from .models import RunResult


@dataclass(frozen=True)
class BehaviorDelta:
    recipe_name: str
    renderer: str
    before: str
    after: str


@dataclass(frozen=True)
class BeforeAfterResult:
    before: list[RunResult]
    after: list[RunResult]
    deltas: list[BehaviorDelta]

    def to_markdown(self) -> str:
        if not self.deltas:
            return "## Behavioral Deltas\n\nNone.\n"
        lines = ["## Behavioral Deltas", ""]
        for delta in self.deltas:
            lines.append(
                f"- `{delta.recipe_name}` [{delta.renderer}]: "
                f"{delta.before} -> {delta.after}"
            )
        return "\n".join(lines) + "\n"


def build_before_after(
    before: list[RunResult],
    after: list[RunResult],
) -> BeforeAfterResult:
    return BeforeAfterResult(before=before, after=after, deltas=compute_deltas(before, after))


def compute_deltas(
    before: list[RunResult],
    after: list[RunResult],
) -> list[BehaviorDelta]:
    before_by_key = {_key(result): result for result in before}
    after_by_key = {_key(result): result for result in after}
    deltas: list[BehaviorDelta] = []
    for key in sorted(before_by_key.keys() | after_by_key.keys()):
        before_status = _status(before_by_key.get(key))
        after_status = _status(after_by_key.get(key))
        if before_status != after_status:
            recipe_name, renderer = key
            deltas.append(BehaviorDelta(recipe_name, renderer, before_status, after_status))
    return deltas


def _key(result: RunResult) -> tuple[str, str]:
    return (result.recipe_name, result.renderer)


def _status(result: RunResult | None) -> str:
    if result is None:
        return "SKIP"
    return "PASS" if result.passed else "FAIL"
