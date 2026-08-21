# Differential harness

Cross-runtime differential harnesses for the layers the port has to match. One
per layer, each the same two-half shape:

| Layer | Oracle | Port | Corpus |
|---|---|---|---|
| Steps | `probe_steps.py` | `tests/differential_steps.rs` | `corpus/cases.json` |
| Assertions | `probe_assertions.py` | `tests/differential_assertions.rs` | `corpus/assertion_cases.json` |
| Evidence manifest | `probe_evidence_manifest.py` | `tests/differential_evidence_manifest.rs` | `corpus/evidence_manifest.expected.json` |

They exist because the port claimed corpus parity several times over with green
local gates, and a differential run against the Python implementation still
found the two runtimes agreeing on a minority of cases. A number nobody can
reproduce is not a measurement.

# Step semantics

## Shape

The harness is two halves that meet at a checked-in corpus.

| Half | Where | What it does |
|---|---|---|
| Oracle | `probe_steps.py` | Drives the Python steps over `corpus/cases.json` and records each case's `name`, `passed` and `detail` into `corpus/steps.expected.json`. |
| Port | `crates/termproof/tests/differential_steps.rs` | Replays the same cases through the Rust steps and reports the agreement count. |

Splitting it this way means the measurement is reproducible in CI without a
Python interpreter, and the recorded expectations carry the environment they
were observed in — several details are CPython-, libc- and `ptyprocess`-version
dependent (`spec/002-builtin-steps/spec.md` FR-004, FR-008, FR-016).

## Regenerating the expectations

```sh
cd /path/to/termproof/python
TERMPROOF_PYTHON_REPO=$PWD uv run python \
    ../conformance/probe_steps.py \
    > ../conformance/corpus/steps.expected.json
```

Only regenerate deliberately: the file is the oracle's testimony, and quietly
re-recording it turns a failing comparison into a passing one without changing
any behaviour.

## Reading the number

```sh
cargo test -p termproof --test differential_steps -- --nocapture
```

The test prints every divergence and two counts, and fails if either drops below
the floor recorded in the test:

| Count | Meaning | At the harness commit | Now |
|---|---|---|---|
| Full agreement | `name`, `passed` and `detail` all match | 26 / 115 | 82 / 115 |
| Verdict agreement | `passed` matches, whatever `detail` says | not recorded | 113 / 115 |
| Panicked | the port took the process down | 5 | 0 |
| Never returned | the port wedged on a deadline it could not reach | 1 | 0 |
| Ran against a real child | the port drove a pseudo-terminal, as the oracle does | 0 / 115 | 28 / 115 |

The two counts are separate floors on purpose. A fix that corrects a verdict and
leaves the wording to a later commit moves the second and not the first, so it
still has to move a number; a wording-only fix moves the first alone.

The panic and never-returned counts are asserted at zero rather than ratcheted.
Recipe-controlled input taking the process down is not a divergence to be traded
off against agreement — see `spec/002-builtin-steps/spec.md` FR-007.

Full agreement is **not** required, because the remaining gap is one open
decision that is not the port's to make plus two rows that belong to another
layer — see "Known residual" below.

## What the corpus does and does not measure

**Does**: the step layer — argument coercion, validation order, timeout
handling, regex dialect, and the exact `detail` string each step produces.

**Does not**: terminal fidelity, for the 87 cases the corpus marks `kind: stub`.
Those run on both sides against a session with fixed content whose wait loops
are transcribed from `termproof/session.py`, so screen rendering, scrollback and
escape-sequence handling stay out of frame for them. The screen layer has its
own work.

**Does, since `PtySession` implements `Session`**: the write path of a real
pseudo-terminal, for the 28 cases the corpus marks `kind: child`. Both halves now
spawn `cat` on a pty and drive it, so `send_text`, `send_line` and `press` are
compared terminal to terminal rather than terminal to double. The count is
ratcheted alongside the agreement floors: routing those cases back to the stub
fails the test.

Three deliberate compromises, each of which inflates or deflates the number in a
knowable direction:

