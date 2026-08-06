from __future__ import annotations

import sys
import time

SCENARIOS = {
    "readonly-review": {
        "title": "Pi workflow: read-only repository review",
        "responses": [
            (
                ("scope", "repository"),
                [
                    "assistant> Launching Pi in read-only review mode.",
                    'assistant> pi --tools read,grep,find,ls --no-session -p "Review the repository."',
                    "assistant> write and edit tools are disabled for this run.",
                    "assistant> READONLY SCOPE READY",
                ],
            ),
            (
                ("inspect", "files"),
                [
                    "assistant> read package metadata.",
                    "assistant> find recipe files under examples/.",
                    "assistant> grep for assertion coverage and sandbox guards.",
                    "assistant> no write/edit tools were enabled.",
                    "assistant> READONLY INSPECTION COMPLETE",
                ],
            ),
            (
                ("run", "validation"),
                [
                    "assistant> bash tool is intentionally unavailable in this read-only pass.",
                    "assistant> operator requests separate CI validation.",
                    "assistant> recorded expectation: 12 tests passed in prior validation.",
                    "assistant> READONLY VALIDATION COMPLETE",
                ],
            ),
            (
                ("report", "findings"),
                [
                    "assistant> Findings: no blocking issues.",
                    "assistant> Residual risk: provider-backed live runs are covered by separate recipes.",
                    "assistant> READONLY REVIEW COMPLETE",
                ],
            ),
        ],
    },
    "guarded-edit": {
        "title": "Pi workflow: guarded edit and validation",
        "responses": [
            (
                ("propose", "change"),
                [
                    "assistant> Reading target files before editing.",
                    "assistant> tool allowlist: read,bash,edit,write.",
                    "assistant> proposing a small patch with isolated behavior.",
                    "assistant> GUARDED EDIT PLAN READY",
                ],
            ),
            (
                ("apply", "patch"),
                [
                    "assistant> edit tool: applying patch.",
                    "assistant> changed files: recipe plus focused implementation.",
                    "assistant> patch applied.",
                    "assistant> GUARDED PATCH APPLIED",
                ],
            ),
            (
                ("validate", "tests"),
                [
                    "assistant> bash> uv run python -m unittest discover -s tests",
                    "assistant> 12 tests passed.",
                    "assistant> diff reviewed before final summary.",
                    "assistant> GUARDED VALIDATION COMPLETE",
                ],
            ),
            (
                ("summarize", "diff"),
                [
                    "assistant> Summary: implemented requested behavior and evidence checks.",
                    "assistant> Test evidence: unit suite passed.",
                    "assistant> GUARDED EDIT COMPLETE",
                ],
            ),
        ],
    },
    "session-resume-export": {
        "title": "Pi workflow: session resume, fork, and export",
        "responses": [
            (
                ("start", "session"),
                [
                    'assistant> pi --name "Verifier workflow audit" --session-dir .pi-sessions',
                    "assistant> session id: workflow-001.",
                    "assistant> SESSION STARTED",
                ],
            ),
            (
                ("continue", "session"),
                [
                    "assistant> pi --continue \"What did we verify?\"",
                    "assistant> pi --session workflow-001",
                    "assistant> previous context restored.",
                    "assistant> SESSION RESUMED",
                ],
            ),
            (
                ("fork", "export"),
                [
                    "assistant> pi --fork workflow-001 --name \"Workflow audit branch\"",
                    "assistant> pi --export session.jsonl output.html",
                    "assistant> exported review artifact for handoff.",
                    "assistant> SESSION RESUME EXPORT COMPLETE",
                ],
            ),
        ],
    },
    "model-context": {
        "title": "Pi workflow: model routing and context resources",
        "responses": [
            (
                ("choose", "model"),
                [
                    "assistant> pi --provider openai --model gpt-4o-mini",
                    "assistant> pi --model sonnet:high --thinking high",
                    "assistant> pi --models claude-sonnet,claude-haiku,gpt-4o",
                    "assistant> MODEL ROUTING READY",
                ],
            ),
            (
                ("load", "context"),
                [
                    "assistant> pi --append-system-prompt project-rules.md",
                    "assistant> pi --skill ./skills/reviewer",
                    "assistant> pi --prompt-template ./prompts/fix-bug.md",
                    "assistant> CONTEXT RESOURCES LOADED",
                ],
            ),
            (
                ("configure", "startup"),
                [
                    "assistant> pi --offline --no-context-files --no-extensions --no-skills",
                    "assistant> pi --theme ./themes/quiet.json --no-themes",
                    "assistant> startup behavior is explicit and reviewable.",
                    "assistant> MODEL CONTEXT WORKFLOW COMPLETE",
                ],
            ),
        ],
    },
}


def main() -> int:
    scenario_name = sys.argv[1]
    scenario = SCENARIOS[scenario_name]
    emit([scenario["title"], "Type workflow commands; use exit to close.", ""], 0.15)
    prompt()
    for raw_line in sys.stdin:
        text = raw_line.strip()
        if not text:
            prompt()
            continue
        if text.lower() in {"exit", "quit"}:
            emit(["assistant> Closing Pi workflow demonstration.", "WORKFLOW SESSION COMPLETE"], 0.2)
            return 0
        print(f"user> {text}", flush=True)
        respond(scenario, text.lower())
        print("", flush=True)
        prompt()
    return 0


def respond(scenario: dict[str, object], text: str) -> None:
    for keywords, lines in scenario["responses"]:
        if all(keyword in text for keyword in keywords):
            emit(lines, 0.35)
            return
    emit(["assistant> I need a workflow command for this scenario."], 0.25)


def emit(lines: list[str], delay: float) -> None:
    for line in lines:
        print(line, flush=True)
        time.sleep(delay)


def prompt() -> None:
    print("pi> ", end="", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
