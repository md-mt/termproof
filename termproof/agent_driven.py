from __future__ import annotations

import json
import os
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .cast import CastRecorder
from .models import AssertionResult, Recipe, StepResult
from .protocols import AgentRunner
from .screen import replay_cast
from .session import TerminalSession


@dataclass(frozen=True)
class AgentOutcome:
    assertions: dict[str, bool]
    transcript: str
    raw_output: str
    exit_code: int | None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CodexCliAgentRunner:
    command: list[str] = field(default_factory=lambda: ["codex", "exec"])
    timeout_seconds: float = 180.0
    prompt_mode: str = "stdin"
    cwd: str | None = None
    env: dict[str, str] = field(default_factory=dict)
    record_terminal: bool = True

    @classmethod
    def from_recipe(cls, recipe: Recipe) -> "CodexCliAgentRunner":
        config = recipe.operator
        command = list(config.get("command", ["codex", "exec"]))
        timeout_seconds = float(config.get("timeout_seconds", 180))
        prompt_mode = str(config.get("prompt_mode", "stdin"))
        cwd = config.get("cwd")
        env = dict(config.get("env", {}))
        record_terminal = bool(config.get("record_terminal", True))
        return cls(command, timeout_seconds, prompt_mode, cwd, env, record_terminal)

    def run(self, recipe: Recipe, prompt: str, run_dir: Path) -> AgentOutcome:
        if self.record_terminal:
            return self._run_recorded(recipe, prompt, run_dir)
        return self._run_subprocess(prompt)

    def _run_recorded(self, recipe: Recipe, prompt: str, run_dir: Path) -> AgentOutcome:
        command = list(self.command)
        if self.prompt_mode == "arg":
            command.append(prompt)
        elif self.prompt_mode == "stdin":
            prompt_path = (run_dir / "agent_prompt.md").resolve()
            command = ["sh", "-lc", f"{shlex.join(command)} < {shlex.quote(str(prompt_path))}"]
        with TerminalSession(
            command,
            run_dir / "session.cast",
            self.cwd,
            self.env,
            recipe.cols,
            recipe.rows,
        ) as session:
            session.wait_for_exit(self.timeout_seconds)
            raw_output = session.raw_output
            exit_code = session.exit_code
        assertions, transcript, metadata = parse_agent_output(raw_output)
        return AgentOutcome(
            assertions=assertions,
            transcript=transcript,
            raw_output=raw_output,
            exit_code=exit_code,
            metadata={
                **metadata,
                "command": command,
                "recorded_cast": str(run_dir / "session.cast"),
            },
        )

    def _run_subprocess(self, prompt: str) -> AgentOutcome:
        env = os.environ.copy()
        env.update(self.env)
        command = list(self.command)
        input_text = prompt
        if self.prompt_mode == "arg":
            command.append(prompt)
            input_text = ""
        try:
            completed = subprocess.run(
                command,
                cwd=self.cwd,
                env=env,
                input=input_text,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=self.timeout_seconds,
            )
            assertions, transcript, metadata = parse_agent_output(completed.stdout)
            return AgentOutcome(
                assertions=assertions,
                transcript=transcript,
                raw_output=completed.stdout,
                exit_code=completed.returncode,
                metadata={**metadata, "command": command},
            )
        except subprocess.TimeoutExpired as error:
            output = _timeout_output(error)
            return AgentOutcome(
                assertions={},
                transcript=output,
                raw_output=output,
                exit_code=None,
                metadata={"command": command, "timed_out": True},
            )
        except FileNotFoundError as error:
            output = str(error)
            return AgentOutcome(
                assertions={},
                transcript=output,
                raw_output=output,
                exit_code=127,
                metadata={"command": command},
            )


@dataclass
class AgentDrivenRunner:
    agent_runner: AgentRunner

    def run(
        self,
        recipe: Recipe,
        run_dir: Path,
    ) -> tuple[list[StepResult], list[AssertionResult], str, int | None, str]:
        prompt = build_agent_prompt(recipe)
        (run_dir / "agent_prompt.md").write_text(prompt, encoding="utf-8")
        outcome = self.agent_runner.run(recipe, prompt, run_dir)
        _write_agent_files(run_dir, outcome)
        screen = _screen_from_agent_cast(recipe, run_dir, outcome)
        steps = [
            StepResult(
                name="codex-operator",
                passed=outcome.exit_code == 0,
                detail=f"operator exit code {outcome.exit_code}",
                screen=screen,
            )
        ]
        assertions = _agent_assertions(recipe, outcome)
        return steps, assertions, outcome.raw_output, outcome.exit_code, screen