1. **`send_text`, `send_line` and `press` cases run against a real child on both
   sides.** A stub session that appends to a list records `send_text
   {"text": 5}` as *passing*; only a real child reveals the failure. The Python
   half has always used one; the Rust half used its in-memory session until
   `PtySession` implemented `Session`, so a divergence in these rows could
   belong to either the step layer or the session layer. It can no longer: both
   halves spawn a pty child, and a divergence is the port's.
2. **`NaN`, `Infinity` and `-Infinity` cannot be written as JSON numbers.** The
   corpus spells them `"@nan"`, `"@inf"` and `"@-inf"`. Python's `json` module
   accepts bare `NaN` tokens and Rust's does not, so each half substitutes the
   spelling its own parser accepts and that its duration coercion maps to the
   same float. The step under test sees the same `f64` either way.
3. **A step object with no `action` is absent from the corpus.** It kills the
   Python run outright — the runner's own exception handler reads
   `step["action"]` as its first line — so there is no oracle verdict to record.
   `spec/002-builtin-steps/spec.md` FR-025 supersedes the oracle here and
   OQ-008 leaves the replacement diagnostic undecided.

## Known residual

### Foreign error text — 30 cases, verdict agrees

A little over a quarter of the corpus embeds an error string owned by CPython or
by libc rather than by TermProof — `could not convert string to float: 'abc'`,
`utf_8_encode() argument 1 must be str, not int`,
`timestamp out of range for platform time_t`,
`unterminated character set at position 0`. Matching them byte-for-byte means
hardcoding a table of another project's messages, keeping it current across
their releases, and inheriting a platform-sensitive one. That is a decision
about what TermProof's diagnostics *are*, not a porting detail, and it is open
as 001-OQ-001 / 002-OQ-002 / 003-OQ-010 — one decision, raised in three specs.

Until it is made, these cases agree on `passed` and diverge on `detail`: the
port reaches the same verdict by the same route and says so in its own words.

### Two `press` rows — verdict differs

`press/ctrl-bracket` (`ctrl-[`) and `press/ctrl-unmapped` (`ctrl-1`) are the only
rows where the two runtimes disagree on `passed`. The oracle accepts both — it
derives the control byte arithmetically — and the port's key table refuses
anything not named in it. That is the `termproof::terminal` mapping rather than the
step layer's (`spec/002-builtin-steps/spec.md` FR-016), and the shape the port
should adopt is open as OQ-005, because `ctrl-1` produces a byte the oracle
itself would not call meaningful.

Both rows now run against a real pty child on both sides and still diverge, so
the disagreement is the key table's and not an artefact of the port having
replayed them against a double.

### One diagnostic the corpus says is missing

`wait_for_idle` reports `no output observed from the session` when the session
produced nothing at all, and `timed out waiting for idle` otherwise. The port
emits the second for both. It is a real divergence, recorded here rather than
fixed, and the heuristic behind it is OQ-004.

# Assertion semantics

A second corpus, same shape, for the eight built-in assertions
(`spec/003-builtin-assertions/spec.md`).

## Shape

| Half | Where | What it does |
|---|---|---|
| Oracle | `probe_assertions.py` | Builds a real fixture tree, drives the Python assertions over `corpus/assertion_cases.json` and records each case's `name`, `passed` and `detail` into `corpus/assertions.expected.json`. |
| Port | `crates/termproof/tests/differential_assertions.rs` | Builds the same fixture tree, replays the same cases through the Rust assertions and reports the agreement count. |

## The corpus

165 cases. Two kinds:

- **`assertion`** (154) — one assertion evaluated on its own against a fixed
  `screen`, `raw_output` and `exit_code`.
- **`run`** (11) — a whole recipe's assertion list, transcribed from
  `TermProofRunner.evaluate_assertions`, recording the evaluated list in order
  plus the score and the overall verdict. This is what measures FR-019 ordering
  and FR-022 scoring rather than assuming them.

