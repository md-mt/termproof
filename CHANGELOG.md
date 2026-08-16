# Changelog

All notable changes to TermProof are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - Unreleased

### Added

- **An attributed screen model, and colour in the final screenshot and video.**
  `termproof.attributed` keeps a per-cell grid — foreground and background,
  bold, dim, italic, underline, strikethrough, reverse, and double-width
  handling — instead of a flat string. The SVG renderer emits one `<text>` per
  cell positioned at `x = col * cell_w`, so column alignment no longer depends
  on whichever font the viewer resolves, and a red error no longer renders
  identically to ordinary prose. A grid can be read from a live `pyte.Screen`
  (`screen.screen_attributed`), from a recorded cast
  (`screen.replay_cast_attributed`), or parsed out of text that still carries
  SGR escapes. Canvas geometry is unchanged: for the default 80x24 the old and
  new formulas both give 756x516.

  **Not yet the per-step screenshots.** `final.svg` and the `attributed_rsvg`
  video render from the grid and carry colour; the images under `steps/` render
  from `StepResult.screen`, which is pyte's already-flattened `display`, so they
  are still monochrome. See `docs/evidence-quality.md` for what closing that
  needs.
- **An optional `render_attributed` method on the renderer protocol.** A
  renderer that defines it is handed the grid instead of text. Additive: a
  renderer written against the text-only protocol keeps working unchanged. See
  [`docs/plugin-protocols.md`](docs/plugin-protocols.md).
- **`png_rsvg`, a PNG renderer that rasterizes the attributed SVG.** Unlike the
  Pillow-based `png` renderer it keeps colour and styling, and it cannot drift
  from the `svg` output because it renders the same document. Needs
  `rsvg-convert`; `png` remains the default. Every external call goes through a
  `ToolRunner` seam, so a host with its own subprocess policy can supply one.
- **`attributed_rsvg`, a video backend that renders frames from the same
  attributed grid.** A video frame and a screenshot of the same moment are then
  the same image. Slower than `agg_ffmpeg` — one rasterizer call per frame —
  and encodes `yuv444p` rather than `yuv420p`, because 4:2:0 chroma subsampling
  smears the edges of coloured text. `agg_ffmpeg` remains the default.
- **A `tmux` session backend.** A pty is a byte pipe, so the pty backend has to
  reconstruct the screen with `pyte` — accurate, but a second emulator's opinion
  of what the first would have shown, and most likely to diverge for programs
  that repaint whole frames on the alternate screen. tmux owns a real grid, and
  `capture-pane` returns what is on it, with attributes. Set
  `session_backend: tmux`. The cast is recorded from `pipe-pane`, so it keeps
  the session's real timings.
- **`termproof.selection`, for running only the recipes a change could have
  broken.** A recipe's `ci_paths` are matched against the files a diff touched.
  `select_names` takes `(name, ci_paths)` pairs rather than recipe objects, so a
  host whose recipes are classes can use it too; `select_recipes` is the wrapper
  for this package's model. An `always` set runs regardless, and `harness_paths`
  falls back to that set when the change is to the harness itself — the
  path-to-recipe mapping is then exactly what is in question.
- **`BuildInfo.from_binary` and `BuildInfo.from_source_build`.** `from_command`
  resolves a name on PATH, which does not describe a binary built for the run.
  A source build records `build_target` (what produced it) and `source_ref` (a
  PR number, diff number or tag), and `verify_provenance` requires both plus a
  binary that exists — previously any commit at all was enough, including the
  working tree's, which says nothing about what was tested.
