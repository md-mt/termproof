# Changelog

All notable changes to TermProof are documented in this file — both
implementations, one history.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html),
with the pre-1.0 rule that under `0.x` a breaking change bumps the minor digit.

## How to read this file

- **One version number, one heading.** The Python implementation under
  `python/` and the Rust implementation under `rust/` share a version train,
  so a release number means the same point in the project's history for both.
- **Each heading is split by implementation** — `Python — Added`,
  `Rust — Changed`, and so on. A version with no section for an
  implementation changed nothing in it.
- **A heading is a point in the project's history, not a receipt for two
  artifacts.** Whichever release is cut first moves the shared version and
  promotes everything pending under `[Unreleased]`, so a version can carry
  entries for an implementation whose own artifact has not been published at
  that number yet. What is actually published, and where, is in
  [`SECURITY.md`](SECURITY.md#what-is-published-and-who-has-to-be-notified).
- **The artifacts stay independent.** A release is cut per implementation and
  tagged `py-v<version>` or `rs-v<version>`; the Python package goes to PyPI
  and the `termproof` crate to crates.io. One version train, two release
  paths.
- Add new entries under `[Unreleased]`, in the same PR as the change, under
  the implementation they affect.
- **Below 0.3.3 the two counts were independent**, so those headings can carry
  two release dates for one number. From 0.3.3 the counts are the same.

## [Unreleased]

### Rust — Added

- **`fancy_regex`, `jsonschema` and `vt100` are re-exported at the crate root.**
  All three reach the public API — `pyregex::compile` returns a
  `fancy_regex::Regex`, `pyschema::compile` a `jsonschema::Validator`, and
  `terminal::attributed::from_vt100` takes a `vt100::Screen` — and a
  third-party type in a signature is only interchangeable with the consumer's
  own when cargo hands both sides the same copy. Naming
  `termproof::fancy_regex::Regex` instead of your own makes that true by
  construction. Purely additive; nothing that compiled before stops.
  ([#177](https://github.com/md-mt/termproof/issues/177))

### Rust — Docs

- **The crate docs no longer claim `schemars` is the only dependency reaching
  the public API.** Three others do, and the claim is why that went unnoticed.
  A new *Dependencies in the public API* section names all four, says why a
  bound on them is a source-compatibility surface and not just a duplicate
  count, and records the resolver behaviour behind it: cargo takes the **top**
  of a requirement's range, so the window of versions a consumer can unify with
  is one version wide however the range is written — widening moves the window
  rather than enlarging it. `schemars` stays the one with no escape hatch,
  because its derives are on the published types rather than in a signature.
  ([#177](https://github.com/md-mt/termproof/issues/177))

### Docs

- **The distribution claims now say what 0.3.4 actually shipped.** Both
  packages are live — `termproof` on PyPI and the `termproof` crate on
  crates.io — and the repository still said otherwise in a dozen places.
  `README.md` denied the PyPI publish outright and named `0.3.3` as the newest
  crate; `SECURITY.md` reported the PyPI upload as still gated off;
  `rust/docs/publishing.md`, the release and security workflow headers, the
  Rust Dockerfile and the `termproof-cli` README were all a release behind.
  `rust-release.yml` and `rust/docs/publishing.md` also said no `rs-v*` tag had
  been cut, and `rust-auto-release.yml` explained its first-release guard as if
  none were reachable from `main`; `rs-v0.3.4` is both. The front door and the
  Python package page now offer `pip install termproof`, and the two
  "what is published" tables link the registries rather than enumerating
  versions that go stale.

- **`rust/docs/publishing.md` says how to keep those claims correct.** Moving
  them is a manual step after the publish, it has to move *all* of them — the
  whole set went stale together after `0.3.4` because the step was skipped —
  and it has to be scoped to what actually went out, because a Rust release
  cuts `rs-v*` while PyPI is only uploaded on `py-v*`. The existing sweep
  compares surfaces to each other, so it cannot see either failure.

- **The `publish-plan.py` transcript is gone from the same page.** It printed
  `"version": "0.3.3"` while the script printed `0.3.4`. An embedded sample of
  live tool output is a claim about the manifests that no test can check and no
  bump will move, so the page names the command and the shape of what it
  returns instead of pasting a run of it.

- **The container-image rows say what is actually in the registry.**
  `README.md` and `SECURITY.md` both said the two images publish on every push
  to `main` and every release tag. True of `ghcr.io/md-mt/termproof`; not of
  `ghcr.io/md-mt/termproof-rust`, whose push has been failing since the
  consolidation, so `latest` there is still the `0.3.3` build and no
  `rs-v0.3.4` image exists. The build itself is #178 and is not fixed here.

- **The smoke-install examples no longer pin a version that never existed.**
  `python/docs/releases.md` and `python/scripts/smoke-install.sh` showed
  `0.2.0`; PyPI has never carried it, so the documented smoke test could not
  succeed. Both take a `<version>` placeholder now. `docs/launch/checklist.md`
  keeps its `0.2.0` numbers — they are what that plan said — under a header
  saying plainly that it was never executed at that version.

### Python — Fixed

- The canonical recipe schema is a package resource
  (`termproof/_resources/recipe-schema-v1.json`) rather than a docs file
  relocated into the package at wheel-build time. It shipped in the wheel and
  nowhere else: a build system that consumes the sdist's sources directly runs
  no hatchling force-include, so `recipe_schema.load_recipe_schema()` found
  nothing and had to be patched back by hand on every version bump. The wheel
  layout is unchanged — same path, no force-include — and the sdist now carries
  the schema too. `load_recipe_schema()` lost its `docs/` fallback, which
  existed only because the resource was conditional (#174).

### Rust — Fixed

- `schema::load_canonical_schema` returns the canonical schema for every
  consumer, including a crates.io one. It resolved
  `../../../python/docs/recipe-schema-v1.json` from `CARGO_MANIFEST_DIR`; a
  registry checkout has no repository above it, so the function returned `None`
  for its actual audience. The crate now carries the schema at
  `resources/recipe-schema-v1.json` and embeds it with `include_str!`, so it
  reads no path outside itself and no working directory can influence the
  answer — the property the 0.3.4 removal of the cwd fallback was protecting,
  now held without giving up the schema (#174).

### Rust — Added

- `schema::CANONICAL_SCHEMA_JSON`, the embedded canonical schema as text.
- `tests/canonical_schema.rs` ships in the published package. It was excluded
  in 0.3.4 because it read outside the crate; it no longer does, so the seam is
  testable from the artifact that is published — including the decoy-directory
  regression (#174).

### Changed

- **`python/tests/test_docs_pages.py` no longer forbids `pip install
  termproof`.** It asserted the command's absence because the package was
  unpublished, and went on passing after the publish made that wrong.
- **`python/docs/recipe-schema-v1.json` stays where it is.** It is now a
  byte-identical copy rather than the original. It is not in the wheel, so no
  installed package carries it and no import path reaches it; the sdist ships
  it, as it ships all of `docs/`, and nothing loads it there either. It is kept
  because it is a *published path*: the schema has always been linked from
  `docs/recipe-format-v1.md`, so it may already be in a `$schema` line, a
  script or a bookmark, and moving a file inside the packages is no reason to
  404 a URL. The packaging argument against a third copy is about artifacts and
  answers a different question (#174).
- CI holds every copy of the canonical schema byte-identical against the
  package resource (`python/scripts/check_schema_copies.py`). It runs in `CI
  (Python)` and in all four release paths — Python release, Rust release, Rust
  publish and Rust auto-release — because a tag can be cut from a commit that
  passed neither pull-request nor `main` CI, and a mismatch there is two
  published artifacts disagreeing about what a recipe is (#174).

### Python — Added

- `StepResult.screen_attributed`, an optional `AttributedScreen | None`
  alongside the existing flattened `screen`. When it is present the per-step
  screenshot is rendered from it, so the images under `steps/` carry the colour
  and text attributes `final.svg` already did ([#175]).

  Every built-in session backend fills it — `pexpect`, `pexpect_asciinema` and
  `docker` from the session's `pyte.Screen`, `tmux` from `capture-pane -e` —
  and the agent-driven mode fills it from its cast replay. Over the 13 example
  recipes, step screenshots carrying attributed rendering went from 0/76 to
  11/76 (9 in colour, 11 with text attributes); the other 65 are byte-identical
  because those recipes drive genuinely monochrome TUIs.

  Optional means optional. A `SessionBackend` whose session does not implement
  `screen_attributed()` reports no grid, and its step screenshots render from
  the text exactly as before. The `png` renderer takes text only, so PNG step
  screenshots stay monochrome either way, and dim (SGR 2) reaches the grid on
  the tmux path but not the pty one.

  The field is deliberately absent from `StepResult.to_dict()`: `result.json` is
  a shape shared with the Rust implementation and read by the run cache, and
  nothing downstream of it re-renders an image. It is `compare=False` for the
  same reason — equality tracks the serialised shape, so a live result still
  equals `RunResult.from_dict(result.to_dict())` as it always has.

  `AttributedScreen` also grows a compact `__repr__`. The generated dataclass
  one was an `AttributedCell(...)` per cell, around half a megabyte for a
  100x32 grid, and a grid now hangs off every `StepResult` — which is what a
  failing assertion would have printed.

- `termproof.screen.capture_screen`, one read of a session's screen returning
  text and grid together, and `termproof.builtin_steps.step_result` for step
  actions that want the same. The grid is read first and the text derived from
  it, so `steps/NN.txt` and `steps/NN.svg` cannot describe different instants.

### Python — Fixed

- Step-screenshot dedup fingerprints the rendered grid so that a colour-only
  change between two steps counts as a change. That was inert for the artifacts
  dedup applies to, because the grid was rebuilt from already-flattened text; it
  now compares the grid the session reported ([#175]).

- A CSI escape sequence cut before its final byte no longer emits its parameter
  bytes as glyphs. `\x1b[31` at the end of a `capture-pane -e` line rendered as
  a literal `[31` in the middle of a screenshot; a terminal waiting for the
  terminator displays nothing, and now neither does the parser.

- A CSI sequence ending in a final byte that is not a letter no longer eats the
  first letter of the text after it. ECMA-48 puts the final byte at 0x40-0x7E;
  the parser scanned for `isalpha()`, so `before\x1b[1~after` rendered as
  `beforefter`. Same for `\x1b[5@`, `\x1b[2^`, `\x1b[?25l` and the rest of the
  non-letter finals. A fresh `ESC` now also abandons a sequence in progress
  rather than being read as one of its parameter bytes.

- Escape sequences that are not CSI are recognised rather than rendered as
  glyphs. Only CSI was handled; every other family had its `ESC` dropped and
  its body printed, so an OSC-8 hyperlink — which `capture-pane -e` really does
  emit — turned `beforeTXTafter` into `before]8;;url\TXT]8;;\after` in a step
  screenshot and in the `.txt` beside it. OSC, DCS, SOS, PM and APC are now
  consumed to either terminator (`BEL` or `ESC \`), as are charset designation,
  the DEC line-size controls and the two-byte escapes; SS2 and SS3 consume
  their introducer and leave the character they shift. None of them contributes
  anything visible, which is what a terminal shows for them too.

### Python — Changed

- The attributed grid builders share one cell object between cells that compare
  equal. A terminal screen is mostly repetition, so a typical 100x32 grid goes
  from 527 KiB to 31 KiB, and the 75 step grids a run over the example corpus
  retains go from 37.1 MiB to 2.9 MiB — 506 KiB down to 40 KiB per step. That
  is what makes keeping a grid per step affordable.

  The saving is in the repetition and nowhere else, so the floor is exactly no
  saving: a screen whose 3,200 cells are all distinct measures 527 KiB pooled
  and 527 KiB unpooled. No real screen looks like that, and the number states
  the mechanism rather than qualifying it.

  Measured with `tracemalloc`, summing allocations made in
  `termproof/attributed.py` that are still alive once the run's results are in
  hand. A `sys.getsizeof` walk of the same objects reads higher — around 46-55
  MiB unshared depending on what the walk counts — because `getsizeof` on a
  key-sharing instance dict reports more than the allocator handed out. Same
  conclusion either way.

[#175]: https://github.com/md-mt/termproof/issues/175

## [0.3.4] — 2026-08-17

One project, one version. The two repositories became one: the Rust
implementation was consolidated into `md-mt/termproof`, the repository root
became a front door for the project rather than for one implementation, the
community-health documents converged onto a single set, and the CI, release,
container and documentation pipelines were renamed so each says which
implementation it serves. Both artifacts move on one version number from here.
Two registries still mean two tags, `py-v` and `rs-v`, but one version and one
entry.

**The two implementations did not change by the same amount, and neither
changed much.** The Python package's runtime code did not change at all; the
Rust crate's changed in one function. Read the sections below rather than
assuming a release this size moved both.

### Python — Changed

- **The package's runtime code did not change.** `python/termproof/` is
  byte-identical to the previous release — same modules, same CLI, same
  behaviour. What follows is payload that ships beside it in the sdist and the
  wheel, not a reason to expect the tool to behave differently.
- **The README that ships in the sdist is rewritten** as the Python
  implementation's reference rather than the project's front door, which is
  the repository README now. It points at the Rust implementation, carries the
  renamed CI and release badges, and drops the star and fork counts.
- **The examples are presented as a set rather than a flagship showcase.**
  `examples/generic` is self-contained and needs no external binary, so it is
  the starting point; the colour-stress example, the multi-turn conversation
  and the `pi_workflow_*` recipes are listed beside it as different shapes of
  terminal program. The recipes themselves are unchanged. TermProof knows
  nothing about the program it drives beyond what a recipe says, and naming one
  example the flagship read as though it did.
- **The agent-driven test fixture names no organisation.** The fake agent in
  `tests/test_agent_driven.py` emitted a transcript carrying a company's name.
  Nothing asserts on that text — it only has to be a multi-line string that
  echoes part of the prompt — and the file ships in the sdist, so the payload
  is neutral now.
- **The documentation that ships beside the package** — the release, Docker
  and launch pages — describes the consolidated layout and the renamed
  workflows.

### Rust — Changed

- **Almost nothing in the crate's source moved, and what did is one function.**
  Four files under `crates/termproof/src/` differ from the previous release.
  Three carry doc-comment corrections only — `assertions.rs`, `pyschema.rs` and
  `terminal/session.rs`, which referred to a `harness/` directory since renamed
  to `conformance/` and to a two-repository layout that no longer exists. The
  fourth is `schema.rs`, and its change is described under *Rust — Fixed*
  below. Everything else that moved for Rust is documentation, CI and packaging
  metadata. A consumer upgrading for any reason other than
  `load_canonical_schema` should expect no behavioural difference.
- **cargo:** `repository`, `homepage` and `documentation` name
  `md-mt/termproof`. They named the Rust-only repository, which no longer holds
  the source, so the links on crates.io and docs.rs pointed at the wrong place.
  This is the substantive reason to publish the crate again.
- **cargo:** `tests/canonical_schema.rs` is excluded from the package. It reads
  `python/docs/recipe-schema-v1.json`, which sits outside the crate, so
  shipping it would put a test in the tarball that cannot pass from there.

### Rust — Fixed

- **release:** the auto-release moves the whole version train. It bumped
  `rust/Cargo.toml` alone, so a release would push a `main` whose Python
  manifest and changelog were left behind and whose own drift check failed.
  `version-bump.py` now moves `python/pyproject.toml` and this file too, and
  the workflow verifies the train before it tags.
- **schema:** `load_canonical_schema` reaches
  `python/docs/recipe-schema-v1.json`. Its candidate paths described
  side-by-side checkouts from before the two implementations shared a
  repository, so it returned `None` everywhere.

  **This is the one behavioural change a consumer of the published crate can
  observe.** The path is resolved from `CARGO_MANIFEST_DIR` alone. One of the
  old candidates was `docs/recipe-schema-v1.json` relative to the working
  directory, so the function could read whatever file of that name happened to
  sit in a consumer's tree and hand it back as TermProof's canonical schema.
  The crate does not vendor the schema, so `None` is the correct answer from a
  registry checkout, and `None` is what it returns. `load_canonical_schema_from_dir`
  is new and doc-hidden; it exists so a test can prove the packaged case.

## [0.3.3] — 2026-08-16

The version at which the two implementations converged. The Rust
implementation had already reached 0.3.3 on its own count, so the Python
package moved onto that number rather than continuing to 0.3.1. The Python
package released nothing as 0.3.1 or 0.3.2 — the entries under those headings
below are the Rust implementation's, and nothing is missing from this file.
From here a version number means the same point in the project's history for
both.

### Python — Added

- **An `ArtifactPublisher` plugin protocol.** Where evidence goes is now an
  extension point like every other part of the pipeline, registered under the
  `artifact_publishers` config key and selected by name. A publisher implements
  `publish(source, key) -> PublishedArtifact`: the caller decides the key layout,
  because that is the shape of the evidence rather than a property of any store,
  and the publisher maps the key onto its own namespace and onto a public URL.
  The result is a record rather than a bare URL because publishing is not the
  last step — reports link evidence by local path, so rewriting those links
  needs the source and the URL together, which `url_map_from_published` builds.
  A publisher reports `published=False` when it did not transfer the bytes and
  an empty `url` when it did but cannot address them, so neither has to be an
  exception. Neither is treated as a success either: only an artifact that is
  both published and addressable is rewritten into a report, `publish-videos`
  reports each declined artifact with its `detail`, records only what was stored
  in `video-manifest.json`, and exits non-zero if anything was declined — a
  batch that stored most of its evidence and quietly dropped the rest is the
  same false success as one that stored none. Report links are rewritten to the
  URLs the selected publisher reported rather than to a predicted S3 layout, so
  no store's address scheme can speak for another, and `--dry-run` is refused by
  a publisher that takes no target, since it would never see the flag and would
  publish for real. The existing S3/R2 path is the first implementation
  (`termproof.evidence_publish:S3ArtifactPublisher`, registered as `s3`) rather
  than a parallel special case, and `publish-videos` gained `--publisher` to
  select another one; `--bucket` is a precondition of that publisher rather than
  of publishing, so another one may run without it. Publishing behaviour is
  unchanged: same keys, same URLs, same report rewriting, same failure when
  neither the AWS CLI nor boto3 is installed. A configured publisher is imported
  when it is asked for rather than when a runner is built, so a store that
  nothing publishes to cannot break an ordinary run. Deployment settings reach a
  publisher through an optional
  `from_target` classmethod, mirroring `from_config` for renderers, so
  credentials stay out of the checked-in config file. See
  `python/docs/plugin-protocols.md`.
- **Assertions can read the screen captured after each step.** Until now an
  assertion saw only the final screen, which makes anything about a state the
  run passes through and then leaves — a dialog that was dismissed, a mid-flow
  confirmation — inexpressible. The data already existed: `StepResult` carries a
  per-step `screen`, and the scripted execution modes simply did not pass it on.
  They now do, via a new `steps` argument on `VerificationRunner.evaluate_assertions`
  and on assertion evaluation, plus a `StepAwareAssertionType` protocol exported
  from `termproof.protocols` alongside the existing nine. The new built-in
  `step_screen_contains` assertion takes a `step` name and a `value` substring
  and reads that step's screen.

  The change is additive: TermProof passes `steps` only to an `evaluate` that
  declares a parameter of that name, so an assertion written against
  `AssertionType` is still called with the original five arguments and keeps
  working without source changes. A bare `**kwargs` deliberately does not count
  as opting in, so an assertion that forwards unrecognised arguments to another
  one written against the older signature cannot break either. `steps` is
  keyword-only with a default of `None`, which also lets a step-aware assertion
  run unchanged on a TermProof that never passes it — `None` means the execution
  mode supplied no per-step screens, which is not the same as a run in which no
  step ran. See `python/docs/plugin-protocols.md` and the `StepScreenMatches` example in
  `plugin-template/`.

### Rust — Added

- **Community-health and maintainer contracts**, a rebuilt public entry point,
  and a repository governance baseline (`#38`, `#40`, `#44`).

### Rust — Changed

- **ci:** CI, dependencies and release verification hardened; the crates.io
  publish environment named, and a container image published (`#41`, `#45`).
- **schema:** `generate_recipe_schema` output pinned to a checked-in snapshot
  (`#39`).

This release was cut from the predecessor repository, before consolidation,
and its entry was never written there. The list above is reconstructed from
the release notes; the commit list is on that release.

## [0.3.2] — 2026-08-15

### Rust — Changed

- **cargo:** JUnit output gets its own feature, so a consumer who only wants
  JUnit stops paying for the evidence renderers (`#36`).
- **cargo:** the portable-pty and unicode-width floors are documented from
  outside, so the reason each floor sits where it does is legible without
  reading the code (`#35`, `#37`).
- **evidence:** the JUnit writer moves to its own module (`167cc96`).

## [0.3.1] — 2026-08-14

### Rust — Added

- **cargo:** `schema` — schemars moves behind a default-on feature, so a
  consumer that does not need schema generation stops compiling it (`#28`).
- **cargo:** default-on `evidence` and `json-schema` features, so a consumer
  compiles only what it uses (`#31`).
- **terminal:** `Session::cwd()`, reporting where the child process actually
  went (`#30`).

### Rust — Changed

- **cargo:** every version requirement is now a tested floor — CI pins each
  widened requirement to its floor and runs the suite against it, so a floor
  that stops being true fails CI rather than rotting (`#32`).
- **steps:** type inference names the regex `Captures` type instead of a
  concrete version of it (`d23c727`).

## [0.3.0] — 2026-08-14 (Rust), 2026-08-16 (Python)

### Python — Added

- **An attributed screen model, and colour in `final.svg` and the
  `attributed_rsvg` video.** `termproof.attributed` keeps a per-cell grid —
  foreground and background, bold, italic, underline, strikethrough, reverse,
  and double-width handling — instead of a flat string. The SVG renderer emits
  one `<text>` per cell positioned at `x = col * cell_w`, so column alignment no
  longer depends on whichever font the viewer resolves, and a red error no
  longer renders identically to ordinary prose. A grid can be read from a live
  `pyte.Screen` (`screen.screen_attributed`), from a recorded cast
  (`screen.replay_cast_attributed`), or parsed out of text that still carries
  SGR escapes. Canvas geometry is unchanged: for the default 80x24 the old and
  new formulas both give 756x516.

  Two limits, both pinned by tests rather than left to be discovered:

  - **Per-step screenshots are not included.** `final.svg` and the
    `attributed_rsvg` video render from the grid and carry colour; the images
    under `steps/` render from `StepResult.screen`, which is pyte's
    already-flattened `display`, so they are still monochrome. On the shipped
    recipes that is 124 of the 146 regenerated corpus SVGs.
  - **Dim (SGR 2) does not survive the cast-replay path.** pyte 0.8.2's `Char`
    has no dim/faint field, so the attribute is consumed by the emulator before
    the grid is built. A grid parsed directly from SGR text does carry dim.
    Supporting it on the replay path means modelling SGR 2 in the emulator
    layer.

  See `python/docs/evidence-quality.md` for both.
- **An optional `render_attributed` method on the renderer protocol.** A
  renderer that defines it is handed the grid instead of text. Additive: a
  renderer written against the text-only protocol keeps working unchanged. See
  [`python/docs/plugin-protocols.md`](python/docs/plugin-protocols.md).
- **`png_rsvg`, a PNG renderer that rasterizes the attributed SVG.** Unlike the
  Pillow-based `png` renderer it keeps colour and styling, and it cannot drift
  from the `svg` output because it renders the same document. Needs
  `rsvg-convert`; `png` remains the default. Every external call goes through a
  `ToolRunner` seam, so a host with its own subprocess policy can supply one.
- **`attributed_rsvg`, a video backend that renders frames from the same
  attributed grid `final.svg` uses.** A video frame and the final screenshot of
  the same moment are then the same image. Not the per-step screenshots, which
  are still rendered from plain text. Slower than `agg_ffmpeg` — one rasterizer
  call per *distinct* frame — and encodes `yuv444p` rather than `yuv420p`,
  because 4:2:0 chroma subsampling smears the edges of coloured text.
  `agg_ffmpeg` remains the default.
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
  either way. See `python/docs/evidence-quality.md` for the research behind the
  recommended values.

### Python — Changed

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
- **The rendered corpus under `python/examples/artifacts/` is regenerated.** All 146
  checked-in SVGs differ, because the markup shape changed from one `<text>` per
  line to one per cell. No session was re-recorded — the `session.cast` files
  are untouched and the only input that changed is the renderer. A recorded run
  of `python/examples/colorstress` joins the corpus as the entry that can catch a
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

### Python — Fixed

- **The `tmux` backend recorded casts with every carriage return stripped.** The
  `pipe-pane` fifo was read in Python's default text mode, whose universal-newline
  translation rewrites `\r\n` to `\n` and a bare `\r` to `\n`. Nothing looked
  missing — every glyph and every escape sequence was recorded — but replaying
  the cast never returned the cursor to column 0, so `final.svg` and `final.txt`
  came out as a diagonal staircase and `\r`-redrawn progress lines were lost.
- **`attributed_rsvg` now names what to install when a tool is missing.** It
  reported which of `rsvg-convert` / `ffmpeg` it could not find but not what to
  do about it, unlike `png_rsvg`, which already named the alternative.
- **`attributed_rsvg` holds the closing frame.** `evidence.video.last_frame_duration`
  reached `agg_ffmpeg` but not this backend, so the final screen — the state the
  run ended in — occupied a single frame, 42ms at 24fps. It is now held for 3.0s
  by default, matching agg. A frame identical to the one before it is written by
  copying the rendered PNG rather than rasterizing again, so the hold, and any
  idle stretch, costs disk instead of rasterizer calls.

### Python — Removed

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
  - `rust/docs/rust-reimplementation-spec.md`, `python/docs/rust-gates.md` and the docs-site
    Rust pages are gone; `/rust/` now explains the move.

  **There is no replacement yet.** `termproof-rust` has not published a release
  and has no parity gate — a differential harness found the two implementations
  agreeing on 55 of 217 cases. The Python implementation, which is what every
  install channel has always shipped, remains the only supported engine.

### Rust — Added

- **evidence:** `EvidenceCollector`, an ordered step model beside `RunResult`
  (`#26`).
- **terminal:** `SessionDriver`, a scenario-facing layer over `Session`
  (`#23`).
- **result:** the `RunResult` payload is versioned, with an absent version its
  own rule (`#22`).

### Rust — Changed

- **evidence:** one SVG renderer behind both stills and video — the change
  that bumped the minor digit under the pre-1.0 rule (`#19`, `#25`).
- **terminal:** `dim` is carried through the vt100 path (vt100 `0.15` →
  `0.16`) (`#21`).
- **docs:** conditional recipes are declined, and the docs say what a consumer
  with a branching scenario uses instead (`#24`).

## [0.2.1] — 2026-07-29 (Python), 2026-08-13 (Rust)

### Python — Added

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

### Python — Changed
- **Stabilized plugin protocol API** for steps, assertions, and backends (#50).
- **Pages deploy is now opt-in** (#67).
- **PyPI release publishing is now opt-in** via `ENABLE_PYPI` (#71).

---

### Rust — Added

First release of the Rust implementation, covering everything from the
workspace seed through the release automation (`#14`).

- **release:** weekly auto-release that only fires on real change, and a
  complete GitHub Release (`#14`).
- **cargo:** every crate made publishable to crates.io, with the publish set
  and order derived from `cargo metadata` rather than a maintained list
  (`#11`).
- **core:** the eight built-in assertions, measured against the Python oracle
  (`#10`).
- **execution:** `PtySession` is a `Session`, and `termproof run` runs recipes
  against a real child (`#9`).
- **terminal:** the terminal layer is real — children run on a real
  pseudo-terminal via `portable-pty`, and the screen is a `vt100` cell grid
  that interprets escapes instead of stripping them (`#6`).
- **core:** assertions get the screen captured after each step (`#5`).
- **spec:** Spec Kit adopted and the core verification semantics specified
  (`#4`).

### Rust — Changed

- **refactor:** `termproof-core`, `termproof-terminal` and `termproof-evidence`
  merge into one crate named `termproof` before any of them is published
  (`#13`).
- **core:** the five step-layer defects fixed, each with a test that failed
  first (`#7`).

## [0.2.0] — 2026-07-26

### Python — Added

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
- **Launch kit** (`python/docs/launch/`): HN Show post draft, outreach templates for 5 TUI frameworks (Bubble Tea, Ratatui, Textual, Ink, Charm), social media profiles and assets, launch runbook, pre-flight checklist
- **Contributing guide** and **Code of Conduct**
- **Verified by TermProof badge** for downstream projects

#### CI/CD
- GitHub Actions CI workflow: lint, type-check, test matrix (3.11, 3.12, 3.13), build verification
- Trusted publishing to PyPI via GitHub release trigger
- Release workflow with attestation

### Python — Changed

- **Renamed from TUI Verifier to TermProof** (#42). Package, CLI entry point, docs, and all internal references updated.

### Python — Known limitations

- Bundled `agg` binary distribution is deferred to v0.2.1. Users need `agg` installed separately for video rendering (`--video` flag).
- Video rendering requires `agg` (from asciinema) and `ffmpeg` on PATH.
- The launch kit outreach templates reference canonical artifact paths that may shift before launch day.

---

## Before 0.2.0

All work prior to 0.2.0 was in the TUI Verifier codebase, which is what the
Python implementation was called before the rename. Key milestones:

- **Config system + Step/Assertion plugin registry** — YAML config, entry-point-based plugin loading
- **Reporter + Screen Renderer registries** — pluggable output and rendering backends
- **Execution Mode + Agent Runner registries** — execution strategies, agent-driven test mode
- **SessionBackend + VideoBackend** — recording and video rendering integration
- **Agent-driven mode** — AI agents can drive the TUI via structured interaction
- **Engineering design documentation** — architecture, extension points, data flow
