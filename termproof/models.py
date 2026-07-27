from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


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


@dataclass(frozen=True)
class StepResult:
    name: str
    passed: bool
    detail: str
    screen: str


@dataclass(frozen=True)
class AssertionResult:
    name: str
    passed: bool
    detail: str


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
            "steps": [step.__dict__ for step in self.steps],
            "assertions": [assertion.__dict__ for assertion in self.assertions],
            "artifacts": self.artifacts,
        }


def recipe_from_mapping(data: dict[str, Any]) -> Recipe:
    command_data = data["command"]
    command = CommandSpec(
        argv=list(command_data["argv"]),
        cwd=command_data.get("cwd"),
        env=dict(command_data.get("env", {})),
        pty=bool(command_data.get("pty", True)),
    )
    return Recipe(
        name=data["name"],
        recipe_version=int(data.get("recipe_version", 1)),
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

    return recipe_from_mapping(json.loads(path.read_text(encoding="utf-8")))


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