- **`asciinema` is now an optional extra, `termproof[record]`.** See Changed.
- **An `evidence:` block in `.termproof/config.yaml`.** The SVG and PNG
  renderers and the video pipeline no longer hardcode their rendering
  parameters: `evidence.svg` (character width, line height, padding, font size
  and family, foreground and background), `evidence.png` (scale, padding, font
  size and path, foreground and background) and `evidence.video` (fps, fps cap,
  pixel format, CRF, preset, tune, idle time limit, last frame duration, theme,
  font size and family) are all settable, and every default reproduces the
  previous hardcoded behaviour byte for byte (#158). Alongside them,
  `evidence.dedup_step_screenshots` (default `false`) skips the screenshot for a
  step whose screen is unchanged from the immediately preceding step, plus a
  `steps/steps-manifest.json` mapping every step onto the image that represents
  it and a `step_manifest` artifact key. Half the consecutive step screenshots
  in the shipped recipes are byte-identical, because a step that only waits for
  the screen to settle re-renders the screen already written. It stays off by
  default because it changes the artifact layout: a consumer that globs the step
  directory has to read the manifest instead. Every step keeps its own `.txt`
  either way. See `docs/evidence-quality.md` for the research behind the
  recommended values.

### Changed

- **The default session backend records the cast itself.** `pexpect` (new
  default) spawns the child directly and writes the asciinema v2 cast from the
  PTY output it is already reading. The `asciinema` CLI is no longer required
  to run TermProof, and has moved out of the base dependencies into a
  `termproof[record]` extra. The previous behaviour is still available as the
  `pexpect_asciinema` backend, for when the cast has to be one asciinema itself
  wrote — install the extra and set `session_backend: pexpect_asciinema`.
  `asciinema` was never imported, only shelled out to, and it was the one
  dependency most likely to be missing in a vendored or offline environment.
- **Step-screenshot dedup compares the rendered grid, not the screen text.**
  Two consecutive steps whose screens differed only in colour compared equal, so
  the second reused the first's image — and a colour change is frequently the
  whole signal. Dedup now fingerprints the attributed grid the screenshot is
  rendered from. For screens with no escapes the fingerprint is a function of
  the text alone, so behaviour is unchanged there.
- **One SVG renderer instead of two.** `screen.render_svg` was a second copy of
  `builtin_renderers.SvgRenderer`, with a comment saying the two had to be kept
  in step. It is now a wrapper over the renderer.
- **The rendered corpus under `examples/artifacts/` is regenerated.** All 146
  checked-in SVGs differ, because the markup shape changed from one `<text>` per
  line to one per cell. No session was re-recorded — the `session.cast` files
  are untouched and the only input that changed is the renderer. A recorded run
  of `examples/colorstress` joins the corpus as the entry that can catch a
  regression back to monochrome; every other recipe drives a monochrome TUI.

- **`wait_for_idle` no longer treats a session that has produced no output as
  idle.** The stable window is armed by the first byte the session emits, so a
  session that has emitted nothing at all can no longer have its blank initial
  screen captured as the final evidence. The deliberate trade: a target that stays alive and emits
  nothing at all can never report idle, and will fail the step after its
  timeout — including the single-step recipe produced by `termproof init`. For
  an evidence-recording tool a zero-output session is not something we can
  attest to, so it is reported rather than passed. That failure now reads
  `no output observed from the session` instead of `timed out waiting for
  idle`. Once armed, quiescence is still measured on rendered screen text
  alone, so terminal-title ticks, colour-only animation and idempotent repaints
  go idle exactly as before.

### Fixed

- **The `tmux` backend recorded casts with every carriage return stripped.** The
  `pipe-pane` fifo was read in Python's default text mode, whose universal-newline
  translation rewrites `\r\n` to `\n` and a bare `\r` to `\n`. Nothing looked
  missing — every glyph and every escape sequence was recorded — but replaying
  the cast never returned the cursor to column 0, so `final.svg` and `final.txt`
  came out as a diagonal staircase and `\r`-redrawn progress lines were lost.
- **`attributed_rsvg` now names what to install when a tool is missing.** It
  reported which of `rsvg-convert` / `ffmpeg` it could not find but not what to
  do about it, unlike `png_rsvg`, which already named the alternative.

### Removed

- **The Rust engine.** The in-progress Rust reimplementation has moved to its
  own repository, [md-mt/termproof-rust](https://github.com/md-mt/termproof-rust),
  and no longer ships from here. Concretely:
  - the GitHub Action no longer accepts `engine: rust`; passing it now fails
    with an explanatory error instead of downloading a release archive. The
    `rust-version` input is gone. `engine: auto` and `engine: python` are
    unchanged.
  - the container image no longer contains the `termproof-rust` binary. It
    still contains a Rust toolchain, which builds the `agg` cast renderer and
    is unrelated.
  - the `rust/` workspace, the `Rust` and `Release (Rust)` workflows, the
    `rust` build dependency in the Homebrew formula, and the
    `pyproject.toml` ↔ `rust/Cargo.toml` version drift check are gone.
  - `docs/rust-reimplementation-spec.md`, `docs/rust-gates.md` and the docs-site
    Rust pages are gone; `/rust/` now explains the move.

  **There is no replacement yet.** `termproof-rust` has not published a release
  and has no parity gate — a differential harness found the two implementations
  agreeing on 55 of 217 cases. The Python implementation, which is what every
  install channel has always shipped, remains the only supported engine.

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