Coverage against the spec's success criteria: every row of FR-004, FR-008,
FR-011, FR-016 and FR-020; every worked example in FR-016; all eight assertion
types with at least one passing and one failing case each; all three FR-019
ordering rows; all five FR-022 scoring shapes; fourteen `best_match` schemas
that produce more than one error simultaneously; and Python-`repr` conformance
over strings, dicts, lists, floats, bools and `None`.

### Fixtures

`fixtures` in the corpus is the file tree both halves build in a fresh temporary
directory before running. `null` means a directory; `@hex:...` means those raw
bytes, which is how a file that is not valid UTF-8 gets into a JSON corpus.

There is deliberately **no `sub/` directory**. FR-011 requires
`sub/../exists.txt` to resolve to a path that does *not* exist — both runtimes
`stat` the joined path and the kernel resolves `..` against the real tree, so
the row only measures what it claims to if `sub` is absent. `realsub/` is the
paired positive case.

`@FX` is the fixture root: substituted in before a case runs and substituted
back out of the recorded detail, so an absolute path in `file_exists` or
`schema file unreadable:` is comparable across machines. This is the
`spec/OBSERVATION-LOG.md` §4 constraint, honoured rather than worked around.

## Regenerating the expectations

```sh
cd /path/to/termproof/python
TERMPROOF_PYTHON_REPO=$PWD uv run python \
    ../conformance/probe_assertions.py \
    > ../conformance/corpus/assertions.expected.json
```

Only regenerate deliberately: the file is the oracle's testimony, and quietly
re-recording it turns a failing comparison into a passing one without changing
any behaviour.

## Reading the number

```sh
cargo test -p termproof --test differential_assertions -- --nocapture
```

The test prints every divergence and the counts below, and fails if either
ratcheted count drops beneath its floor:

| Count | Meaning | At the implementation commit |
|---|---|---|
| Full agreement | `name`, `passed` and `detail` all match | 124 / 147 |
| Verdict agreement | `passed` matches, whatever `detail` says | 143 / 147 |
| Contained | the oracle ends its run; the port returns a result instead | 18 / 18 |
| Escaped containment | the port also lost results | 0 |
| Panicked | the port took the process down | 0 |
| Never returned | the port wedged | 0 |
| Skipped | no validator compiled in this build | 0 / 0 |

The denominator is 147, not 165: the eighteen contained cases have no oracle
verdict to agree with, so counting them either way would be inventing a result.

### Without the `json-schema` feature

The harness always compiles and always runs. `termproof`'s `json-schema`
feature is default-on, and with it off the 58 `json_schema` cases have no
validator to answer them — so those are skipped *by assertion type*, and only
those. The other 107 are the same evidence either way, and a feature
combination that dropped them would still report green, which is the failure
this shape exists to prevent.

| Count | `--no-default-features` |
|---|---|
| Full agreement | 89 / 89 |
| Verdict agreement | 89 / 89 |
| Contained | 18 / 18 |
| Skipped | 58 / 58 |

Skipped is asserted exactly, not ratcheted: a build that skips a case it could
have answered is measuring less than it claims, and so is one that skips none
when it should skip 58.

That the remainder is 89 / 89 is worth reading twice — every one of the 23
detail divergences and all 4 verdict divergences in the default run is a
`json_schema` case, which is what the `jsonschema`-message note below predicts.

The two agreement counts are separate floors on purpose. A fix that corrects a
verdict and leaves the wording to a later commit moves the second and not the
first, so it still has to move a number; a wording-only fix moves the first
alone.

Containment, panics and never-returned are asserted rather than ratcheted.
`spec/003-builtin-assertions/spec.md` FR-020 says no assertion and no assertion
input may terminate the run, which is not a property to be traded off against
agreement.

Full agreement is **not** required. Every one of the twenty-three remaining
divergences is one of the four residuals below.

## What the corpus does and does not measure

**Does**: the assertion layer — which haystack each type reads, path resolution,
Python `==` across types for `exit_code`, schema resolution order, `best_match`
selection, `repr` and `str` rendering, evaluated-list order, scoring, and the
exact `detail` each assertion produces.

**Does not**:

