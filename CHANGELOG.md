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
- **Write entries in the past tense, about the release they sit under.** A
  released section is a record of what that version did, and it is never
  rewritten to match the present — that would destroy the one job it has,
  telling someone on an old version what changed and when. But this file is
  also read for current behaviour, so a present-tense entry ("the crate does
  not vendor the schema") goes on reading as a claim about now long after a
  later release made it false. Past tense keeps the record intact and stops it
  being mistaken for a statement about the current tree. Three entries under
  `[0.3.4]` had to be re-tensed for exactly this reason (#174).
- **Below 0.3.3 the two counts were independent**, so those headings can carry
  two release dates for one number. From 0.3.3 the counts are the same.

## [Unreleased]

### Docs

- **Both READMEs now say that `EvidenceCollector.capture_text` is the one
  collector signature the two implementations do not share.** Rust takes the
  `CaptureKind` positionally and Python defaults it to
  `CaptureKind.CHECKPOINT`; each is idiomatic where it sits, and neither README
  mentioned the method at all, so a reader carrying the symmetry the rest of
  the surface has would have carried it here too and been wrong. Reported by a
  consumer running both implementations against the same collector code. The
  signatures are unchanged — the Python default is now covered by an assertion
  in `test_text_can_be_captured_without_a_source` rather than only being
  exercised.

### Python — Added

- **`termproof.models.score_from` and `termproof.models.assertion_map`:**
  `score_from` scores a name → passed mapping the way `RunResult.score` is
  defined — the fraction that held — and `assertion_map` builds that mapping
  from `(name, passed)` pairs, last pair for a name winning. Consumers were
  each writing those four lines, which was fine for the arithmetic and not fine
  for the one decision inside it: **a run that asserted nothing scores `1.0`,
  not `0.0`**, and a consumer that chose the other way published numbers that
  looked comparable to these and were not. That choice is now stated in the
  `RunResult` docstring and in `spec/003-builtin-assertions/spec.md` FR-022,
  as part of the result contract rather than as a note on one function.
  `score_from_assertions` is unchanged in behaviour and now delegates to the
  same rule; the difference between the two shapes is that a list weighs
  duplicate names once each and a mapping folds them into one entry.

- **`termproof.collector.EvidenceCollector.record_session`:** the wiring 0.4.0
  left out. `Recording`, `attach_recording`, the cast-to-video backends and the
  upload seam all existed; nothing joined them, so every consumer that wanted a
  video of a whole run wrote the same five-step sequence itself. This is that
  sequence: save the live session's cast through a caller-supplied callable,
  append the captured checkpoints to it with `append_checkpoint_frames`,
  convert it to a video, upload the video, and attach a `Recording` that
  `publish` then writes into the manifest.

  **The error handling is the part worth having upstream, and it is a stated
  rule rather than an accident of control flow: a step runs only when the step
  before it produced the thing it works on.** A cast that could not be saved
  leaves nothing to append to, convert or upload, so steps 2–4 are skipped; an
  append that failed leaves the cast on disk and still convertible, so it is the
  one non-fatal step; **a conversion that failed leaves nothing to upload, so no
  upload is attempted** — reporting a store error for a video that was never
  encoded is exactly what two independent consumer implementations got wrong.
  No failure a step *reports* raises: a recording is evidence about a run, not
  part of its verdict. Every failure instead lands on the `Recording`'s `error`,
  prefixed with the name of the step that produced it — `save cast`,
  `append checkpoint frames`, `convert` or `upload` — and two failures in one
  call are joined with `"; "` so neither is lost. The promise stops where
  `Exception` does: a `KeyboardInterrupt` or `SystemExit` from one of the three
  caller-supplied seams propagates and the recording is lost rather than
  degraded, which the docstring now says outright.

  **A step is not believed, it is checked.** Each of the three seams is
  caller-supplied, and the outcome worse than any recorded failure is a
  `Recording` that reports none — no `error`, a `video` that is not on disk, and
  a `url` for it. So a `save_cast` that returns having written no file, a
  converter that returns a path it did not write, and an uploader that returns
  an empty string are each recorded as *that* step failing
  (`convert: reported success but wrote no file at <path>`, and so on), rather
  than left for the next step to trip over and take the blame.

- **`termproof.collector.EvidencePublisher.video_converter`**, beside the
  existing `renderer` and `uploader`, with `termproof.collector.VideoConverterLike`
  as its protocol. Optional rather than defaulted, because a converter is two
  more binaries on the host; a `record_session` against a publisher without one
  records that as the `convert` step failing, since converting is what it was
  called to do.

- **`termproof.cast_video.RsvgFfmpegBackend.convert`** and `output_path_for`,
  which satisfy that protocol: `render` is the `VideoBackend` method and is
  unchanged, and `convert` supplies the two things it makes a caller invent — an
  output path and a frame rate. The rate is the configured
  `evidence.video.fps`, or `DEFAULT_FPS` when the backend was not built from a
  config, which is the rate Rust's `CastVideoConverter` defaults to.

- **`termproof.cast_video.append_checkpoint_frames`:** appends the captured
  checkpoint screens to a cast as held trailing frames, so a recording ends by
  replaying the evidence sequence instead of stopping on whatever the last
  keystroke painted — one artifact to watch rather than fifteen stills to open.
  Each screen repaints the whole grid — pen, scroll region, cursor and all, so a
  scroll region the recorded TUI left set cannot scroll rows of the evidence out
  of the frame — and is held for `hold_seconds`, defaulting to the three of
  `DEFAULT_CHECKPOINT_HOLD` and floored at the microsecond of
  `MIN_CHECKPOINT_HOLD`, below which two frames would share a timestamp. It
  appends only: the header and every recorded event are left as the session
  wrote them, and the new timestamps continue from the last one in the file
  rather than restarting at zero, so the result is still a valid asciinema v2
  cast. A run that captured nothing is a silent no-op, and nothing about it
  needs the session to still be running.

- **`models.RecipeMeta` and `Recipe.meta`:** the same seven descriptive fields
  as the Rust `recipe::RecipeMeta`, with the same defaults, as a frozen
  dataclass a host with an imperative suite can build without a `Recipe` — and
  therefore without inventing a `command`. `Recipe.meta` hands over its own
  descriptive half as one, copying `ci_paths` rather than aliasing it.

  **`Recipe` does not inherit from it**, which is the one place the two
  implementations differ in shape rather than in semantics. Rust embeds and
  flattens; Python cannot, because dataclass inheritance puts base fields
  first, which would move `command` behind six defaulted fields and force it
  keyword-only — changing `Recipe`'s positional signature, a break this package
  states it avoids in `StepResult`'s docstring. `Recipe`'s field list, order,
  defaults and positional signature are therefore unchanged, and pinned by
  `tests/test_recipe_meta.py`, which also holds the two field lists to the same
  names and defaults since nothing in the language does.

  Selection needed nothing: `selection.select_names` has always taken
  `(name, ci_paths)` pairs, so the gap `Selectable` closed on the Rust side in
  0.4.0 never existed here.
  ([#199](https://github.com/md-mt/termproof/issues/199))

### Python — Changed

- **evidence:** the step-screenshot dedup was written out twice — once in
  `EvidenceCollector.publish` and once in `evidence._render_step_screens` —
  and the two copies shared no code, so nothing stopped them drifting on what
  counts as a changed screen. Both now ask the new `termproof.dedup.Deduper`,
  which is the single copy of the rule. `termproof.dedup` mirrors
  `termproof::evidence::dedup`, where the Rust implementation has kept the rule
  in one place since the consolidation; the Python package flattens the Rust
  `evidence::` namespace into top-level modules, so it lands beside
  `termproof.collector` rather than inside `termproof.evidence`.

  Nothing observable moved. `render_artifacts` writes the same `steps/` layout
  and the same `steps-manifest.json`, still gated on
  `evidence.dedup_step_screenshots` and still off by default; `publish` writes
  the same `evidence.json`, byte-for-byte — `conformance/probe_evidence_manifest.py`
  reproduces the committed corpus unchanged. The two file layouts are still
  separate, and folding one into the other is still a compatibility question of
  its own rather than something to smuggle into a dedup fix.

  Both module docstrings now say plainly which type owns what:
  `EvidenceCollector` owns capture-while-running, `render_artifacts` owns
  rendering a finished `RunResult`, and neither owns the dedup.

- **This release changes rendered screenshots.** `SvgStyle` and
  `SvgRenderConfig` both described SVG geometry and their defaults disagreed in
  every single field. `SvgStyle` is now the single canonical definition and
  `SvgRenderConfig` takes each default from the same `DEFAULT_*` constant in
  `termproof.attributed` instead of restating it, so an unconfigured
  `screen_svg(screen, SvgStyle())` and an unconfigured `SvgRenderer` finally
  produce the same image. What moved, on the `evidence.svg` side:

  | key | was | is |
  |---|---|---|
  | `char_width` | `9` | `10.0` (`DEFAULT_CELL_W`) |
  | `line_height` | `20` | `22.0` (`DEFAULT_CELL_H`) |
  | `font_size` | `14` | `16` (`DEFAULT_FONT_PX`) |
  | `padding` | `18` | `10` (`DEFAULT_PADDING`) |
  | `bg` | `#101418` | `#0b0f14` (`DEFAULT_BG`) |
  | `font_family` | `ui-monospace,SFMono-Regular,Menlo,Consolas,monospace` | `Noto Sans Mono, Liberation Mono, monospace` (`FONT_STACK`) |

  A 120x40 screen was 1116x836 and is now 1220x900. `fg` did not move. To keep
  the old output exactly, pin all six in `.termproof/config.yaml` — **and, if
  any screen is narrower than 32 columns or shorter than 7 rows, the two floor
  keys with them**, because below that the old canvas was 320x160 and the six
  above cannot restore it on their own:

  ```yaml
  evidence:
    svg:
      char_width: 9
      line_height: 20
      font_size: 14
      padding: 18
      bg: "#101418"
      font_family: "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"
      # Only needed below 32 columns or 7 rows, where the old floor bound.
      min_width: 320
      min_height: 160
  ```

  `min_width`/`min_height` are new `evidence.svg` keys, added so that recipe is
  exact at every grid size — see the floor entry below.

  Note that pinning `font_family` restores a stack naming three fonts that
  exist on macOS and Windows and none that exist on a stock Linux image. It
  collapses to generic `monospace` there, and `Menlo` resolves to
  *proportional* DejaVu Sans on some images, which overflows the cell grid the
  attributed renderer is built on. That is why the canonical stack names
  `Noto Sans Mono` and `Liberation Mono` ahead of the generic fallback.

  `char_width` and `line_height` are now typed `float` rather than `int`, which
  widens what they accept; an integer in YAML still loads.

- **The SVG canvas has no minimum size; every rasterised one still does.**
  `SvgRenderConfig.style()` used to set `min_width: 320, min_height: 160` while
  `SvgStyle`'s own defaults were `0` — a third disagreement, invisible at 120x40
  because the floors do not bind there. The vector path is floorless now, so an
  SVG is exactly `grid + 2 * padding` at any size: a 3x2 grid renders 50x64, not
  320x160. A viewer scales an SVG, so a floor there only surrounds a small grid
  with dead background.

  That argument stops at the rasterisers, and all three keep the 320x160 floor
  they had: `PngRenderer`, the `png_rsvg` renderer, and the `attributed_rsvg`
  video backend. The last two call `rsvg-convert` with no `-w`/`-h`/`-z`, so it
  renders at intrinsic size and the PNG's pixel dimensions *are* the SVG's
  `width`/`height` — a 20x4 grid would have become a 220x108 postage stamp.
  `SvgRenderConfig.raster_style()` is the one place that floor is applied and
  `RASTER_MIN_WIDTH`/`RASTER_MIN_HEIGHT` in `termproof.config` are the one place
  the two numbers are written down, `PngRenderer` included.

- **`evidence.svg.min_width` and `evidence.svg.min_height` are new keys**, both
  defaulting to `0`. They make every `SvgStyle` field reachable from YAML, which
  is what lets the pin-the-old-output recipe above be exact below the old floor.
  On the two renderers that rasterise that SVG — `png_rsvg` and the
  `attributed_rsvg` video backend — they raise the floor but cannot lower it
  below 320x160. They do not reach the `png` renderer, which is configured by
  `evidence.png` and keeps its own fixed 320x160 floor; making one knob govern
  both would mean giving `PngRenderConfig` its own pair, which is a separate
  change.

- **`evidence.png.fg` and `evidence.png.bg` follow the same palette**, moving
  `bg` from `#101418` to `#0b0f14`, so the PNG and SVG screenshots of one run
  no longer disagree about what colour the terminal is. `png.padding`,
  `png.font_size` and `png.scale` are unchanged — they are raster quantities
  with no SVG counterpart. Pin `evidence.png.bg: "#101418"` to keep the old
  PNG background.

- **The checked-in evidence corpus under `python/examples/artifacts/` was
  regenerated** — 156 SVG files, which is what the new geometry looks like.
  `CorpusByteIdentityTest` requires exactly that of any change to the defaults,
  so the new bytes are in the diff rather than in a later surprise.

- `BUILTIN_DEFAULTS["evidence"]` is now read off the config dataclasses with
  `asdict()` rather than restating each default beside the field that declares
  it. `python/README.md` points at that dict as the documentation of every
  knob, so it could not be allowed to drift from the values a renderer applies.

- An out-of-range `evidence` value now reports its bound —
  `evidence.svg.char_width must be at least 1, got 0.5` — rather than naming a
  class of number. `char_width` and `line_height` accept a float, so the old
  "must be a positive integer" was wrong for them, and `0.5` satisfies
  "positive" while still being refused.

### Rust — Added

- **`result::score_from` and `result::assertion_map`:** the same two functions
  with the same semantics, `score_from` taking `&BTreeMap<String, bool>` and
  `assertion_map` collecting `(impl Into<String>, bool)` pairs. The empty-map
  case is `1.0` here too, and is documented on `RunResult::score` — the field
  the number ends up in — rather than only on the function that computes it.

- **`evidence::collector::EvidenceCollector::record_session`:** the same five
  steps with the same semantics and the same rule about which of them run after
  a failure, taking `save_cast: FnOnce(&Path) -> Result<(), String>` where
  Python takes a callable that raises. It returns nothing rather than a
  `Result`, for the reason nothing on the Python side raises: no failure a step
  reports may fail the run. `&mut self`, because it appends a `Recording`;
  `publish` stays `&self`. The four step names it prefixes an error with are the
  same four strings both implementations write, which the conformance pair now
  compares.

- `with_video_converter`, beside the existing `with_renderer` and
  `with_uploader` and in the same builder style. The field it sets is the
  breaking part above.

- **`evidence::cast_video::append_checkpoint_frames`:** the same capability with
  the same semantics, taking `hold_seconds: Option<f64>` where Python takes a
  defaulted keyword and returning `Err` where Python raises `ValueError`. The
  two write byte-identical events for the same screens: the Python encoder is
  pinned to `serde_json`'s compact, raw-UTF-8 shape, its six-decimal rounding
  transcribes Rust's expression rather than calling `round(at, 6)`, which breaks
  halves the other way, and the evidence-manifest conformance pair now compares
  two appended casts — one at the default hold, one at a fractional one that
  needs the rounding — alongside the step files.

- **`recipe::RecipeMeta`:** the seven fields that describe a recipe — `name`,
  `description`, `intent`, `priority`, `execution`, `determinism`, `ci_paths` —
  as a type that can be constructed on its own. They describe a scenario the
  same way whether it is driven declaratively or by a consumer's own runner,
  but they used to be reachable only by constructing a `Recipe`, which needs a
  `command` an imperative suite has no single honest value for; one such
  consumer re-declared all seven, field name for field name. `RecipeMeta::new`
  takes a name and fills the rest from the same functions `serde` uses for the
  file defaults, so hand-built and parsed metadata cannot drift. It implements
  `selection::Selectable`, so selection by `ci_paths` came free for those
  consumers rather than needing a trait impl of their own. Re-exported at the
  crate root as `termproof::RecipeMeta`, the way every other public type in
  `recipe` is — the consumer this is for is the one whose `Recipe { .. }`
  literal just stopped compiling, and asking them to also discover a
  sub-module path would be a second papercut on top of the first.
  ([#199](https://github.com/md-mt/termproof/issues/199))

- **`run_config::cli`, behind the new opt-in `clap` feature:** the command line
  that fills in a `RunConfig`. `run_config` has modelled a whole run since it
  landed — `RunConfig`, `Discovery`, `Selection`, `Execution`, `BinarySource`,
  `Output`, `Publisher`, `Requirements`, and `pick(flag, configured, builtin)`
  for how the three sources of an answer rank — but nothing populated it from
  argv, so each consumer wrote that layer again. Measured on one of them, a TUI
  validator: 23 `clap` argument builders and about 200 lines whose only job was
  to get from flags to this crate's own type, with `pick()` re-derived by hand
  once per flag (#197).

  Six functions, re-exported at the `run_config` root:
  `clap_command()` for the standard flags on a bare command;
  `augment_args(Command)` for adding them to a consumer's own, so extra `.arg()`
  calls compose and the consumer keeps its name, version and subcommands;
  `from_matches(&ArgMatches)` for exactly what the flags said;
  `configured(&ArgMatches)` for the file `--run-config` names;
  `merge(flags, configured, builtin)` for `pick()` applied to every field at
  once; and `resolve(&ArgMatches, builtin)` for all of it in one call.

  Two rules are load-bearing and are asserted rather than described. No flag
  carries a `default_value` — a defaulted flag is indistinguishable from a
  passed one, and if the two look alike a config file can never override one,
  which is what `run_config`'s precedence section warned about; the built-in
  therefore arrives as the `builtin: &RunConfig` argument. And a flag passed
  empty is a flag passed: `--renderer ''` beats a configured renderer, because
  reading it as unset would add a fourth state to `pick()`'s three and put every
  consumer back to remembering which flags have it.

  **One field does not obey that precedence, and it is deliberate.**
  `Requirements.uploaded_media` is a `bool`, so it has no unset state for
  `pick()` to rank and the three layers are ORed instead: any of them asking for
  it is asking for it. It can therefore be raised but never lowered —
  `require: {uploaded_media: false}` in a config file is inert against a
  built-in `true`, and there is no `--no-require-uploaded-media`. For a
  requirement that is the safe direction to fail in, since a config file quietly
  switching off a "the evidence must be shareable" gate is the outcome worth
  preventing, but it is an exception to the rule rather than an instance of it:
  a caller that needs the gate off has to leave it off in the built-in. The
  repeatable flags behave differently again — for those, empty is unset, and the
  first non-empty of flag / config / built-in wins as a whole rather than
  merging, so a passed `--env` replaces a configured `env` outright.

  **Reconciled against `termproof.cli`.** Where the two name the same thing they
  use the same flag: `--priority`, `--recipe-name` (repeatable in both) and
  `--renderer`. The rest is new, and no name is reused for a second meaning:

  | This layer | Python's `termproof.cli` | Why |
  |---|---|---|
  | `--run-config PATH` | `--config PATH` is the *plugin registry* (`VerifierConfig`) | Two different config files. Reusing `--config` would be the one collision worth avoiding, and a consumer that has both still needs to name each. |
  | `--artifact-dir DIR` | `--out DIR` | Not the same thing. `--out` is one directory that the report path is also derived from; `RunConfig` separates `artifact_dir`, `report_path` and `result_json_path`, so no flag here has `--out`'s meaning. |
  | `--all`, `--changed-files` | — | `Selection` has four arms; Python's CLI exposes two of them. All four get a flag, in one `ArgGroup`, so "all *and* a priority" is a usage error rather than something this layer has to rank. |
  | `--priority` **with** `--recipe-name` is a usage error | the two compose | The one divergence that is not about a name. `termproof.registry.select_recipes` applies priority and then names as successive filters, so `--priority P0 --recipe-name smoke` is a legal narrowing there — "smoke, if it is P0". `Selection` holds one arm, so the same pair is an `ArgumentConflict` here. Same names, same individual meanings, different composition, which is exactly the case a ported command line trips over; a caller wanting the intersection filters a `Selection::Priority` run itself. |
  | `--root`, `--repo-marker`, `--exclude`, `--transport`, `--model`, `--effort`, `--binary-installed`, `--binary-build`, `--env`, `--timeout-scale`, `--publisher`, `--publisher-setting`, `--require-uploaded-media`, `--require-media-publisher` | — | Fields `RunConfig` has and Python has no counterpart for. |

  The feature is off by default, so a consumer that does not name it does not
  compile `clap`. CI's feature powerset is enumerated from the feature list, so
  it grew from sixteen combinations to thirty-two by construction, and both the
  default build without `clap` and every build that names it are exercised.

  Python is deliberately unchanged. `run_config` is Rust-only — there is no
  `termproof.run_config`, and the conformance pair has nothing to compare —
  so this closes an asymmetry rather than opening one. `termproof.cli` is an
  `argparse` *program*; this is a library layer, and no binary is added.

### Rust — Changed

- **scoring:** `assertions::score` and `RunResult::score_from_assertions` were
  two hand-written copies of the same arithmetic, and `result::score_from`
  would have made a third. All three now call one private rule in `result`.
  Nothing observable moved — the assertion differential harness reproduces the
  committed corpus, `score` cases included — and the point is that the
  empty-set answer can no longer drift between them.

- **`Recipe` holds its descriptive fields in a `RecipeMeta` and flattens it.**
  Nothing moved on the wire: a recipe file parses the same, serialises to
  byte-identical text with the same key order, and generates a byte-identical
  JSON Schema — pinned by `tests/recipe_meta.rs`, which asserts the exact
  serialised strings recorded from the pre-split tree, and by the existing
  `schema_snapshot.rs`, which still reaches through the flattened type.

  **What breaks:** Rust code that names `recipe.name`, `recipe.priority` or any
  of the other five reads them through `recipe.meta` now, and a `Recipe { .. }`
  literal has to supply `meta` instead. `cargo semver-checks` reports it as
  `struct_pub_field_missing` and `constructible_struct_adds_field` and asks for
  a major bump, which under this project's pre-1.0 rule is the minor digit. A
  `Deref` from `Recipe` to `RecipeMeta` would have kept field *reads*
  compiling; it was declined, because it would not have saved the literals or
  quietened `semver-checks`, and it would have put a smart-pointer conversion
  on a plain data type to hide a break rather than state it. In this repository
  the change touched three assertions and one trait impl.

  **The version did not move.** This break ships on 0.4.x by maintainer
  decision, waived rather than versioned, through the same mechanism #196
  established: `struct_pub_field_missing = "allow"` joins
  `constructible_struct_adds_field` under
  `[package.metadata.cargo-semver-checks.lints]`, with the decision and the
  release line it was granted for recorded beside it. The waiver is scoped to
  a lint rather than to a struct because that is the only granularity
  cargo-semver-checks offers, so — exactly as in #196 — two tests bound it:
  `every_public_field_of_the_recipe_is_accounted_for` names every field of
  `Recipe` in an exhaustive literal, so no field of the struct the waiver was
  granted for can arrive or leave silently while the lint is off, and
  `the_recipe_semver_waiver_is_scoped_to_the_release_it_was_granted_for` fails
  the build the moment the version leaves 0.4.x. `docs/publishing.md`'s
  release checklist lists both waivers.
  ([#199](https://github.com/md-mt/termproof/issues/199))

- On SVG geometry, nothing. `SvgMetrics` in `terminal::attributed` already took every default
  from the `DEFAULT_*` constants beside it, `ScreenshotRenderer` and
  `CastVideoConverter` already referenced those same constants rather than
  restating them, and the Rust stack was already the Linux-first one — the
  Python defaults moved *onto* the values Rust has been rendering all along.
  The two implementations agree on SVG geometry for the first time. Rust has no
  `min_width`/`min_height` concept, which is the behaviour both now have on the
  vector path.

  Rust's raster path is *not* floored, and was not before this change either:
  `ScreenshotRenderer::render` and `CastVideoConverter` both invoke
  `rsvg-convert --output <png> <svg>` with no `-w`/`-h`/`-z`, so a small grid
  rasterises small. Python's raster renderers have floored at 320x160 since
  they existed, so the two already disagreed here; this release restores that
  status quo rather than changing it. Giving `SvgMetrics` a raster floor to
  match is worth doing and is deliberately not done here — it would change what
  Rust renders, in a release that changes no other Rust rendering behaviour.

### Rust — Changed (breaking)

- **`evidence::collector::EvidencePublisher` gained a fifth public field,
  `video_converter: Option<CastVideoConverter>`, which stops the struct being
  constructible by literal.** Every field of `EvidencePublisher` is `pub` and
  the struct is not `#[non_exhaustive]`, so an external crate writing
  `EvidencePublisher { dir, identity, renderer, uploader }` no longer compiles;
  `cargo semver-checks` reports it as `constructible_struct_adds_field`. Nothing
  else about the type moved — the four existing fields keep their names, types
  and meanings, and `EvidencePublisher::new` plus the `with_*` builders
  (`with_renderer`, `with_uploader`, and the new `with_video_converter`) compile
  unchanged.

  **To fix a literal, build through the constructor**, which is what every
  in-tree caller and every doc example already does:

  ```rust
  // was
  let publisher = EvidencePublisher { dir, identity, renderer, uploader: Some(u) };
  // now
  let publisher = EvidencePublisher::new(dir, identity)
      .with_renderer(renderer)
      .with_uploader(u);
  ```

  Filed as breaking rather than as an addition because the pre-1.0 rule in this
  file's preamble is about what a consumer's source does, not about what the
  crate meant to offer. The seam had to hang somewhere, and the alternative
  shape — passing the converter to `record_session` instead of the publisher —
  would have avoided the break at the cost of putting one of the publisher's
  three seams somewhere other than the publisher. That trade is worth stating;
  it is not free either way.

  **The version does not move for it.** The pre-1.0 rule above says a breaking
  change bumps the minor digit; the decision on [#196](https://github.com/md-mt/termproof/pull/196)
  is that termproof stays on 0.4.x and this break is waived instead. So
  `constructible_struct_adds_field` is set to `allow` in
  `[package.metadata.cargo-semver-checks.lints]` in
  `rust/crates/termproof/Cargo.toml` — the tool's own scoped mechanism, one
  lint, rather than a version bump or a disabled CI job. **This entry is not
  rewritten to match:** a waiver decides what the version does about a break,
  not whether the break happened, and a consumer whose literal stopped
  compiling needs the paragraphs above whatever the digit says.

  The waiver is scoped in two directions, because at lint granularity it would
  otherwise also cover field additions nobody has decided about:
  `every_public_field_of_the_publisher_is_accounted_for` builds
  `EvidencePublisher` from an exhaustive literal, so a sixth field fails to
  compile, and
  `the_semver_waiver_is_scoped_to_the_release_it_was_granted_for` fails the
  build if the version leaves 0.4.x while the waiver is still in place. The
  release checklist in `rust/docs/publishing.md` now says to read the waiver
  list before reading the green check.

## [0.4.0] — 2026-08-19

### Rust — Changed

- **cargo:** the `fancy-regex` requirement was narrowed to `0.16` from
  `>=0.16, <0.20`. The headroom bought nothing and cost a duplicate. Cargo does
  not unify across `0.x` minors: handed a range it takes the top of it, not a
  copy the graph already holds. Resolved fresh, the old requirement put
  `fancy-regex` 0.16.2 *and* 0.19.0 in this workspace's own lockfile —
  `jsonschema`'s copy and ours — and only the committed lockfile, written when
  the requirement was narrower, kept the pair out of sight. `deny.toml` sets
  `bans.multiple-versions = "deny"` with no skip for `fancy-regex`, so the
  first regeneration of that lockfile would have failed the security job.
  `^0.16` was what `jsonschema` 0.32.1 and 0.33.0 asked for themselves, so a
  default build shared one backtracking regex engine with it by construction.
  Nothing in the crate needed a newer one: the suite and both differential
  harnesses were run at 0.16.0, 0.16.1, 0.16.2, 0.17.0, 0.18.0 and 0.19.0, and
  the parity numbers were identical at every one. The committed lockfile did
  not change — it already resolved 0.16.2.

  **It cost a consumer nothing, which is a property this release had to buy
  first.** While `pyregex::compile` returned a `fancy_regex::Regex`, changing
  this requirement changed which single version a consumer could name that type
  from: under `>=0.16, <0.20` a consumer pinned to 0.19.0 compiled and one
  pinned to 0.16.2, 0.17.0 or 0.18.0 did not, and narrowing would only have
  swapped the ends. With no `fancy-regex` type left in the public API, a
  consumer on any version compiled either way, and the most the requirement
  could cost was a second copy in the graph — which narrowing it removed.
  ([#177](https://github.com/md-mt/termproof/issues/177))

- **ci:** the `test at the declared dependency floors` step was retargeted to
  pin `fancy-regex` to 0.16.0, the bottom of the new requirement, rather than
  to the 0.16.2 the lockfile already resolved — pinning what the lock picks
  would have re-run what the earlier steps already ran. Its comment had also
  claimed the committed lockfile resolves every range to its top, which was
  never true of this entry and is what let the duplicate hide.
  ([#177](https://github.com/md-mt/termproof/issues/177))

### Rust — Changed (breaking)

**No dependency reaches this crate's public API any more, except `schemars`.**
Several did, and each made that dependency's version requirement a
*source-compatibility* surface: two copies of a crate are two unrelated types,
so a consumer naming one compiled only when its copy was the copy cargo handed
us. Widening a requirement did not help — cargo resolves to the **top** of a
range, so the window a consumer could unify with was one version wide however
the range was written.

This is the whole reason 0.4.0 is a minor bump rather than a patch. **If you do
not name any of the types below, nothing changes for you**; calling methods on
the returned values without annotating them compiled before and compiles now.

A signature is not the only door, and this release closed four kinds:

| Door | Was | Now | What to change |
|---|---|---|---|
| return type | `pyregex::compile` gave `fancy_regex::Regex` | `pyregex::PyRegex` | drop the annotation, or write `pyregex::PyRegex`. `is_match`, `captures` and `capture_names` are still there, unchanged in meaning |
| return type | reading a match gave `fancy_regex::Captures` / `Match` | `pyregex::PyCaptures` / `pyregex::PyMatch` | `get`, `name` and `len` are unchanged. `captures.named()` is new and replaces zipping `capture_names()` against `name()` |
| return type | `pyschema::compile` gave `jsonschema::Validator`, and `pyschema::validate` took one | `pyschema::PySchema` | drop the annotation, or write `pyschema::PySchema`. Both functions are otherwise identical |
| argument | `terminal::attributed::from_vt100(&vt100::Screen)` was public | crate-internal | **see below — this one removes a capability** |
| re-export | `termproof::fancy_regex`, `::jsonschema`, `::vt100` | removed | depend on the crate directly and choose your own version. You no longer need ours to match |
| trait impl | `PyRegex`'s derived `Debug` printed the engine's parsed pattern | written out; prints the translated pattern only | nothing, unless you were asserting on the old text |

**`from_vt100` removes a capability, and there is no replacement for it.** It
took the third-party type as an *argument*, and an argument cannot be wrapped —
the caller is what builds it. A caller that already holds a live
`vt100::Screen` now has no public way to turn it into an `AttributedScreen`: it
must replay the bytes through `terminal::screen::TerminalScreen`, which owns
its own parser, and pay for the second parse. `attributed_screen_from_text` and
`attributed_screen_from_ansi_text` are unchanged and never had the problem.
Keeping `from_vt100` public would have meant keeping `vt100` in the API for the
one caller shape that supplies its own parser; that trade went the other way.

**The re-exports were added earlier in this same release and are removed again
before it ships**, so no published version ever carried them. They were an
escape hatch while the types were still leaking — a way to name *our* copy
deterministically. Wrapping the signatures removed the thing they were an
escape from and left them as the last door: a re-exported crate is public API,
so its breaking changes are ours, and `termproof::fancy_regex::Captures` broke
across exactly the range this release narrows.

`schemars` is the one that could not be closed — the `JsonSchema` derives are
on `Recipe` and the types it holds, so the trait sits on published types rather
than in a signature. Turning the `schema` feature off is still the only way out
of carrying two copies.

**What this does and does not claim.** The *declared requirement* on these
crates is no longer a compatibility surface: depend on any `fancy-regex` you
like, ours is an implementation detail of the graph. It is not a claim that the
engine is interchangeable — a backtracking engine's accepted language moves
between releases, and `(?<=a+)b` is rejected at 0.16 and accepted at 0.19 —
which is why the requirement is pinned to one minor and the differential
harnesses are run against it rather than assumed.

- **`select`, `select_names`, `compute_deltas` and `build_before_after` are
  generic.** Each took a concrete slice and read two or three fields of it;
  each now takes `R: Selectable` or `R: Comparable`. Every call that names its
  element type compiles unchanged and resolves to the same types it did before,
  and `BeforeAfterResult` on its own still means `BeforeAfterResult<RunResult>`
  — verified by compiling a consumer that names the bare type in a struct
  field, a return position, an argument, a `let` annotation, a struct literal
  and nested inside another generic.

  **What breaks:** a call that passed an untyped empty literal, as in
  `compute_deltas(&[], &[])` or `select_names(&[], &[], &cfg)`. The element
  type used to be fixed by the signature and is now inferred, and an empty
  literal gives inference nothing to work with. Annotate the slice —
  `compute_deltas(&[] as &[RunResult], …)` — or pass a typed binding. There are
  no such calls in this repository.

  Rust has no default type parameter for a function, so no arrangement of
  defaults avoids this; `cargo semver-checks` reports it as
  `function_requires_different_generic_type_params` and asks for a major bump,
  which under this project's pre-1.0 rule is the minor digit. It therefore
  belongs in the same breaking release as the wrapping above rather than asking
  for a second one.

### Rust — Docs

- **The crate docs used to claim `schemars` was the only dependency reaching
  the public API.** Three others did, and that sentence is why it went
  unnoticed for as long as it did. A new *Dependencies in the public API*
  section replaces it: every door a dependency can reach a consumer through —
  return type, argument, re-export, and what a public trait impl renders — what
  each one was and what closed it, and the resolver behaviour underneath, which
  is that cargo takes the **top** of a requirement's range, so the window of
  versions a consumer can unify with is one version wide however the range is
  written. After 0.4.0 the original sentence is finally true, and for the
  reason it always should have given: `schemars` is the only one left because
  it is the only one that could not be closed.
  ([#177](https://github.com/md-mt/termproof/issues/177))

- **`terminal::attributed`'s module docs no longer list `from_vt100` as a
  source, or as "the usual path".** It has not been public since this release,
  and the doc on the function itself now says plainly that the capability was
  removed rather than relocated.
  ([#177](https://github.com/md-mt/termproof/issues/177))

- **`rust/Cargo.toml` no longer promises that "releases here bump the patch
  digit only".** That described the releases that had happened rather than a
  rule they followed, and this one makes it false. It is replaced with the
  actual rule from
  `rust/docs/publishing.md` — pre-1.0, a breaking change to any public API is a
  minor bump and everything else is a patch — which leaves the `schemars` hold
  standing on the argument that does not depend on a version digit.
  ([#177](https://github.com/md-mt/termproof/issues/177))

### Docs

- **`SECURITY.md` supports the `0.4.x` train.** The version bump has to reach
  every surface that names a version, and the supported-versions table was one
  the bump script does not touch. `0.3.x` keeps its tick alongside it, because
  the train moves *before* the release that puts it on the registries: for the
  window between the two, the newest published artifact is still a `0.3.x` one.
  The "published through `0.3.4`" rows below it are correct and deliberately
  left alone — they are statements about PyPI and crates.io, not about the
  manifest. ([#177](https://github.com/md-mt/termproof/issues/177))

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

- **A published step's `step-NN.txt` no longer gains a trailing newline.** The
  screen is written verbatim, as the Rust implementation writes it. Found by
  running both implementations over one scenario and diffing what they wrote:
  the manifests agreed byte-for-byte and four of the files they pointed at did
  not. Only reachable through `termproof.collector`, which is new in the same
  release, so no published artifact changes shape.

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

- **`EvidenceCollector::capture_text`** records a screen the caller already
  holds. `capture` and `capture_failure` pull from a `ScreenSource`, which
  presumes something live to pull from; text recovered from a log, the screen a
  step returned before the session moved on, or a golden file in a test arrives
  no other way, and recording one meant writing a throwaway `ScreenSource`
  whose only job was to hand back a string. It is a step like any other — same
  sequence, same index, same filename scheme — so the manifest does not develop
  a gap where one was taken. No raw output log is attached even for
  `CaptureKind::Failure`: there is no source to ask for one.

- **`Recording`, `EvidenceCollector::attach_recording` and
  `EvidenceCollector::recordings`** carry whole-session recordings into the
  manifest. A collector's captures are instants; a run also produces a span —
  the terminal recording and whatever video was encoded from it — and a caller
  keeping both had to write a second document beside the manifest and join them
  by convention. The collector does not *produce* recordings: encoding a cast
  is a tool-shelling job with its own failure modes and its own choice of tool.
  One `error` field rather than separate conversion and upload errors, because
  a conversion that failed leaves nothing to upload. `recordings` is
  `skip_serializing_if = "Vec::is_empty"`, so a run that records nothing writes
  byte-for-byte the document it wrote before — which is why
  `EVIDENCE_MANIFEST_VERSION` does not move, and it is asserted by a test.

- **`selection::Selectable` and `before_after::Comparable`** let both modules
  work on results that are not this crate's. A suite whose recipes branch on
  what the screen shows cannot be expressed as a declarative `Recipe`, but it
  has names and `ci_paths` and still has the problem of running everything on
  every change; a caller whose results carry fields this crate does not model
  had to convert to a `RunResult` and back to ask whether anything flipped,
  losing those fields on the way. One accessor per field actually read.
  `(String, Vec<String>)` implements `Selectable` too, so a caller can ask the
  question without writing an impl — that pairing is what the Python
  implementation's `select_names` has always taken.

  No third-party type appears in any of this. `Recording` holds `String` and
  `Option<String>` and derives nothing that reaches past them; `Selectable` and
  `Comparable` are generic over the caller's own types and their accessors
  return `&str`, `&[String]` and `bool`.

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
  (Python)`, whose path filter covers all three copies, so a pull request that
  can change one runs it; in the `gate` job of `Publish crates (Rust)`, which
  runs on every `rust/**` pull request; and in all four release paths — Python
  release, Rust release, Rust publish and Rust auto-release — because a tag can
  be cut from a commit that went through none of them, and a mismatch there is
  two published artifacts disagreeing about what a recipe is (#174).

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

- **`termproof.collector`** — the evidence collector Rust has had since the
  consolidation. `termproof.evidence` renders whatever a finished `RunResult`
  happens to carry, which is enough for a declarative recipe where the runner
  knows every step before it starts. A caller driving a session imperatively
  decides *while running* which moments are worth keeping, and had nowhere to
  put them. `capture`, `capture_failure`, `capture_text`, `attach_recording`
  and a `publish` that writes text, renders, dedupes, uploads and emits
  `evidence.json`. Mirrored deliberately down to the manifest field names and
  the `step-NN-label` filename scheme, so the two implementations produce one
  document format.

  The two modules are not layered on one another and answer different
  questions; the module docstring now carries a table of which is for what, and
  why consolidating them is a separate change with its own compatibility
  question — `render_artifacts`'s file layout is what every existing reader of
  a run directory depends on.

- **`EvidenceManifest.attach_to`** joins a manifest to a `RunResult` and
  refuses one belonging to a different run. Evidence sits beside the result
  rather than inside it, so nothing about the file layout stops a caller
  pairing run A's evidence with run B's result. Rust has had this; Python's
  `RunResult` carries the same `recipe_name`, `renderer` and `artifacts`
  contract, so it behaves identically apart from raising `ValueError` where
  Rust returns `Err`.

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

### CI

- **Every workflow job is bounded, and the Python jobs no longer install
  ffmpeg from a package mirror.** A quiet Ubuntu mirror stalled
  `apt-get install ffmpeg` in three jobs of one run; nothing carried a
  `timeout-minutes`, so all three ran to GitHub's six-hour ceiling — 18
  job-hours from one commit — and reported `cancelled` with no test output,
  which reads as a broken pull request rather than as infrastructure. The
  install turned out to be redundant everywhere it appeared:
  `termproof.evidence.find_ffmpeg` falls back to
  `imageio_ffmpeg.get_ffmpeg_exe()`, and `imageio-ffmpeg` is a hard runtime
  dependency whose Linux wheel carries the binary, so `uv sync` had already
  put a working ffmpeg on every one of those runners. All three apt steps are
  gone, the jobs that render video assert the bundled binary resolves instead,
  and `cargo install` — the remaining step that reaches the network — runs
  under `.github/scripts/retry.sh`, which bounds each *attempt* so a retry can
  survive a stall rather than only a plain error. All 25 jobs across the 12
  workflows now declare a `timeout-minutes`, and `test_ci_timeouts.py` fails if
  a new one does not. Affects CI only; neither published artifact changes.
  ([#183](https://github.com/md-mt/termproof/issues/183))

### Testing

- **A third differential harness, for the evidence manifest.**
  `conformance/probe_evidence_manifest.py` drives the Python collector over a
  fixed scenario and records the published `evidence.json` together with the
  contents of every file it wrote;
  `crates/termproof/tests/differential_evidence_manifest.rs` builds the same
  scenario through the Rust collector and compares the whole recording.

  It replaces a Python unit test that asserted the manifest key set by spelling
  the Rust field names out — a list derived by reading the Rust structs rather
  than by running them, which could only ever catch a rename on the Python
  side. The files are compared as well as the document because a manifest is a
  set of paths, and agreeing on paths is not agreeing on files: that is what
  caught the trailing newline above.

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
- **cargo:** `tests/canonical_schema.rs` was excluded from the package. It read
  `python/docs/recipe-schema-v1.json`, which sat outside the crate, so
  shipping it would have put a test in the tarball that could not pass from
  there.

### Rust — Fixed

- **release:** the auto-release moves the whole version train. It bumped
  `rust/Cargo.toml` alone, so a release would push a `main` whose Python
  manifest and changelog were left behind and whose own drift check failed.
  `version-bump.py` now moves `python/pyproject.toml` and this file too, and
  the workflow verifies the train before it tags.
- **schema:** `load_canonical_schema` was made to reach
  `python/docs/recipe-schema-v1.json`. Its candidate paths had described
  side-by-side checkouts from before the two implementations shared a
  repository, so it returned `None` everywhere.

  **This is the one behavioural change a consumer of the published crate can
  observe.** The path is resolved from `CARGO_MANIFEST_DIR` alone. One of the
  old candidates was `docs/recipe-schema-v1.json` relative to the working
  directory, so the function could read whatever file of that name happened to
  sit in a consumer's tree and hand it back as TermProof's canonical schema.
  The crate did not vendor the schema at this release, so `None` was the
  correct answer from a registry checkout, and `None` is what it returned.
  `load_canonical_schema_from_dir` was new and doc-hidden; it existed so a test
  could prove the packaged case.

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
