# Status and parity

This page is the deep version of the README's maturity notice. It is written
to be read **before** you depend on anything in this repository, and it is
kept deliberately honest: what the port measures, what it does not, and where
it is known to diverge from the Python implementation. The
[`conformance/README.md`](../../conformance/README.md) is the authority on every number
here — this page summarises it, it does not replace it.

## What this port is

The Rust workspace under `rust/` is a reimplementation of
[TermProof](https://github.com/md-mt/termproof). The Python implementation at
`md-mt/termproof` is the **shipped product and the behavioural oracle**. This
port is **in progress** and is **not yet a drop-in replacement**, and nothing
here should be read as a claim of full parity with the Python implementation.

Treat the Python implementation as the authority on TermProof's behaviour.
A **required gate** now gates the measured layers (see
[What is gated now](#what-is-gated-now) below): `Oracle freshness result`
is required and the ten differential harnesses — including the
cache/config (#263) and selection (#264) harnesses — run via the required
`CI (Rust) result`. The self-assessment in
[What is gated now](#what-is-gated-now) finds #216's three Done-when
bullets met by that gate, the recorded differences and this page. The gate
is still narrower than full parity — full parity is not claimed. It holds
the measured layers to their recorded floors, equalities and named allowed
differences, and recorded is not the same as agreeing. The milestone
re-cut in
[`rust-reimplementation-spec.md`](rust-reimplementation-spec.md#milestone-re-cut-215)
defines v1.0 and Rust M5 by the #216 Done-when gate passing *plus* the
remaining cutover gates recorded there, so do not read a green gate here
as v1.0 or M5 having been reached.

## What is gated now

Two status checks are required on `main` by the repository ruleset
`main: require CI (Rust) result + Oracle freshness result` (id `24859051`,
enforcement active — see [`governance.md`](governance.md) sections 5 and 6.1):

- **`Oracle freshness result`** — the rollup of the always-on
  `CI (Oracle)` workflow (`.github/workflows/oracle-ci.yml`; the workflow
  always starts and the rollup always reports, while its `changes` job
  decides whether an oracle-relevant path moved). When one has, its
  `oracle` job re-runs the conformance probes in the canonical environment
  (`ubuntu-24.04`, CPython 3.13.5, uv 0.11.8, dependencies from
  `python/uv.lock`) and runs
  `python3 conformance/verify_oracle.py --strict-environment`, so the
  checked-in corpus must still reproduce, payload and recorded
  `environment` blocks alike, in that one pinned environment. The corpus
  was re-recorded in that environment in #261, after the gate itself landed
  in #260, and the `CI (Oracle)` run on `main` for that re-record
  (run `38158366345`) succeeded.
- **`CI (Rust) result`** — the rollup of `CI (Rust)`, whose test jobs run
  `cargo test --workspace` when a Rust-relevant path moved (`rust`, `spec`,
  `conformance` or the workflow itself; the rollup reports either way).
  That includes the ten differential harnesses below, so their floors,
  equalities and exact residuals are required on `main` through this check
  rather than merely advisory. A corpus-only re-record touches
  `conformance`, so it re-runs the Rust halves against the new testimony
  rather than landing uncompared.

What that gate does **not** establish:

- **Full parity is not claimed.** The step and assertion harnesses assert a
  floor, not equality (see below), and a floor passing means agreement has
  not fallen — not that the two implementations agree everywhere.
- **Allowed differences are recorded, not fixed.** The run-result,
  build-info, report and config/cache harnesses each name their allowed
  differences in [`conformance/README.md`](../../conformance/README.md) and
  in named constants in the Rust test, asserted so the test fails when a
  divergence stops existing; the cast-replay and selection harnesses pin
  their residuals exactly the same way. The remaining gaps — foreign
  (CPython/libc) error text and the other items under
  [Known defects and divergences](#known-defects-and-divergences) — remain
  open decisions, not settled parity. See
  [Recorded allowed differences](#recorded-allowed-differences).
- **All six #209 surfaces are now covered; coverage still has edges.** The
  cache/config harness (#263) covers the `run_cache`/`cache` and `config`
  pairs (#209 items 4 and 5) and the selection harness (#264) covers
  `selection` (#209 item 6), completing the six alongside run result
  (item 1), build info (item 2) and report (item 3). What each harness
  deliberately does not measure — cache-digest equality and the cache
  round trip, the build-info constructors, the selection recipe-object
  wrappers, and the rest listed in
  [`conformance/README.md`](../../conformance/README.md) — stays ungated,
  and drift there would not fail the checks above.
- **Python CI is not ruleset-required.** Plainly: no `CI (Python)` check is
  in the live ruleset today (see [`governance.md`](governance.md) section
  5). The Python implementation remains the shipped product and the
  behavioural oracle this port is measured against.

### Gate self-assessment against #216

#216 is done when three things hold. Against the live repository, each now
holds — with the qualifications stated, which are part of the finding:

1. **The check runs on every pull request and is required on `main` —
   met.** Ruleset `24859051` (enforcement active) requires exactly
   `CI (Rust) result` and `Oracle freshness result` on the default branch
   for every actor except the live admin-role bypass
   (`RepositoryRole:5:always` — [`governance.md`](governance.md) section
   6.1), which release-automation pushes to `main` go through. Both are
   rollups of
   always-on workflows, so both report on every pull request; the heavy
   jobs behind them run when a relevant path moved (`rust`/`spec`/
   `conformance` for the Rust tests, `python`/`spec`/`conformance` for the
   oracle check), and a Python-only behaviour change is caught by the
   oracle check failing against the stale corpus until it is re-recorded,
   which in turn re-runs the Rust halves. On `main` at `447a197` both
   workflows succeeded (`CI (Rust)` run `38168472478`, `CI (Oracle)` run
   `38168472412`). This is the two-check live ruleset, not the fourteen
   checks [`governance.md`](governance.md) section 6.2 intends; in
   particular no `CI (Python)` check is required, as noted above.
2. **The known drifts are either fixed or explicitly recorded as allowed
   differences — met, by recording rather than by fixing.** All six #209
   module pairs are pinned by a harness whose allowances or exact
   residuals are named in
   [`conformance/README.md`](../../conformance/README.md) and asserted in
   the Rust test, so an allowance fails when its divergence stops existing
   instead of silently outliving it. The cast-replay residual is recorded
   the same way. The step and assertion residuals are recorded as floors
   + README-named residuals, not self-expiring allowances — their tests
   assert `agreed >= FLOOR` only, so a healed case raises agreement
   without forcing the record out — and the no-harness recordings by
   design — `render_fingerprint`
   (#222, decided in #234) and the attributed screen's Unicode behaviour
   (#244) — are written out under
   [Recorded allowed differences](#recorded-allowed-differences) below.
   Recorded does not mean settled: which side is the reference is still
   undecided for build info, report, config/cache and selection (#209),
   the step and assertion floors tolerate the recorded wording gaps rather
   than requiring agreement, and each harness's stated exclusions remain
   unmeasured.
3. **This page can point at the gate instead of saying there is not one —
   met.** [What is gated now](#what-is-gated-now) above names the two
   required checks, what runs behind them and what they do not establish,
   and this assessment is the pointing. Pointing at the gate is not a
   claim of full parity, and it does not by itself complete v1.0 or Rust
   M5, whose remaining cutover gates are recorded in
   [`rust-reimplementation-spec.md`](rust-reimplementation-spec.md#milestone-re-cut-215).

Pre-1.0 `0.x` releases may change public APIs without notice. A breaking
change is a minor bump (`0.2.x` → `0.3.0`) under the workspace's
[version-bump rule](publishing.md#version-bump-rule), but that is a semver
convention, not a stability promise: the port's public surface is still
moving as it approaches parity.

## The differential harness

Ten layers are measured, as listed in
[`conformance/README.md`](../../conformance/README.md), which is the
authority for this table. Each layer has its own harness, each the same
two-half shape: a Python probe drives its side, and a Rust test replays the
same cases or scenario and compares. Some layers replay a checked-in corpus
of cases; others — the evidence-manifest, run-result, build-info, report
and config/cache harnesses — build their scenario in code in each half
rather than from a corpus of cases, and compare the recorded document (and,
for the evidence manifest, the files it wrote) — see
[`conformance/README.md`](../../conformance/README.md).

| Layer | Oracle | Port | Corpus | Shape |
|---|---|---|---|---|
| Steps | `conformance/probe_steps.py` | `crates/termproof/tests/differential_steps.rs` | `conformance/corpus/cases.json` | floor |
| Assertions | `conformance/probe_assertions.py` | `crates/termproof/tests/differential_assertions.rs` | `conformance/corpus/assertion_cases.json` | floor |
| Evidence manifest | `conformance/probe_evidence_manifest.py` | `crates/termproof/tests/differential_evidence_manifest.rs` | `conformance/corpus/evidence_manifest.expected.json` | equality |
| Before/after | `conformance/probe_before_after.py` | `crates/termproof/tests/differential_before_after.rs` | `conformance/corpus/before_after_cases.json` | equality |
| Cast replay | `conformance/probe_cast_replay.py` | `crates/termproof/tests/differential_cast_replay.rs` | `conformance/corpus/cast_replay_cases.json` | exact residual |
| Run result | `conformance/probe_run_result.py` | `crates/termproof/tests/differential_run_result.rs` | `conformance/corpus/run_result.expected.json` | equality apart from named allowed differences |
| Build info | `conformance/probe_build_info.py` | `crates/termproof/tests/differential_build_info.rs` | `conformance/corpus/build_info.expected.json` | equality apart from named allowed differences |
| Report | `conformance/probe_report.py` | `crates/termproof/tests/differential_report.rs` | `conformance/corpus/report.expected.json` | equality apart from named allowed differences |
| Config / run cache | `conformance/probe_config.py` | `crates/termproof/tests/differential_config.rs` | `conformance/corpus/config.expected.json` | config: equality apart from named allowed differences; cache: availability/sensitivity (digests never cross-compared) |
| Selection | `conformance/probe_selection.py` | `crates/termproof/tests/differential_selection.rs` | `conformance/corpus/selection_cases.json` | exact residual |

The step and assertion harnesses assert a **floor rather than equality**:
agreement can rise but must never fall, and panics and cases that never return
are asserted at zero rather than ratcheted. Full agreement is deliberately
**not** required — the remaining gaps are open decisions that are not the port's
to make (see [Known defects and divergences](#known-defects-and-divergences)
below).

The evidence-manifest and before/after harnesses have no ratchet and demand
equality: they compare a document or a report format rather than scoring a
corpus, and a partial score for a format is not a useful number. The
before/after direction is also the other way round — Rust is the reference
and Python was changed to match it (#204), because the Rust module is the
newer of the two and carries the documented ordering rationale.

The run-result, build-info, report and config/cache harnesses likewise
demand equality of the whole document, apart from the allowed differences
each one names in `conformance/README.md` and in named constants in its
Rust test. Each allowance is asserted in both directions, so the test fails
when the pinned divergence stops existing and the allowance has to be
removed deliberately; any other difference fails the comparison. The
config/cache harness makes one deliberate exception inside that shape: the
two cache-key payloads differ by construction, so key *digests* are not
compared across languages — availability and per-side input sensitivity are
pinned instead, with direct digest comparison recorded in
`conformance/README.md` as the follow-up if the payloads ever converge.
Nobody has yet decided which side is the reference for the build-info,
report and config/cache layers (#209), so those allowances record the drift
rather than settling it.

Cast replay and selection assert their known residuals exactly — cast
replay by case name and pinned frame, selection by case name and the exact
list Rust selects (34 of 49 cases agree exactly, 15 are pinned) — rather
than as a floor, so a listed case that starts agreeing fails the test, as
does one that moves to a different answer. The step and assertion counts
are summarised below; the other eight harnesses are described in
`conformance/README.md` rather than duplicated here — cast replay and
selection there with their counts and the residuals tracked in #209, and
the evidence-manifest, before/after, run-result, build-info, report and
config/cache harnesses there in pass/fail form (the two documents or
recordings printed on failure), so they have no counts to summarise here.

## Step layer

| Count | Meaning | Now |
|---|---|---|
| Full agreement | `name`, `passed` and `detail` all match | **82 / 115** |
| Verdict agreement | `passed` matches, whatever `detail` says | **113 / 115** |
| Panicked | the port took the process down | 0 |
| Never returned | the port wedged on a deadline it could not reach | 0 |
| Ran against a real child | the port drove a pseudo-terminal, as the oracle does | 28 / 115 |

Up from 26 of 115 when the harness first ran. The remaining 33 cases are
enumerated in `conformance/README.md`.

## Assertion layer

| Count | Meaning | Floor |
|---|---|---|
| Full agreement | `name`, `passed` and `detail` all match | **at least 124 / 161 comparable** |
| Verdict agreement | `passed` matches, whatever `detail` says | **at least 143 / 161 comparable** |
| Contained | the oracle ends its run; the port returns a result instead | 18 / 18 |
| Escaped containment | the port also lost results | 0 |
| Panicked | the port took the process down | 0 |
| Never returned | the port wedged | 0 |

The denominator is 161, not 179: the eighteen contained cases have no oracle
verdict to agree with. The 124 and 143 are absolute floors, carried over
unchanged from the 147-comparable corpus when the fourteen `multipleOf`
cases enlarged it — minima the harness enforces, not a measurement of the
enlarged corpus, whose agreement counts the harness's first CI run at
`jsonschema` 0.56 will report. With `termproof`'s `json-schema` feature off,
the 72 `json_schema` cases are skipped by assertion type and the floor for
the rest is 89 / 89 comparable: full agreement is required of every case
that needs no validator, so the harness can only pass while every remaining
divergence is a `json_schema` case.

## What the numbers do not cover

These are layer-level numbers, not a product number:

- **Screen fidelity is outside them.** 87 of the 115 step cases drive the
  steps against a session with fixed content; rendering, scrollback and
  escape-sequence handling stay out of frame. The assertion corpus fixes
  `screen`, `raw_output` and `exit_code` as strings, so terminal fidelity,
  the PTY and real exit-code capture are out of frame there too.
- **Whole-recipe execution is outside them.** The eleven assertion `run`
  cases stop at the evaluated list, the score and the overall verdict; they
  do not exercise the planner, the runner or the evidence pipeline as a run
  would.
- **The assertion layer can only be as right as what it is handed.** An
  assertion is evaluated against fixed strings, so a divergence upstream of
  it cannot be detected here.
- **Non-POSIX path semantics are not handled.** `crates/termproof/src/pypath.rs`
  models `PurePosixPath`; Windows drive letters and UNC paths are not in the
  corpus and are not supported.
- **Each harness's stated exclusions are outside them.** All six #209
  pairs now have a harness, but what a harness declines to measure — cache
  digests and the cache round trip, the build-info constructors, the
  selection recipe-object wrappers, cross-runtime `render_fingerprint`
  digests (runtime-local by decision, below) — is outside every number and
  gate here, so nothing on this page says whether those agree.

Reading 82/115 or 124/161 as a parity figure for the port would be wrong.

## Recorded allowed differences

These are the explicit recordings #216's second Done-when bullet requires:
a known drift that is written down here or in
[`conformance/README.md`](../../conformance/README.md) counts as recorded,
and recorded means **no fix is planned** unless an entry says otherwise.
Each entry says where the difference is observable, so it is not
rediscovered later as a fresh bug.

Most recordings are harness-pinned and live in
[`conformance/README.md`](../../conformance/README.md), not duplicated
here: the run-result, build-info, report and config/cache allowances, the
cast-replay and selection exact residuals, and the step and assertion
known residuals summarised under
[Known defects and divergences](#known-defects-and-divergences) below.
Each allowance and exact residual is also a named constant asserted in
its Rust test, so the test fails when the divergence stops existing and
the record has to be removed deliberately. The step and assertion
residuals are recorded as floors + README-named residuals, not
self-expiring allowances: their tests assert `agreed >= FLOOR` only.
The remaining entries have no harness by design and are
written out in full here.

### `render_fingerprint` on non-ASCII screens (#222, decided in #234)

Recorded, no fix planned. Python hashes `json.dumps` output with its
default `ensure_ascii=True`, so a non-ASCII cell is hashed as an escape
(`\u00e9`); Rust hashes `serde_json` output, which writes the raw UTF-8
(`é`). ASCII-only screens therefore fingerprint identically in both
runtimes and screens with non-ASCII cell text do not. By the decision
recorded in #234 the digest is **runtime-local**: it only has to match
other fingerprints produced by the same runtime, which is all evidence
dedup asks of it, and no harness compares it across runtimes
([`conformance/README.md`](../../conformance/README.md), "Not compared:
`render_fingerprint`"). A portable cross-runtime fingerprint remains
future work under #222.

That framing is safe only because a fingerprint never persists anywhere a
second runtime could read it, and that was verified rather than assumed:
the digest's only consumer in either implementation is the screenshot
`Deduper` (`python/termproof/dedup.py`,
`crates/termproof/src/evidence/dedup.rs`), which keeps the previous
screen's fingerprint in memory for a one-step lookback inside a single
publish. What the manifest serialises is the verdict — the `same_as`
back-reference and the reused image path — not the digest; no
serialised step carries a fingerprint field, and no code path writes one
to a file. The run-cache key is a separate digest computed separately
(`cache::cache_key`, `run_cache._cache_key`) and is not derived from the
fingerprint. Where this difference is observable, then, is only in the
digest string itself when a caller prints `render_fingerprint()` for the
same non-ASCII screen in both runtimes; nothing stored, compared or
served from cache depends on the two agreeing.

### Interpreter-dependent Unicode tables (#244)

Recorded, no fix planned. The attributed screen takes its width and
combining decisions from different tables on each side: Python from the
running interpreter's `unicodedata` (`east_asian_width`, `combining`),
Rust from the pinned `unicode-width` and `unicode-normalization` crates.
Measured over every scalar value (#244), the two disagree on a few
hundred code points in the canonical CPython 3.13.5 environment — 356
that are wide only in Rust and 46 combining marks that merge only in
Rust — and the gap moves with the Python version, because each
interpreter carries a different Unicode version. On Python 3.11, still
the `requires-python` floor and still in the CI matrix, the gap was far
larger until #248: `east_asian_width` returns `F` for every
*unassigned* code point, so roughly 764k unassigned code points took
two cells in Python and one in Rust. #248 closed that bulk by
special-casing unassigned (Cn) code points in `_cell_width`
(`python/termproof/attributed.py`) — two cells in the five
default-wide ranges, one elsewhere — bringing 3.11 width disagreements
from 764,532 to 383, in line with later interpreters. Real terminal
output rarely contains unassigned code points, but the size of the
former gap is recorded so nobody has to re-measure it to believe it.

Where this is observable is the point to be careful about. The width and
merging decisions change the cell grid itself, and with it `text_lines`
output and where glyphs are placed in the rendered SVG — and, through the
cell payload, the fingerprint. Only that last effect is covered by the
runtime-local decision above. **Cell layout and SVG placement are not
runtime-local**: the same screen lays out differently depending on which
runtime, and on the Python side which interpreter version, built it, and
that difference is visible in artifacts a consumer reads. It must not be
folded into the fingerprint framing as if recording the digest had
recorded the layout. Vendoring a pinned table into Python remains the
open option listed in #244 and is not planned.

### A combining mark in a wide glyph's filler cell (#244)

Recorded, no fix planned, and — unlike the entry above — the same on both
sides rather than a divergence between them. A combining mark that
follows a wide glyph attaches to the glyph's invisible width-0 filler
cell in both constructors (`日` + U+0301 becomes `[日 w2][U+0301 w0]`).
The mark therefore **counts in `render_fingerprint`** — the marked and
unmarked screens hash differently — but is **never displayed**:
`text_lines` keeps only `width > 0` cells and the SVG renderer skips
`width == 0` cells, on both sides. Real text hits this: decomposed
`か` + U+3099 (が) renders as `か`, the voicing mark silently lost, in
both implementations. Where observable: rendered text and SVG on either
side, and two screens that display identically while fingerprinting
differently. Attaching such a mark to the preceding wide glyph instead
would change both implementations together and is not planned.

## Known defects and divergences

In rough severity order:

- **The in-memory session double encodes test-passing rather than PTY
  semantics.** `InMemorySession`'s `wait_for_text` answers from fixed content
  and ignores its deadline, and `wait_for_idle` always returns true — so
  nothing running through it can show a deadline being honoured.
- **Two `press` rows diverge on verdict.** `press/ctrl-bracket` (`ctrl-[`)
  and `press/ctrl-unmapped` (`ctrl-1`) are the only step rows where the two
  runtimes disagree on `passed`. The oracle derives the control byte
  arithmetically; the port's key table refuses anything not named in it.
  This is the `terminal` module's mapping to settle (`spec/002-builtin-steps/spec.md`
  FR-016, OQ-005).
- **`wait_for_idle` does not distinguish** "no output observed from the
  session" from an ordinary idle timeout (OQ-004).
- **Foreign error text — 30 step cases and 15 assertion cases, verdict
  agrees.** A little over a quarter of the step corpus embeds an error string
  owned by CPython or libc (`could not convert string to float: 'abc'`,
  `utf_8_encode() argument 1 must be str, not int`, …). The port reaches the
  same verdict by the same route and words the diagnostic itself; matching
  byte-for-byte means hardcoding another project's messages and keeping them
  current across releases. That is an open decision about what TermProof's
  diagnostics *are* (001-OQ-001 / 002-OQ-002 / 003-OQ-010), not a porting
  detail.
- **Non-finite JSON — 4 assertion cases, verdict differs.** Python's `json`
  decoder accepts bare `NaN`, `Infinity` and `-Infinity`; `serde_json`
  rejects them. These are the only four rows where the two runtimes disagree
  on `passed` (003-OQ-008).
- **Object key order — 1 assertion case.** Python dicts preserve insertion
  order; `serde_json::Map` without `preserve_order` is a `BTreeMap`. Turning
  the feature on would fix this row and change how every other JSON object in
  the crate is ordered, a workspace-wide decision.
- **`best_match` tie-breaks — 2 assertion cases.** When two root-level errors
  have identical relevance keys, the winner is decided by the validator's
  yield order, which the port cannot see through its map type.

Five earlier defects are fixed, each with a test that failed first: a large
finite `timeout_seconds` / `seconds` panicking the process, valid Python
regexes rejected, strict JSON typing rejecting recipes Python accepts,
`send_line` silently discarding a non-string `text`, and match diagnostics
diverging from Python's `repr`.

## Library surface no TermProof command uses yet

Fourteen modules landed as tested APIs with no caller in the CLI. They are
worth knowing about and worth **not** mistaking for features of `termproof
run`:

- `termproof::parity` — compares two runs and reports where they disagree.
- `termproof::before_after` — reports which outcomes flipped.
- `termproof::selection` — maps a changeset onto recipes via `ci_paths`.
- `termproof::run_config` — a whole run described by one file, plus
  `run_config::cli` under the `clap` feature: the flags that fill one in.
- `termproof::vocabulary` — a configurable failure detector.
- `termproof::build_info` — provenance for the binary under test.
- `terminal::attributed` — a per-cell screen carrying colours, styles and
  display width, with an SVG renderer.
- `terminal::tmux` — a `Session` that runs the program in a tmux pane and
  reads the grid back with `capture-pane`.
- `terminal::proc` — child processes with a deadline.
- `terminal::driver` — `SessionDriver`, a scenario-facing wrapper over
  `Box<dyn Session>`.
- `evidence::screenshot` and `evidence::cast_video` — stills and video frames
  through one renderer.
- `evidence::dedup` — skips re-rendering a screen identical to the step
  before it.
- `evidence::uploader` — a publishing seam with a fallback chain.
- `evidence::collector` — `EvidenceCollector`, the ordered step model those
  plug into; `publish` renders, dedupes, uploads and writes an
  `evidence.json` manifest in one pass. It sits **beside** `RunResult` rather
  than inside it.

**None of this is wired into `termproof run`.** A run writes
`raw_output.txt`, `screen.txt` and a cast if one was recorded — no image at
all, so no command reaches either renderer. No run uses the tmux backend or
the deduper, and nothing calls the uploader. Treat these as a library a
caller could build on, not as behaviour the CLI has.

## What a run still cannot do

So that a green exit is not read as more than it is:

- **Only `execution: scripted` on a pty runs.** A recipe whose `command.pty`
  is false, or whose `execution` is anything else, is refused with a
  diagnostic naming the reason and a non-zero exit. `DockerSessionBackend` is
  still a stub.
- **`--video`, `--diff`, `--update-baselines` and `--skip-unchanged` are
  parsed and ignored**, with a warning on stderr rather than silence.
- **A recipe cannot branch on what it observes** — and that is a decision
  rather than a gap. Polling until something renders and acting only if it
  did, dismissing an overlay that may or may not appear, and retrying a racy
  step all belong in a consumer's own runner, written against `SessionDriver`.
  What the crate offers such a consumer instead — and why a `when` predicate
  and a second, imperative recipe model were both declined — is
  [`conditional-recipes.md`](conditional-recipes.md).
- **Failures are not contained.** RUST-009 (issue #2) — turning recipe, step,
  plugin, process and PTY failures into structured results — is untouched.