- **Anything upstream of the assertion.** `screen`, `raw_output` and `exit_code`
  are fixed strings in the corpus, so terminal fidelity, the PTY and how a real
  process's exit code is captured are all out of frame. An assertion can only be
  as right as what it is handed.
- **Concurrency, ordering across recipes, or evidence serialisation.** The eleven
  `run` cases stop at the list, the score and the overall verdict.
- **Whether the recorded oracle is itself right.** The corpus measures agreement
  with the Python implementation as it behaves today, which is why FR-020's
  eighteen cases are scored against the spec instead.
- **Non-POSIX path semantics.** `crates/termproof/src/pypath.rs` models
  `PurePosixPath`. A Windows drive letter or UNC path is not in the corpus and
  is not handled.

## Known residual

Twenty-three divergences, in four groups. None is a defect the port can fix
without a decision that is not the port's to make.

### Foreign error text — 15 cases, verdict agrees

The `json_schema` details that interpolate a message owned by `jsonschema`,
CPython or libc. The port reaches the same verdict by the same route, keeps
FR-016's prefix byte-exactly, and words the interpolated clause itself:

| Oracle (foreign) | Port (its own) |
|---|---|
| `[Errno 2] No such file or directory: '…'` | `no such file or directory: '…'` |
| `[Errno 21] Is a directory: '…'` | `is a directory: '…'` |
| `Expecting value` | `invalid syntax at line 1 column 2` |
| `Expecting property name enclosed in double quotes` | `invalid syntax at line 1 column 2` |
| `Unexpected UTF-8 BOM (decode using utf-8-sig)` | `unexpected UTF-8 byte order mark` |
| `'nope' is not valid under any of the given schemas` | `'nope' does not match any of the given schemas` |
| `{} is not valid under any of the given schemas` | `{} does not match any of the given schemas` |
| `Additional properties are not allowed ('extra' was unexpected)` | `1 is not allowed here` |
| `[1, 2, 3] is too long` | `[1, 2, 3] has more than 1 items` |

Matching them byte-for-byte means hardcoding a table of another project's
messages, keeping it current across their releases, and inheriting a
platform-sensitive one. Open as 001-OQ-001 / 002-OQ-002 / 003-OQ-010 — one
decision, raised in three specs.

Two of those rows lose information rather than just rewording it. The port's
`additionalProperties: false` message cannot name the offending property,
because the crate reports it as a false-schema failure at the root with only the
value attached; and the parse-failure rows trade a description of what was
expected for a line and column. Both are consequences of the same decision.

### Non-finite JSON — 4 cases, verdict differs

`json_schema/nan-bare`, `infinity-bare`, `negative-infinity-bare` and
`nan-nested`. Python's decoder accepts bare `NaN`, `Infinity` and `-Infinity`,
so a recipe asserting "my program emits valid JSON" passes on output no other
parser accepts. `serde_json` rejects them, and its `Value` cannot represent them
at all, so matching would mean a bespoke value type — not a parser flag. These
are the only four rows where the two runtimes disagree on `passed`. Open as
003-OQ-008, which asks whether to match Python's permissiveness or tighten
Python to strict JSON.

### Object key order — 1 case

`json_schema/instance-repr-multi-key-dict`: the oracle renders
`{'b': 1, 'a': 2}` and the port `{'a': 2, 'b': 1}`. Python dicts preserve
insertion order; `serde_json::Map` without the `preserve_order` feature is a
`BTreeMap`. Turning the feature on would fix this row and change how every other
JSON object in the crate is ordered, which is a workspace-wide decision rather
than an assertion-layer one.

### `best_match` tie-breaks — 2 cases

`best_match/pattern-and-minlength` and `best_match/enum-and-type`. Both schemas
produce two root-level errors whose relevance keys are identical, so the winner
is decided by the order the validator yields them, which is the schema's key
insertion order in Python. The port cannot see that order — the schema arrives
through the same `serde_json::Map` as above — so it takes the crate's keyword
order instead.

