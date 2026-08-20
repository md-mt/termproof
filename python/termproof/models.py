from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from .attributed import AttributedScreen

RECIPE_VERSION = 1


@dataclass(frozen=True)
class CommandSpec:
    argv: list[str]
    cwd: str | None = None
    env: dict[str, str] = field(default_factory=dict)
    pty: bool = True


@dataclass(frozen=True)
class RecipeMeta:
    """What a recipe says about itself, independent of how it is driven.

    These seven fields answer "which scenario is this, how much does it matter,
    and which sources does it cover" — questions with the same answer whether
    the scenario is a declarative :class:`Recipe` or a host's own imperative
    runner. Only the *driving* half of a recipe is declarative, and only that
    half is out of reach for a suite that branches on what the screen shows.
    The description is not, and used to be reachable only by constructing a
    :class:`Recipe`, which needs a ``command`` such a suite has no single
    honest value for.

    A host builds one of these directly and hands it to
    :func:`termproof.selection.select_names` as ``(meta.name, meta.ci_paths)``,
    or reads one off a :class:`Recipe` through :attr:`Recipe.meta`.

    Product-specific knobs do not belong here; a host's own class beside this
    one is their home.

    ``Recipe`` does **not** inherit from this. It would be the closer mirror of
    the Rust side, where ``Recipe`` embeds ``RecipeMeta`` and flattens it, but
    dataclass inheritance puts base fields first, which would move ``command``
    behind six defaulted fields and force it keyword-only — changing the
    positional signature of ``Recipe``. This package treats that as a break
    worth avoiding (see :class:`StepResult`). The two field lists are held
    together by ``tests/test_recipe_meta.py`` instead.
    """

    name: str
    description: str = ""
    intent: str = ""
    priority: str = "P2"
    execution: str = "scripted"
    determinism: str = "deterministic"
    ci_paths: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Recipe:
    name: str
    command: CommandSpec
    recipe_version: int = 1
    description: str = ""
    intent: str = ""
    priority: str = "P2"
    execution: str = "scripted"
    determinism: str = "deterministic"
    ci_paths: list[str] = field(default_factory=list)
    checks: list[str] = field(default_factory=list)
    operator: dict[str, Any] = field(default_factory=dict)
    renderers: dict[str, list[str]] = field(default_factory=lambda: {"default": []})
    steps: list[dict[str, Any]] = field(default_factory=list)
    assertions: list[dict[str, Any]] = field(default_factory=list)
    expect_exit_code: int | None = 0
    timeout_seconds: float = 30.0
    cols: int = 100
    rows: int = 30
    source_path: str | None = None

    @property
    def meta(self) -> RecipeMeta:
        """This recipe's descriptive half as a :class:`RecipeMeta`.

        A copy, not a view: ``Recipe`` is frozen, and ``ci_paths`` is copied
        rather than aliased so mutating the returned list cannot reach back
        into the recipe. A property rather than a field, so nothing about
        ``Recipe``'s own signature, field order or ``repr`` moves.
        """
        return RecipeMeta(
            name=self.name,
            description=self.description,
            intent=self.intent,
            priority=self.priority,
            execution=self.execution,
            determinism=self.determinism,
            ci_paths=list(self.ci_paths),
        )


