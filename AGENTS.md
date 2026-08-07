# AGENTS.md

## PTY tests must hold under both unittest and pytest

CI and the documented local workflow run the suite with `unittest discover -s tests`
(see `CONTRIBUTING.md`), but pytest's extra harness startup shifts PTY timing enough
to expose races unittest never reaches. A green unittest run is therefore not
evidence that a PTY test is stable — run new or changed PTY tests under both runners
before landing, and treat a pytest-only failure as a real bug rather than harness
noise. Regression example:
`tests/test_runner.py::QuiescenceBehaviorTest::test_wait_for_idle_does_not_report_idle_before_first_output`.