The port's `best_match` also drops one component of the oracle's sort key:
whether the instance satisfies a `type` declared alongside the failing keyword.
Computing it needs the enclosing subschema, which the Rust crate does not return
with the error. It only ever separates two non-`type` errors under differently
typed subschemas, and no corpus case exercises that, but it is an approximation
rather than a transcription. FR-017's selection is a library heuristic either
way, which 003-OQ-010 says explicitly.

# Evidence manifest

A third harness, same two-half shape, for the document
`EvidenceCollector::publish` writes.

## Shape

| Half | Where | What it does |
|---|---|---|
| Oracle | `probe_evidence_manifest.py` | Drives the Python collector over a fixed scenario and records the published `evidence.json` **and the contents of every file it wrote** into `corpus/evidence_manifest.expected.json`. |
| Port | `crates/termproof/tests/differential_evidence_manifest.rs` | Builds the same scenario through the Rust collector and compares the whole recording. |

Unlike the other two, there is no corpus of cases: one document shape is built
by calling an API rather than by replaying data, so the scenario **is** the code
in each half and the two are transcriptions of one another. They are short and
commented line-for-line; keep them in step.

## Why it exists

`termproof.collector` was written to mirror `termproof::evidence::collector`
field for field, and the mirror was checked by a Python unit test that spelled
the Rust field names out — a list derived by *reading* the Rust structs, never
by running them. That can catch a rename on the Python side and nothing else:
not a rename on the Rust side, not a field added to one implementation and not
the other, not a value the two spell differently.

Running both and diffing found the claim was very nearly true. Every manifest
key, every value, the `step-NN-label` filename scheme, the dedup verdict and
its `same_as` back-reference, the `kind` spelling, the recordings and their
omission when empty — all identical. One thing was not: **Python appended a
trailing newline to each `step-NN.txt` and Rust wrote the screen verbatim.**
Four files differed under manifests that agreed byte-for-byte.

That is why this harness compares the written files and not just the document.
A manifest is a set of paths, and agreeing on paths is not agreeing on files.
Python was changed to match Rust, which writes what an assertion was actually
evaluated against with nothing added to it.

The same reasoning brought a cast into the scenario. After publishing, each half
writes a fixed asciinema v2 file into the publish directory and runs
`append_checkpoint_frames` over the captured steps, so the appended evidence
sequence is compared byte-for-byte along with the step text. A manifest agreeing
about a recording's path is not agreeing about the recording, and the cast is
what a reviewer actually watches.

There are two of them, and each is there for something the other cannot reach:

- `session-with-checkpoints.cast` runs at the default hold, so the corpus is
  what stops the two implementations' defaults drifting apart. Its base sets a
  scroll region, the state a full-screen TUI leaves behind, so the repaint
  prefix that has to undo it is recorded too.
- `session-with-fractional-hold.cast` passes an explicit `0.2`, which the
  default cast cannot cover, over a base ending on a seventh decimal — the only
  input shape that tells the two languages' rounding apart.

They also hold the two event encoders together. `serde_json` writes compact
separators and raw UTF-8 where Python's `json` defaults to neither, and Rust
rounds by scaling and breaking halves away from zero where Python's
`round(at, 6)` rounds the exact decimal and breaks halves to even. Both are
pinned explicitly on the Python side, and this is what would catch either
drifting back.

The seventh decimal is the whole point of that second base, and it is worth
saying why, because the obvious choice does not work. Over a whole-decimal base
the two rounding rules agree on every frame, so a corpus recorded from one
regenerates byte-for-byte with the Python transcription reverted to
`round(at, 6)` and the differential test cannot see the difference either. A
base of `0.5000005` — which is what a Rust-recorded cast ends on, since
`CastRecorder` writes `as_secs_f64()` unrounded — separates them at three of the
eight appended frames.

The same reasoning brought `record_session` in. Its outcome is a string in the
manifest — the `error` field of a `Recording`, prefixed with the name of the
step that failed — and "which step failed" is only useful to a reader if it does
not depend on which implementation produced the run. Each half drives it once
per outcome, over publishers that differ only in the seam under test:

