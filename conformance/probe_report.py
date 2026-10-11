#!/usr/bin/env python3
"""Oracle half of the report differential harness.

Records what :meth:`termproof.report.ReportGenerator.generate_markdown`
emits for a fixed set of scenarios — the aggregate ``# TUI Verification``
document both CLIs write to disk. The Rust half transcribes the same
scenarios through ``evidence::report::generate_markdown`` and compares the
markdown per case.

The scenarios are code, not a corpus of cases, as with the run result: the
document is built by constructing results rather than by replaying data.
Six calls cover the shapes one cannot: a bare pass/fail mix, the same pair
with a ``BuildInfo`` and with a ``BeforeAfterResult``, artifact maps that
are empty against ones whose values are empty strings, details carrying
newlines, and no results at all.

This half records the Python document as it is. The known divergences —
the Rust generator taking no ``build_info`` or ``before_after`` at all, so
both sections are absent there, and empty-string artifact values being
suppressed here where Rust renders ``[screenshot]()`` (#209) — are **not**
recorded here: they are named allowances in the Rust test, so the checked-in
expectation stays the oracle's testimony and each allowance has to be
edited deliberately, in code, if either side changes.

Python has two markdown entry points with duplicated bodies sharing
``report_helpers`` — ``ReportGenerator.generate_markdown`` and
``MarkdownReporter.generate``. Each case drives both and fails here if
they part, so the recording is testimony for the pair, not for one copy.

The build-info scenario points at a binary path that does not exist, so
``verify_provenance`` answers ``no`` on every host and the recorded
markdown carries no machine-specific path.

Regenerate deliberately::

    cd /path/to/termproof/python
    TERMPROOF_PYTHON_REPO=$PWD uv run python \\
        ../conformance/probe_report.py \\
        > ../conformance/corpus/report.expected.json
"""

from __future__ import annotations

import json
import os
import platform
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, os.environ.get("TERMPROOF_PYTHON_REPO", str(Path(__file__).parent.parent / "python")))

from termproof.before_after import BeforeAfterResult, build_before_after  # noqa: E402
from termproof.build_info import BuildInfo  # noqa: E402
from termproof.builtin_reporters import MarkdownReporter  # noqa: E402
from termproof.models import AssertionResult, RunResult, StepResult  # noqa: E402
from termproof.report import ReportGenerator  # noqa: E402

BINARY = "/nonexistent-termproof-report/built"


def _pair() -> list[RunResult]:
    """The pass/fail pair the first three cases share. Keep in step with
    differential_report.rs."""
    return [
        RunResult(
            recipe_name="login",
            passed=False,
            exit_code=1,
            duration_seconds=1.25,
            priority="P0",
            execution="scripted",
            renderer="default",
            score=0.5,
            steps=[
                StepResult(
                    name="menu-open",
                    passed=True,
                    detail="screen contains 'MENU'",
                    screen="MENU\nitem one",
                )
            ],
            assertions=[
                AssertionResult(name="screen_contains", passed=False, detail="menu missing")
            ],
            # `notes` is outside the evidence key list both sides walk.
            artifacts={"screenshot": "/tmp/evidence/final.png", "notes": "ignored.txt"},
        ),
        RunResult(
            recipe_name="search",
            passed=True,
            exit_code=0,
            duration_seconds=0.5,
            priority="P1",
            execution="agent-driven",
            renderer="ink",
            score=1.0,
            steps=[
                StepResult(name="type-query", passed=True, detail="typed 'hello'", screen="hello")
            ],
            assertions=[AssertionResult(name="exit_code", passed=True, detail="exit 0")],
            artifacts={"cast": "search.cast", "screenshot": "search.png"},
        ),
    ]


def _outcome(recipe_name: str, renderer: str, passed: bool) -> RunResult:
    """A result carrying only what ``before_after`` reads."""
    return RunResult(
        recipe_name=recipe_name,
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


def _bare(recipe_name: str, passed: bool, score: float, artifacts: dict[str, str]) -> RunResult:
    return replace(_outcome(recipe_name, "default", passed), score=score, artifacts=artifacts)


def cases() -> list[dict[str, str]]:
    generator = ReportGenerator()
    reporter = MarkdownReporter()

    def record(
        name: str,
        results: list[RunResult],
        build_info: BuildInfo | None = None,
        before_after: BeforeAfterResult | None = None,
    ) -> dict[str, str]:
        markdown = generator.generate_markdown(
            results, build_info=build_info, before_after=before_after
        )
        if reporter.generate(results, build_info=build_info, before_after=before_after) != markdown:
            raise SystemExit(f"the two Python markdown paths diverged on case {name!r}")
        return {"name": name, "markdown": markdown}

    pair = _pair()
    build_info = BuildInfo(
        mode="installed",
        command=[BINARY, "--serve"],
        binary_path=BINARY,
        version="tool 1.2.3\nsecond line",
        git_commit=None,
        timestamp="2026-01-02T03:04:05",
    )
    before_after = build_before_after(
        [_outcome("login", "default", True), _outcome("search", "ink", True)],
        pair,
    )
    return [
        record("bare-mix", pair),
        record("with-build-info", pair, build_info=build_info),
        record("with-before-after", pair, before_after=before_after),
        record(
            "artifact-emptiness",
            [
                _bare("no-evidence", True, 1.0, {}),
                _bare("blank-evidence", True, 1.0, {"screenshot": "", "video": ""}),
                _bare("mixed-evidence", False, 0.0, {"screenshot": "", "cast": "run.cast"}),
            ],
        ),
        record(
            "multiline-details",
            [
                RunResult(
                    recipe_name="chatty",
                    passed=False,
                    exit_code=1,
                    duration_seconds=0.0,
                    priority="P0",
                    execution="scripted",
                    renderer="default",
                    score=0.0,
                    steps=[
                        StepResult(
                            name="boot",
                            passed=False,
                            detail="first line\nsecond line",
                            screen="",
                        )
                    ],
                    assertions=[
                        AssertionResult(name="contains", passed=False, detail="wanted X\n\ngot Y")
                    ],
                    artifacts={},
                )
            ],
        ),
        record("empty-results", []),
    ]


def main() -> None:
    document = {
        "_comment": (
            "Generated by conformance/probe_report.py against the Python "
            "implementation. Do not hand-edit; regenerate instead."
        ),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.system(),
        },
        "cases": cases(),
    }
    json.dump(document, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
