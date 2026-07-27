# Changelog

All notable changes to TermProof are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] — 2026-07-26

### Added

#### Core engine
- **Recipe-driven PTY execution.** JSON recipes drive real terminal applications through a pseudo-terminal. Launch any binary, type input, wait for regex patterns, run assertions — all deterministic and CI-friendly.
- **Asciinema cast recording.** Every run produces a standard `.cast` file. Replay with `asciinema play` or any asciinema-compatible tool.
- **Evidence pipeline.** Cast → per-step screenshots (SVG, PNG) → final screenshot → text snapshot → optional 60fps MP4 video. Evidence artifacts are files, not claims.
- **`wait_for_regex` step with group evidence.** Named capture groups in wait patterns produce structured evidence attached to the step result. No more "did the regex match?" — you see exactly what matched.
- **JUnit XML reporter** (`builtin_reporters.junit_xml_reporter`). Native CI integration — export test results as JUnit XML for GitHub Actions, GitLab CI, Jenkins, or any JUnit-compatible dashboard.
- **Markdown report generation.** Every run produces a `report.md` with pass/fail summary, per-step results, and evidence links.

#### Plugin system
- **Plugin registry architecture.** Steps, assertions, reporters, session backends, execution modes, video backends, and screen renderers are all pluggable via entry points.
- **Production-ready plugin template** (`plugin-template/`). Scaffold a new TermProof plugin with `termproof scaffold --template`. Includes working example step, assertion, reporter, config wiring, and test suite.
- **Builtin registrations.** Steps: `spawn`, `type`, `wait_for_text`, `wait_for_regex`, `send_signal`, `sleep`, `capture_screen`. Assertions: `screen_contains`, `screen_matches`, `exit_code_equals`, `cast_duration_within`. Reporters: `markdown`, `junit_xml`.

#### CLI
- `termproof run <recipe>` — execute a recipe with full evidence pipeline
- `termproof demo` — interactive demo TUI that exercises all features
- `termproof scaffold <name> --template` — create a new plugin from the template
- `--video` / `--video-fps` — enable MP4 rendering via `agg` + `ffmpeg`
- `--out <dir>` — control output directory
- Config file support (`termproof.yaml`) for defaults

#### Documentation & launch
- **README** with comparison table, quickstart, demo instructions, and badge
- **GitHub Pages** site with polished project landing
- **Launch kit** (`docs/launch/`): HN Show post draft, outreach templates for 5 TUI frameworks (Bubble Tea, Ratatui, Textual, Ink, Charm), social media profiles and assets, launch runbook, pre-flight checklist
- **Contributing guide** and **Code of Conduct**
- **Verified by TermProof badge** for downstream projects

#### CI/CD
- GitHub Actions CI workflow: lint, type-check, test matrix (3.11, 3.12, 3.13), build verification
- Trusted publishing to PyPI via GitHub release trigger
- Release workflow with attestation

### Changed

- **Renamed from TUI Verifier to TermProof** (#42). Package, CLI entry point, docs, and all internal references updated.

### Known limitations

- Bundled `agg` binary distribution is deferred to v0.2.1. Users need `agg` installed separately for video rendering (`--video` flag).
- Video rendering requires `agg` (from asciinema) and `ffmpeg` on PATH.
- The launch kit outreach templates reference canonical artifact paths that may shift before launch day.

---

## Unreleased (pre-0.2.0 history)

All work prior to v0.2.0 was in the TUI Verifier codebase. Key milestones:

- **Config system + Step/Assertion plugin registry** — YAML config, entry-point-based plugin loading
- **Reporter + Screen Renderer registries** — pluggable output and rendering backends
- **Execution Mode + Agent Runner registries** — execution strategies, agent-driven test mode
- **SessionBackend + VideoBackend** — recording and video rendering integration
- **Agent-driven mode** — AI agents can drive the TUI via structured interaction
- **Engineering design documentation** — architecture, extension points, data flow
