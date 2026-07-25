# Documentation Index

Welcome to TUI Verifier engineering documentation.

## Getting Started

- [README](../README.md) — project overview, quickstart, recipe authoring primer
- [Recipe Packs](recipe-packs.md) — reusable packaging contract for recipes
- [Releases](releases.md) — versioning and release lifecycle

## Design Documentation

- [Overview](overview.md) — core principle (recorded sessions; final/proof derivations), package layout, public API, mental model
- [Architecture](architecture.md) — component map, module-by-module boundaries, dependency flow
- [Extension Points](extension-points.md) — 7 registries plus a configurable session backend (8 extension families), protocols, exact signatures, how to wire custom implementations, mode-specific limitations
- [Execution Flow](execution-flow.md) — CLI entry, run loop, execution modes (PTY / process / agent-driven) with mode-specific wiring, assertion evaluation (scripted only), renderer selection, data flow
- [Configuration](configuration.md) — cascade model (builtin → user → project), BUILTIN_DEFAULTS, VerifierConfig, merge semantics, known --config bug, unused defaults, error cases
- [Evidence Pipeline](evidence-pipeline.md) — run dir creation, session recording (TerminalSession + CastRecorder), replay (pyte), artifact rendering (fixed .svg contract, agg gate), result files, CI artifacts
- [Testing, CI, Release](testing-ci-release.md) — 31 tests/8 files including registry and agent artifact/backend coverage, asciinema/real process requirements, packaging, E2E verification, GitHub Actions workflows (CI triggers PR/main; Release triggers tag/manual), versioning contract, downstream CI usage
- [Plugin Authoring](plugin-authoring.md) — accurate minimal examples (SVG-compatible, fixed execution key behavior, programmatic VerificationRunner(agent_runner=...) path, context manager requirement, agg gate), recipe-level patterns and pitfalls
- [Design Decisions](design-decisions.md) — decisions grounded in current code with source refs, lower-bound dependency semantics, plus open limitations

## Reading Order

If you're new:

1. README → overview
2. architecture → extension-points → configuration
3. execution-flow → evidence-pipeline
4. plugin-authoring when extending
5. design-decisions for rationale

If you're operating CI:

- README "GitHub Actions" section
- testing-ci-release

If you're verifying a TUI:

- README "Plug In Any TUI" section
- recipe-packs + plugin-authoring recipe-level examples

## Cross-links

- Source entry points: `tui_verifier/__init__.py`, `tui_verifier/cli.py`, `tui_verifier/runner.py`
- Config canonical source: `tui_verifier/config.py:BUILTIN_DEFAULTS`
- Registry mechanism: `tui_verifier/registry.py:Registry`
- Evidence types: `docs/evidence-pipeline.md` + `examples/generic/generic_tui.recipe.json`