def build_agent_prompt(recipe: Recipe) -> str:
    checks = recipe.checks or ["Codex operator completed the verification"]
    target = " ".join(shlex.quote(part) for part in recipe.command.argv)
    data = {
        "recipe": recipe.name,
        "description": recipe.description,
        "intent": recipe.intent,
        "target_command": recipe.command.argv,
        "cwd": recipe.command.cwd,
        "pty": recipe.command.pty,
        "terminal": {"cols": recipe.cols, "rows": recipe.rows},
        "checks": checks,
        "steps": recipe.steps,
        "assertions": recipe.assertions,
        "expect_exit_code": recipe.expect_exit_code,
    }
    return "\n".join(
        [
            "You are the Codex operator for an evidence-first TUI verification run.",
            "",
            "Exercise the target terminal workflow and decide whether each check passes.",
            "Do not modify files; only inspect or run commands needed for verification.",
            "The harness will turn your transcript into asciinema evidence, screenshots, videos, and reports.",
            "",
            f"Target command: `{target}`",
            "",
            "Recipe context:",
            "```json",
            json.dumps(data, indent=2),
            "```",
            "",
            "Return JSON only with this schema:",
            "```json",
            '{"assertions":{"check name":true},"transcript":"what you observed","notes":"optional"}',
            "```",
        ]
    )


def parse_agent_output(output: str) -> tuple[dict[str, bool], str, dict[str, Any]]:
    data = _load_json(output)
    if data is None:
        return {}, output, {}
    assertions = data.get("assertions", {})
    if not isinstance(assertions, dict):
        assertions = {}
    parsed_assertions = {str(name): bool(value) for name, value in assertions.items()}
    transcript = str(data.get("transcript") or output)
    metadata = {str(key): value for key, value in data.items() if key not in {"assertions", "transcript"}}
    return parsed_assertions, transcript, metadata


def _agent_assertions(recipe: Recipe, outcome: AgentOutcome) -> list[AssertionResult]:
    checks = recipe.checks or ["Codex operator completed the verification"]
    results = []
    seen = set()
    for check in checks:
        seen.add(check)
        passed = bool(outcome.assertions.get(check, False))
        detail = "agent reported pass" if passed else "agent did not report pass"
        results.append(AssertionResult(check, passed, detail))
    for name, passed in outcome.assertions.items():
        if name not in seen:
            detail = "agent reported pass" if passed else "agent reported fail"
            results.append(AssertionResult(name, bool(passed), detail))
    return results


def _write_agent_files(run_dir: Path, outcome: AgentOutcome) -> None:
    (run_dir / "agent_transcript.md").write_text(outcome.transcript, encoding="utf-8")
    (run_dir / "agent_outcome.json").write_text(
        json.dumps(
            {
                "assertions": outcome.assertions,
                "transcript": outcome.transcript,
                "exit_code": outcome.exit_code,
                "metadata": outcome.metadata,
                "raw_output": outcome.raw_output,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _screen_from_agent_cast(recipe: Recipe, run_dir: Path, outcome: AgentOutcome) -> str:
    cast_path = run_dir / "session.cast"
    if cast_path.exists():
        screen, _, _ = replay_cast(cast_path)
        return screen
    with CastRecorder(cast_path, recipe.cols, recipe.rows, ["codex-operator", recipe.name]) as recorder:
        recorder.output(outcome.transcript)
    screen, _, _ = replay_cast(cast_path)
    return screen


def _load_json(output: str) -> dict[str, Any] | None:
    values: list[dict[str, Any]] = []
    candidates = [output.strip(), *[line.strip() for line in reversed(output.splitlines())]]
    if "```" in output:
        chunks = output.split("```")
        candidates.extend(chunk.removeprefix("json").strip() for chunk in reversed(chunks))
    for candidate in candidates:
        if not candidate:
            continue
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            values.append(value)
    decoder = json.JSONDecoder()
    for start in reversed([index for index, char in enumerate(output) if char == "{"]):
        try:
            value, _ = decoder.raw_decode(output[start:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            values.append(value)
    for value in values:
        if "assertions" in value or "transcript" in value:
            return value
    return values[0] if values else None


def _timeout_output(error: subprocess.TimeoutExpired) -> str:
    stdout = error.stdout or ""
    stderr = error.stderr or ""
    if isinstance(stdout, bytes):
        stdout = stdout.decode(errors="replace")
    if isinstance(stderr, bytes):
        stderr = stderr.decode(errors="replace")
    return f"{stdout}{stderr}\n[Codex operator timed out]"
