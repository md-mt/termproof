# Project agent memory

This file is the project's committed home for project-intrinsic agent knowledge: build, test, release, architecture, and sharp-edge notes that should travel with the code.

- Python-specific notes live in [`python/AGENTS.md`](python/AGENTS.md).

## The two implementations mirror each other

A surface added to `python/termproof/` normally has a counterpart in
`rust/crates/termproof/`, with the same name and the same semantics. Where the
languages force a difference, the house pattern is `Option<T>` for a Python
keyword default and `Err` for a Python `ValueError`.

Parity is asserted, not assumed: `conformance/README.md` is the authority on the
three differential harnesses and on how to regenerate a corpus. Read it before
changing anything a harness compares — regenerating an expected file to make a
test pass is how a real divergence gets recorded as correct.

## A test can be gated by more than the suite it lives in

`python/scripts/run_stdlib_tests.py` re-runs a listed subset of test modules in
an environment with **no** third-party packages installed, which is what holds
the modules in its `STDLIB_ONLY` map to their documented "standard library only"
claim. Adding a test to one of those modules that needs `pyte`, `pexpect` or
Pillow at runtime leaves `unittest discover` green and fails that job; guard it
with `unittest.skipUnless` the way the existing ones do. The script's docstring
is the authority.

## Maintaining this file

Keep this file for knowledge useful to almost every future agent session in this project.
Do not repeat what the codebase already shows; point to the authoritative file or command instead.
Prefer rewriting or pruning existing entries over appending new ones.
When updating this file, preserve this bar for all agents and keep entries concise.
