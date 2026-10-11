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
A **required drift gate** now gates the measured layers (see
[What is gated now](#what-is-gated-now) below): `Oracle freshness result`
is required and the differential harnesses run via the required
`CI (Rust) result`. That current gate is **not yet the #216 Done-when
parity gate** and is narrower than full parity — full parity is not
claimed. It holds the measured layers to their recorded floors,
equalities and named allowed differences, and it does not cover every
surface. #216 remains open, in particular for cache/config+selection
coverage, and the milestone re-cut in
[`rust-reimplementation-spec.md`](rust-reimplementation-spec.md#milestone-re-cut-215)
defines v1.0 and Rust M5 by the #216 Done-when gate passing, not by this
drift gate. The required checks described below are live today, so do not
read a green drift gate as v1.0 or M5 having been reached.

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
  `cargo test --workspace` when a Rust-relevant path moved (the rollup
  reports either way). That includes the eight differential harnesses
  below, so their floors, equalities and exact residuals are required on
  `main` through this check rather than merely advisory.

What that drift gate does **not** establish:

- **Full parity is not claimed.** The step and assertion harnesses assert a
  floor, not equality (see below), and a floor passing means agreement has
  not fallen — not that the two implementations agree everywhere.
- **Allowed differences are recorded, not fixed.** The run-result,
  build-info and report harnesses each name their allowed differences in
  [`conformance/README.md`](../../conformance/README.md) and in named
  constants in the Rust test, asserted so the test fails when a divergence
  stops existing. The remaining gaps — foreign (CPython/libc) error text and
  the other items under
  [Known defects and divergences](#known-defects-and-divergences) — remain
  open decisions, not settled parity.
- **Uncovered surfaces stay uncovered until their harnesses land.** In
  particular the cache (`run_cache`/`cache`), `config` and `selection`
  module pairs from #209 have no differential harness yet; work on them is
  in flight, not landed, so drift there is not gated by the checks above.
- **`CI (Python)` is not ruleset-required.** Plainly: no `CI (Python)` check is
  in the live ruleset today (see [`governance.md`](governance.md) section
  5). The Python implementation remains the shipped product and the
  behavioural oracle this port is measured against.

Pre-1.0 `0.x` releases may change public APIs without notice. A breaking
change is a minor bump (`0.2.x` → `0.3.0`) under the workspace's
[version-bump rule](publishing.md#version-bump-rule), but that is a semver
convention, not a stability promise: the port's public surface is still
moving as it approaches parity.

## The differential harness

Eight layers are measured, as listed in
[`conformance/README.md`](../../conformance/README.md), which is the
authority for this table. Each layer has its own harness, each the same
two-half shape: a Python probe drives its side, and a Rust test replays the
same cases or scenario and compares. Some layers replay a checked-in corpus
of cases; others — the evidence-manifest, run-result, build-info and report
harnesses — build their scenario in code in each half rather than from a
corpus of cases, and compare the recorded document (and, for the evidence
manifest, the files it wrote) — see
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

The run-result, build-info and report harnesses likewise demand equality of
the whole document, apart from the allowed differences each one names in
`conformance/README.md` and in named constants in its Rust test. Each
allowance is asserted in both directions, so the test fails when the pinned
divergence stops existing and the allowance has to be removed deliberately;
any other difference fails the comparison. Nobody has yet decided which
side is the reference for the build-info and report layers (#209), so those
allowances record the drift rather than settling it.

Cast replay asserts its known residual exactly — by case name and pinned
frame — rather than as a floor, so a listed case that starts agreeing fails
the test, as does one that replays to a different screen. The step and
assertion counts are summarised below; the other six harnesses are
described in `conformance/README.md` rather than duplicated here — cast
replay there with its counts and the residual tracked in #209, and the
evidence-manifest, before/after, run-result, build-info and report
harnesses there in pass/fail form (the two documents or recordings printed
on failure), so they have no counts to summarise here.

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
- **Surfaces with no harness yet are outside them entirely.** The cache
  (`run_cache`/`cache`), `config` and `selection` pairs from #209 have no
  differential harness yet (work in flight, not landed), so no number or
  gate here says anything about whether they agree.

Reading 82/115 or 124/161 as a parity figure for the port would be wrong.

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