| recording | what it pins |
|---|---|
| `recorded` | all five steps succeed: the cast, the evidence appended to it, the video, the URL |
| `unsaveable` | step 1 refusing — Python raises, Rust returns `Err`, both write `save cast: disk on fire` |
| `silent-save` | step 1 reporting success and writing nothing, which is still step 1 |
| `no-converter` | a publisher with no video converter, which is the `convert` step failing |
| `bad-encode` | a conversion that fails, and the upload that must not follow it |
| `silent-encode` | step 3 reporting success and writing nothing — the `silent-save` guard, one step down |
| `no-url` | an upload that declines, which costs the URL and not the video |
| `blank-url` | an upload that returns `""`, which both sides have to reject rather than record |
| *(empty label)* | the one input on which the two filename schemes could part |

The recordings' own casts and videos land in the publish directory, so they are
compared as files too, not only as paths.

The empty-label case is there because a recording's `cast` and `video` are
strings in the manifest and the two implementations build them differently at
exactly one input: Rust goes through `store::sanitize_component`, which
substitutes `default` for a component that sanitises to nothing, and Python's
`_sanitize` returns `""`. `_recording_file_stem` applies the same fallback so
the two agree, and this case is what holds it there. `CapturedStep.file_stem`
still differs the same way for the same input — pre-existing, not driven by this
scenario, and listed under "outside" below.

Two failures are deliberately absent:

- **An append that fails.** Its message comes from `append_checkpoint_frames`,
  which words its complaints differently in the two languages — `empty cast
  file` against `<path> is empty: a cast has a header line` — so recording it
  here would freeze a divergence in the corpus rather than check a shared
  surface. Each implementation covers it in its own unit tests.
- **An upload that declines *with a reason*.** Rust reads
  `ArtifactUploader::last_error()`; Python's `UploaderLike` has no such
  accessor, so a Python uploader says why by raising. `no-url` and `blank-url`
  therefore pin the *shared fallback* — `upload: uploader returned no URL`,
  emitted when there is no reason to be had — and not the shipped behaviour:
  `FallbackUploader`,
  the only non-test `ArtifactUploader` in the crate, sets `last_error` on every
  failure, so in practice Rust writes `upload: all uploaders returned no URL`
  where Python writes `upload: uploader returned no URL`. That disagreement is
  real and is recorded here rather than in the corpus, because pinning it would
  make the harness certify a divergence.

## What is deliberately neutralised

Three things in the scenario are properties of the machine rather than of either
implementation, and both halves handle them the same way:

- **The rasteriser.** `ScreenshotRenderer` shells out to `rsvg-convert`, so on a
  host without it every step would record a render error whose text belongs to
  the operating system. Both halves stub the tool and write a fixed byte, so a
  screenshot is recorded on every host.
- **The video encoder.** Rust's `CastVideoConverter` shells out to
  `rsvg-convert` and `ffmpeg`; the Rust half stubs the tool runner and the
  Python half stands in a converter that writes the same fixed byte. Neither the
  frame count nor the encoder reaches the manifest — the video path and the file
  at it are what have to agree.
- **The publish directory**, which is a fresh temporary directory. Both halves
  substitute it for `@DIR` before comparing.

Nothing else is normalised. In particular the file *contents* are compared
literally, which is the check that found the divergence above.

## Regenerating the expectations

```sh
cd /path/to/termproof/python
TERMPROOF_PYTHON_REPO=$PWD uv run python \
    ../conformance/probe_evidence_manifest.py \
    > ../conformance/corpus/evidence_manifest.expected.json
```

Only regenerate deliberately: the file is the oracle's testimony, and quietly
re-recording it turns a failing comparison into a passing one without changing
any behaviour. If the Rust half is the one that changed, fix the Rust half.

## Reading the result

```sh
cargo test -p termproof --test differential_evidence_manifest
```

Pass or fail, with the two documents printed on failure. There is no agreement
ratchet here as there is for steps and assertions: the two implementations
either write the same document or they do not, and a partial score for a file
format is not a useful number.
