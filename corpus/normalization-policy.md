# TermProof Python Behavior Contract — Normalization Policy

Part of RUST-001 (issue #94): freeze the current Python implementation as the
executable compatibility oracle for the Rust migration.

This document defines, for every committed fixture under `corpus/`, which
values are normalized before comparison, what the canonical form is, and why.
**No unexplained differences are permitted**: any difference between a
regenerated fixture and the committed bytes must be attributable to one of the
rules below. Anything not listed here is compared byte-for-byte.

The generator that produces these fixtures is `scripts/generate_corpus.py`;
the drift gate that regenerates and diffs the whole corpus is
`python scripts/generate_corpus.py --check`. The exact Python oracle commit is
recorded in `corpus/oracle.json` (see "Oracle record" below).

---

## 1. Why normalizations exist

The Python implementation is the executable oracle, but a handful of outputs
are inherently environment- or tool-dependent even when the *behavior* is
perfectly deterministic:

| Source of instability | Example |
| --- | --- |
| Wall-clock timing | `duration_seconds`, JUnit `time`, report `- Duration:` |
| Machine host / environment | JUnit `hostname`, cast header `env`/`command` |
| Build provenance | report `- Binary:`, `- Version:`, `- Git commit:` |
| Absolute checkout paths | `artifacts` paths, report evidence links, JUnit `system-out` |
| Recorder internals | asciinema cast per-event wall-clock timestamps |
| Font rendering / Pillow version | PNG bytes for the same screen text |

The frozen contract is the *semantic behavior* (what text appears, in what
order; what exit codes and result fields are produced; which artifacts exist),
not the incidental bytes that legitimately vary across machines. Each rule
below states the minimal normalization that removes only the named instability
and preserves everything else.

---

## 2. Normalization rules

### 2.1 `duration_seconds` → `0.0` (JSON)

- **Where:** `normalize_json_value` in `scripts/generate_corpus.py`; applies to
  every `result.json` fixture and the aggregate `corpus/reports/result.json`.
- **Rule:** any `duration_seconds` numeric value is replaced with `0.0`.
- **Why:** wall-clock run duration varies by machine load, scheduler, and PTY
  timing. The Rust conformance gate compares structure, fields, and pass/fail
  semantics, not how many milliseconds a Python run took.

### 2.2 Artifact paths → basenames (JSON)

- **Where:** `normalize_artifact_map` in the generator.
- **Rule:** every value in the `artifacts` map of `result.json` is replaced by
  the path basename (e.g. an absolute `/Users/.../runs/.../session.cast` becomes
  `session.cast`). The single exception is `cache`, replaced by the literal
  token `<cache>`.
- **Why:** the runner writes artifacts into timestamped, absolute run
  directories that differ per checkout and per run. The contract is *which
  artifact names exist and what they are*, not the absolute location.

### 2.3 Step screens: strip trailing whitespace per line

- **Where:** `_stable_screen` in the generator; applied to every `screen` field
  inside `steps` of `result.json`.
- **Rule:** each line's trailing whitespace is stripped.
- **Why:** PTY emulators pad lines to the terminal width; the trailing padding
  depends on the emulator's column count and timing, not on the application's
  behavior.

### 2.4 Markdown report: duration and artifact basenames

- **Where:** `normalize_report_md` in the generator; applies to
  `corpus/runs/*/report.md` and the aggregate `corpus/reports/latest-report.md`.
- **Rule:**
  - `- Duration: <value>` is replaced by `- Duration: \`0.00s\``.
  - Any `- <marker>: \`<path>\`` line whose value looks like a path is reduced
    to the path basename.
- **Why:** same timing and absolute-path rationale as 2.1/2.2.

### 2.5 Aggregate latest-report: build provenance tokens

- **Where:** `normalize_latest_report_md` in the generator; applies only to
  `corpus/reports/latest-report.md`.
- **Rule:**
  - `- Binary: <anything>` → `- Binary: \`python3\``
  - `- Version: <anything>` → `- Version: \`Python 3.x\``
  - `- Git commit: <anything>` → `- Git commit: \`<oracle-commit>\``
  - Evidence links `[name](/abs/path/to/file)` → `[name](file)` (basename).
  - Any remaining timestamped run-directory token → `/<run-dir>`.
- **Why:** the aggregate report embeds machine state (interpreter path,
  exact version string, working-tree commit). The contract is that these
  sections exist and are populated, not their exact environment-specific
  values. The pinned oracle commit is recorded in `corpus/oracle.json`.

### 2.6 JUnit XML: timestamp, hostname, time, and build-provenance tokens

- **Where:** `normalize_junit_xml` in the generator; applies to
  `corpus/reports/junit.xml`.
- **Rule:**
  - `timestamp="..."` → `timestamp="1970-01-01T00:00:00+00:00"`
  - `hostname="..."` → `hostname="localhost"`
  - ` time="..."` → ` time="0.000"`
  - `<property name="version" value="...">` → `value="Python 3.x"`
  - `<property name="git_commit" value="...">` → `value="<oracle-commit>"`
  - Inside `system-out`/`failure` text, any `<label>: <abs-path>/<file>` is
    reduced to `<label>: <file>`.
- **Why:** timestamps and hostnames are wall-clock/host values; duration tokens
  are timing values; the `version`/`git_commit` properties embed the
  interpreter and checkout commit of whichever machine generated the XML (CI
  runs the corpus on Python 3.11/3.12/3.13 at the PR head — different from the
  oracle's 3.12.12 at the oracle commit). The XML *structure*, test names,
  pass/fail counts, and message text are preserved verbatim.

### 2.7 Cast (asciinema): canonical header + merged output events

- **Where:** `normalize_cast` in the generator; applies to every
  `corpus/runs/*/session.cast`.
- **Rule:** the cast is rewritten to a canonical form:
  - Header: `{"version": 2, "width": <w>, "height": <h>, "timestamp": 0,
    "command": "", "env": {}}`, where width/height come from the recorded
    header (or its `term.cols`/`term.rows` if present).
  - All `o` (output) events are concatenated in order into a single event
    `[0.0, "o", "<merged>"]`. Non-output events are dropped.
- **Why:** the asciinema recorder writes per-event wall-clock timestamps and
  header environment/command metadata that differ per run and per recorder
  version. The terminal *output bytes and their order* are the contract; the
  canonical form captures exactly that deterministically.

### 2.8 PNG screenshots: byte-stable only when Pillow matches the oracle

- **Where:** `normalize_png_bytes` in the generator.
- **Rule:** when the local Pillow version equals the version recorded in
  `corpus/oracle.json`, PNG bytes are compared verbatim (base64-encoded so the
  drift diff is textual). When the Pillow version differs, PNG bytes are
  replaced by a semantic descriptor `<png <FORMAT> <WxH>>` — dimensions and
  decodability only.
- **Why:** font rendering and rasterization are byte-stable within a pinned
  Pillow version, but legitimately differ across versions. The conformance gate
  pins the oracle Pillow version and requires byte-identical PNGs; on a machine
  with a different Pillow, the descriptor still verifies the artifact exists,
  decodes, and has the right dimensions. (The committed corpus uses the SVG
  screen renderer for screenshot fixtures; this rule guards PNG renders used
  by `--screen-renderer png` and the visual-diff flow.)

### 2.9 Oracle record: environment metadata excluded from comparison

- **Where:** `normalize_oracle_json` + `write_oracle(check=True)`.
- **Rule:** `corpus/oracle.json` records `generated_at`, `python_version`, and
  `pillow_version`, but drift comparison ignores all three; the committed
  file's values are preserved during `--check`.
- **Why:** `generated_at` is generation metadata; `python_version` /
  `pillow_version` describe the machine that produced the committed fixtures.
  CI regenerates the corpus on any supported Python (3.11/3.12/3.13) with a
  potentially different Pillow, so comparing those fields would fail on every
  machine but the oracle's. The contract fields — `oracle_commit`,
  `termproof_version`, `generator` — are compared byte-for-byte. PNG
  byte-comparison still keys off the *committed* `pillow_version` (rule 2.8),
  so the recorded value remains load-bearing even though drift ignores it.

### 2.10 Diff contract: absolute paths tokenized

- **Where:** `write_diff_contract` in the generator; applies to
  `corpus/diff/diff-result.json` and the baseline SVG under
  `corpus/diff/baselines/`.
- **Rule:** absolute temporary-directory paths in `detail` strings are replaced
  with `<tmp>` / `<baseline>` tokens before the fixture is written.
- **Why:** the visual-diff flow embeds artifact paths that depend on the
  checkout; the contract is the diff *semantics* (a one-line screen drift
  produces a detected difference with the expected fields), not the absolute
  path string.

---

## 3. Values that are NEVER normalized

These are contract-critical and compared byte-for-byte (or semantically where
noted). If a regenerated fixture differs here, that is a real regression:

- **Exit codes** — `corpus/cli/exit-codes.json` records real exit codes from
  the oracle (0 for success, 1 for recipe failure/validation failure, argparse
  codes for usage errors, etc.).
- **CLI help text** — `corpus/cli/help/*.txt` is the verbatim output of each
  public command's `--help`.
- **Flag inventory** — `corpus/cli/flags.json` is the exact public flag set for
  `run` and every subcommand.
- **Config precedence resolution** — `corpus/config/precedence/*.json` records
  the *resolved* `idle_cap_seconds`, docker defaults, and session backend for
  each documented discovery location (builtin → legacy user → termproof user →
  legacy project → termproof project → explicit `--config`).
- **Recipe fixtures** — `corpus/recipes/**` are the canonical inputs; changing
  them changes the contract.
- **Pass/fail semantics** — `passed`, `score`, `exit_code`, assertion
  `detail` text, step `detail` text in `result.json` fixtures.
- **Video contract** — video *bytes* are never compared (encoder/platform
  dependent). The frozen contract is: requesting `--video` with tools present
  yields a `session.mp4` artifact; with tools missing, an exact loud warning is
  emitted and the artifact is omitted. `corpus/video/missing-tools-warning.txt`
  and `corpus/video/presence-contract.json` capture this verbatim.
- **Cache contract** — `corpus/cache/cache-key-inputs.json` records the exact
  SHA-256 cache key inputs (recipe source path, renderer, argv, out dir, screen
  renderer, video backend, video flags) and the resulting key.
- **Failure/partial artifacts** — `corpus/runs/fail-exit-code/*` preserves the
  partial evidence a failing run still produces (`result.json` with
  `passed: false` and non-zero `exit_code`, report, final text/screenshot,
  cast, exit-code file).

---

## 4. Oracle record

`corpus/oracle.json` records:

```json
{
  "oracle_commit": "165c367ca0b0e2a4663a8773ee18b67c2264979c",
  "generator": "scripts/generate_corpus.py",
  "pillow_version": "<Pillow version at generation>",
  "python_version": "<CPython version at generation>",
  "termproof_version": "0.2.1"
}
```

`oracle_commit` is the exact Python commit the corpus was generated from (the
current `origin/main` at the time of RUST-001). Conformance CI must run the
Rust implementation against this corpus and record zero unexplained
differences.

---

## 5. Drift gate

`python scripts/generate_corpus.py --check` regenerates the entire corpus into
a temporary directory, applies the rules above to both sides, and byte-compares
every fixture. Any mismatch (missing file, added file, or differing content)
fails the gate. The same check is wired into `tests/test_corpus_drift.py`
(`CorpusDriftTest.test_drift_check_passes`) so it runs in the normal test
suite, and `CorpusInventoryTest` asserts every acceptance category is present.

To intentionally update the contract (e.g. after an approved Python behavior
change), regenerate with `python scripts/generate_corpus.py`, review the diff
against this policy, and commit the new fixtures together with the behavior
change — never hand-edit fixtures.