@dataclass(frozen=True)
class StepResult:
    """A step's verdict and the screen it left behind.

    ``screen`` is the flattened text. It is what assertions match against, what
    ``steps/NN-name.txt`` holds, and the only form of the screen that
    ``to_dict`` carries.

    ``screen_attributed`` is that same screen as a cell grid, supplied by
    sessions that have one to give. It is what the per-step screenshot is
    rendered from when it is present, which is what puts colour in the image and
    what makes a colour-only change between two steps count as a change for
    screenshot dedup.

    Optional in both directions, deliberately:

    - It defaults to ``None`` and is the last field, so every existing
      construction — ``StepResult(name, passed, detail, screen)``, positional or
      keyword — is unaffected. A ``StepAction`` in a plugin that never sets it
      keeps working and keeps producing monochrome step screenshots.
    - ``to_dict`` does not emit it, so ``result.json`` keeps the shape the Rust
      implementation shares and the run cache reads. A grid per step would be
      orders of magnitude larger than the rest of the file, and nothing
      downstream of the JSON re-renders a screenshot: by the time a result is
      serialised its images are already on disk. A ``StepResult`` rebuilt by
      ``from_dict`` therefore has no grid, which is the honest answer rather
      than a lossy one.
    - It is ``compare=False``, so equality tracks the serialised shape rather
      than diverging from it. Comparing a live result against
      ``RunResult.from_dict(result.to_dict())`` is an ordinary thing for a test
      to do, here and downstream; with the grid in ``__eq__`` that comparison
      would start returning ``False`` for a reason nothing in the JSON explains.
      Two steps with the same verdict, detail and screen text are the same
      result; the grid is evidence the result carries, not part of its identity.
      Excluding it also keeps ``__hash__`` off the grid, which matters because
      hashing one means hashing every cell.
    """

    name: str
    passed: bool
    detail: str
    screen: str
    screen_attributed: AttributedScreen | None = field(default=None, compare=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "detail": self.detail,
            "screen": self.screen,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StepResult:
        return cls(**data)


@dataclass(frozen=True)
class AssertionResult:
    name: str
    passed: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "detail": self.detail,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AssertionResult:
        return cls(**data)


@dataclass(frozen=True)
class PublishedArtifact:
    """The outcome of handing one local evidence file to an artifact store.

    ``source`` is the local path exactly as the caller supplied it, and it is
    the reason this is a result object rather than a bare URL: a report links
    to evidence by local path, so rewriting those links needs the pairing of
    source and URL, not the URL alone.

    ``url`` is empty when the store took the bytes but cannot name a public
    address for them, and ``published`` is false when it did not take them at
    all — a dry run, an unsupported file, or a failure the publisher chose to
    report rather than raise. ``detail`` says which. The two conditions warrant
    different things: a link rewrite needs an artifact that is both published
    and addressable, while a manifest entry needs only that it was published,
    because bytes that were stored but cannot be named still belong in the
    record of what was stored.
    """

    source: Path
    key: str
    url: str = ""
    published: bool = True
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source.as_posix(),
            "key": self.key,
            "url": self.url,
            "published": self.published,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class RunResult:
    """One recipe × one renderer, as a canonical result payload.

    ``score`` is the fraction of assertions that held, in ``0.0..=1.0``.
    **A run that asserted nothing scores 1.0, not 0.0.** That is part of this
    contract rather than a choice each producer makes, because a score is read
    comparatively: a consumer that scored the empty set ``0.0`` would publish
    numbers that look like these and rank against them wrongly. The reading is
    "no assertion failed", which is what an empty set reports; "nothing was
    verified" is carried by ``assertions`` being empty, and a caller that cares
    about it should read that rather than the score.

    :func:`score_from` computes it from a name → passed mapping and
    :func:`score_from_assertions` from an :class:`AssertionResult` list; both
    are the same rule, and neither should be re-derived by a caller.
    """

    recipe_name: str
    passed: bool
    exit_code: int | None
    duration_seconds: float
    priority: str
    execution: str
    renderer: str
    score: float
    steps: list[StepResult]
    assertions: list[AssertionResult]
    artifacts: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "recipe_name": self.recipe_name,
            "passed": self.passed,
            "exit_code": self.exit_code,
            "duration_seconds": self.duration_seconds,
            "priority": self.priority,
            "execution": self.execution,
            "renderer": self.renderer,
            "score": self.score,
            "steps": [step.to_dict() for step in self.steps],
            "assertions": [assertion.to_dict() for assertion in self.assertions],
            "artifacts": self.artifacts,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RunResult:
        return cls(
            recipe_name=data["recipe_name"],
            passed=bool(data["passed"]),
            exit_code=data.get("exit_code"),
            duration_seconds=float(data["duration_seconds"]),
            priority=data["priority"],
            execution=data["execution"],
            renderer=data["renderer"],
            score=float(data["score"]),
            steps=[StepResult.from_dict(step) for step in data.get("steps", [])],
            assertions=[
                AssertionResult.from_dict(assertion)
                for assertion in data.get("assertions", [])
            ],
            artifacts=dict(data.get("artifacts", {})),
        )


def recipe_from_mapping(data: dict[str, Any]) -> Recipe:
    recipe_version = data.get("recipe_version", RECIPE_VERSION)
    if (
        not isinstance(recipe_version, int)
        or isinstance(recipe_version, bool)
        or recipe_version != RECIPE_VERSION
    ):
        raise ValueError(f"unsupported recipe_version: {recipe_version!r}")
    command_data = data["command"]
    command = CommandSpec(
        argv=list(command_data["argv"]),
        cwd=command_data.get("cwd"),
        env=dict(command_data.get("env", {})),
        pty=bool(command_data.get("pty", True)),
    )
    return Recipe(
        name=data["name"],
        recipe_version=recipe_version,
        description=data.get("description", ""),
        intent=data.get("intent", ""),
        command=command,
        priority=data.get("priority", "P2"),
        execution=data.get("execution", "scripted"),
        determinism=data.get("determinism", "deterministic"),
        ci_paths=list(data.get("ci_paths", [])),
        checks=list(data.get("checks", [])),
        operator=dict(data.get("operator", {})),
        renderers=_normalize_renderers(data.get("renderers")),
        steps=list(data.get("steps", [])),
        assertions=list(data.get("assertions", [])),
        expect_exit_code=data.get("expect_exit_code", 0),
        timeout_seconds=float(data.get("timeout_seconds", 30)),
        cols=int(data.get("cols", 100)),
        rows=int(data.get("rows", 30)),
    )


def load_recipe(path: Path) -> Recipe:
    import json

    recipe = recipe_from_mapping(json.loads(path.read_text(encoding="utf-8")))
    return replace(recipe, source_path=str(path))


def score_from(assertions: Mapping[str, bool]) -> float:
    """:attr:`RunResult.score` for a name → passed mapping.

    **An empty mapping scores 1.0.** See :class:`RunResult` for why that is the
    contract and not each caller's decision.

    The mapping's ordering cannot affect the result — only how many values are
    true and how many there are — so a caller that collected its assertions in
    a different order gets the same number. Two entries under one name are one
    entry, which is the difference from :func:`score_from_assertions`: a list
    keeps duplicates and weighs each of them.
    """
    return _score_of(assertions.values())


def assertion_map(pairs: Iterable[tuple[str, bool]]) -> dict[str, bool]:
    """The mapping :func:`score_from` scores, from ``(name, passed)`` pairs.

    The last pair for a name wins, as assigning into the mapping would.
    """
    return {str(name): bool(passed) for name, passed in pairs}


def score_from_assertions(assertions: list[AssertionResult]) -> float:
    """:attr:`RunResult.score` from assertion results (all pass → 1.0, else fraction)."""
    return _score_of(assertion.passed for assertion in assertions)


def _score_of(values: Iterable[bool]) -> float:
    """The one scoring rule, over whatever the caller counted as an assertion."""
    total = 0
    passed = 0
    for value in values:
        total += 1
        passed += 1 if value else 0
    if total == 0 or passed == total:
        return 1.0
    return passed / total


def _normalize_renderers(value: Any) -> dict[str, list[str]]:
    if value is None:
        return {"default": []}
    if isinstance(value, dict):
        return {str(name): list(argv) for name, argv in value.items()}
    raise ValueError("renderers must be an object mapping renderer names to argv lists")
