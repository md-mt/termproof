from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

RECIPE_VERSION = 1


@dataclass(frozen=True)
class CommandSpec:
    argv: list[str]
    cwd: str | None = None
    env: dict[str, str] = field(default_factory=dict)
    pty: bool = True


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


@dataclass(frozen=True)
class StepResult:
    name: str
    passed: bool
    detail: str
    screen: str

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
    report rather than raise. ``detail`` says which. Both a link rewrite and a
    manifest entry are only warranted for an artifact that is published and
    addressable, so callers can tell the two conditions apart.
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


def score_from_assertions(assertions: list[AssertionResult]) -> float:
    if not assertions:
        return 1.0
    passed = sum(1 for assertion in assertions if assertion.passed)
    return 1.0 if passed == len(assertions) else passed / len(assertions)


def _normalize_renderers(value: Any) -> dict[str, list[str]]:
    if value is None:
        return {"default": []}
    if isinstance(value, dict):
        return {str(name): list(argv) for name, argv in value.items()}
    raise ValueError("renderers must be an object mapping renderer names to argv lists")
