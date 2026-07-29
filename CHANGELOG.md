# Changelog

All notable changes to TermProof are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.1] — 2026-07-29

### Added

#### Distribution & packaging
- **Bundled `agg` binary.** Prebuilt `agg` wheels are shipped so video rendering works without a separate `agg` install, closing the v0.2.0 known limitation (#49).
- **Reusable GitHub Action** (`action.yml`). Run TermProof recipes and upload reviewable evidence directly from a workflow (#49).
- **Generic Docker image.** A ready-to-run container image for executing recipes (#59).
- **Homebrew formula** (`Formula/termproof.rb`) for `brew install` distribution (#64).

#### Core engine
- **`json_schema` assertion.** Validate structured output against a JSON Schema (#52).
- **PNG screen renderer** (`png`). Per-step and final screenshots rendered as PNG (#54).
- **Docker session backend.** Execute recipes inside a Docker container (#53).
- **Recipe v1 validation.** Recipes are validated against a versioned schema before execution (#51).
- **Parallel recipe execution.** Run multiple recipes concurrently (#60).
- **Visual diff mode.** Compare screenshots to detect visual regressions (#61).
- **Unchanged recipe cache.** Skip re-running recipes whose inputs are unchanged (#62).

#### CLI
- **`termproof plugins`** command to inspect registered plugins (#55).

#### CI/CD & integrations
- **GitLab CI template** (#57), **CircleCI orb source** (#58), and **framework integration guides** (#56).
- **Receipt-backed CI evidence reports** (#68) and **PR screenshot publishing** to an evidence branch (#70).
- **PyPI trusted publisher setup documentation** (#66).

#### Documentation
- **VitePress documentation site** (#63).
- **First-party plugin examples** listed in the docs (#65).

### Changed
- **Stabilized plugin protocol API** for steps, assertions, and backends (#50).
- **Pages deploy is now opt-in** (#67).
- **PyPI release publishing is now opt-in** via `ENABLE_PYPI` (#71).

---

## [0.2.0] — 2026-07-26

### Added

#### Core engine
- **Recipe-driven PTY execution.** JSON recipes drive real terminal applications through a pseudo-terminal. Launch any binary, type input, wait for regex patterns, run assertions — all deterministic and CI-friendly.
- **Asciinema cast recording.** Every run produces a standard `.cast` file. Replay with `asciinema play` or any asciinema-compatible tool.
- **Evidence pipeline.** Cast → per-step screenshots (SVG, PNG) → final screenshot → text snapshot → optional 60fps MP4 video. Evidence artifacts are files, not claims.
- **`wait_for_regex` step with group evidence.** Named capture groups in wait patterns produce structured evidence attached to the step result. No more "did the regex match?" — you see exactly what matched.
- **JUnit XML reporter** (`junit_xml`). Native CI integration — export test results as JUnit XML for GitHub Actions, GitLab CI, Jenkins, or any JUnit-compatible dashboard.
- **Markdown report generation.** Every run produces a `report.md` with pass/fail summary, per-step results, and evidence links.

#### Plugin system
- **Plugin registry architecture.** Steps, assertions, reporters, session backends, execution modes, video backends, and screen renderers are all pluggable via entry points.
- **Production-ready plugin template** (`plugin-template/`). Scaffold a new TermProof plugin with `termproof scaffold --template`. Includes working example step, assertion, reporter, config wiring, and test suite.
- **Builtin registrations.** Steps: `wait_for_text`, `wait_for_idle`, `send_text`, `send_line`, `press`, `sleep`, `wait_for_regex`. Assertions: `output_contains`, `output_not_contains`, `screen_contains`, `screen_not_contains`, `exit_code`, `file_exists`, `file_contains`. Reporters: `markdown`, `junit_xml`. Screen renderers: `svg`. Video backends: `agg_ffmpeg`. Execution modes: `scripted_pty`, `scripted_process`, `agent_driven`. Agent runners: `codex`.

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
