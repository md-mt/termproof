# Documentation Index

Welcome to TUI Verifier engineering documentation.

## Getting Started

- [README](../README.md) — project overview, quickstart, recipe authoring primer
- [Recipe Packs](recipe-packs.md) — reusable packaging contract for recipes
- [Releases](releases.md) — versioning and release lifecycle

## Design Documentation

- [Overview](overview.md) — core principle (cast is source of truth), package layout, public API, mental model
- [Architecture](architecture.md) — component map, module-by-module boundaries, dependency flow
- [Extension Points](extension-points.md) — registries, protocols, exact signatures, how to wire custom implementations
- [Execution Flow](execution-flow.md) — CLI entry, run loop, execution modes (PTY / process / agent-driven), assertion evaluation, renderer selection, data flow
- [Configuration](configuration.md) — cascade model (builtin → user → project), BUILTIN_DEFAULTS, VerifierConfig, merge semantics, error cases
- [Evidence Pipeline](evidence-pipeline.md) — run dir creation, session recording (TerminalSession + CastRecorder), replay (pyte), artifact rendering (SVG / MP4 via agg+ffmpeg), result files, CI artifacts
- [Testing, CI, Release](testing-ci-release.md) — unit tests, packaging, E2E verification, GitHub Actions workflows (ci.yml, release.yml), versioning contract, downstream CI usage
- [Plugin Authoring](plugin-authoring.md) — concrete minimal examples for custom steps, assertions, screen renderers, reporters, session backends, video backends, execution modes, agent runners; recipe-level patterns and pitfalls
- [Design Decisions](design-decisions.md) — 17 grounded decisions with why and trade-off, plus open limitations

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
