//! Port half of the report differential harness.
//!
//! Builds the scenarios `conformance/probe_report.py` builds, renders each
//! through [`generate_markdown`], and compares the markdown per case
//! against what the oracle recorded in
//! `conformance/corpus/report.expected.json`.
//!
//! # Why this exists
//!
//! Both CLIs write this aggregate document to disk, and a reader comparing
//! two runs — or one run verified in each language — reads whichever the
//! producing implementation emitted. Until this test nothing compared the
//! two renderings: a section present on one side, a link spelled
//! differently, a blank line moved, all moved no number anywhere (#209).
//!
//! The [`RunResult`] here is `result::RunResult`, the canonical one
//! `evidence::report` reads — not `models::RunResult`.
//!
//! # Allowed differences (#209)
//!
//! The bare, multiline and empty cases must match byte for byte. The rest
//! compare whole apart from the named allowances below, each asserted so
//! it fails when the divergence it records stops existing:
//!
//! - [`PYTHON_ONLY_BUILD_INFO_SECTION`] — the Python generator takes a
//!   `build_info` and renders `## Build Provenance`; this crate's
//!   [`generate_markdown`] takes no such parameter and renders no such
//!   section.
//! - [`PYTHON_ONLY_BEFORE_AFTER_SECTION`] — likewise `before_after`: the
//!   Python generator embeds its markdown under the header, this one has
//!   no parameter for it. The embedded text itself is tied to this
//!   crate's real `before_after` rendering below, so only the embedding
//!   is Python-only.
//! - [`DIVERGENT_EVIDENCE_ROWS`] — an artifact whose value is `""` is
//!   suppressed by the Python truthiness check (`if value:`) and rendered
//!   here as `[screenshot]()`.
//!
//! Anything else differing — header counts, table rows, detail sections,
//! blank lines, a new or renamed case — fails the comparison. Nothing in
//! either implementation changed to add this harness.
//!
//! ```sh
//! cargo test -p termproof --test differential_report -- --nocapture
//! ```

// The report is the `evidence` module, so there is no markdown to compare
// without it. The oracle has no equivalent switch — Python builds one
// package — so this is a feature gate on the port half only.
#![cfg(feature = "evidence")]

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

use termproof::before_after::build_before_after;
use termproof::evidence::report::generate_markdown;
use termproof::result::{AssertionResult, RunResult, StepResult, RESULT_SCHEMA_VERSION};

/// The `## Build Provenance` block, byte for byte as the Python generator
/// inserts it between the header blank line and the table, for this
/// scenario's record (#209). This side has no rendering to derive it
/// from — `generate_markdown` takes no build info — so it is pinned as a
/// literal: Python rewording a line, moving the section, or this side
/// growing one all fail below.
const PYTHON_ONLY_BUILD_INFO_SECTION: &str = "## Build Provenance\n\n\
    - Mode: `installed`\n\
    - Command: `/nonexistent-termproof-report/built --serve`\n\
    - Binary: `/nonexistent-termproof-report/built`\n\
    - Version: `tool 1.2.3 / second line`\n\
    - Git commit: `None`\n\
    - Verified: `no`\n\n";

/// What the Python generator inserts for this scenario's before/after,
/// including its extra leading blank line (#209). The delta text is tied
/// to `build_before_after`'s own rendering in the test, so the only
/// Python-only bytes here are the embedding blanks.
const PYTHON_ONLY_BEFORE_AFTER_SECTION: &str =
    "\n**Behavioral deltas:**\n\n- login [default]: PASS -> FAIL\n\n";

/// Table rows whose evidence cell diverges, as `(python, rust)` (#209):
/// empty-string artifact values, suppressed there and rendered as empty
/// links here. The `no-evidence` row agrees (`-` on both sides) and is
/// covered by the whole-document line comparison, not listed here.
const DIVERGENT_EVIDENCE_ROWS: [(&str, &str); 2] = [
    (
        "| `blank-evidence` | `default` | `P0` | `scripted` | PASS | 1.00 | - |",
        "| `blank-evidence` | `default` | `P0` | `scripted` | PASS | 1.00 | \
         [screenshot]() / [video]() |",
    ),
    (
        "| `mixed-evidence` | `default` | `P0` | `scripted` | FAIL | 0.00 | [cast](run.cast) |",
        "| `mixed-evidence` | `default` | `P0` | `scripted` | FAIL | 0.00 | \
         [screenshot]() / [cast](run.cast) |",
    ),
];

/// The case names the oracle must record. `expected_cases` collects
/// them into a sorted [`BTreeMap`], so the probe order here is only for
/// readability. A case added to one half only fails there rather than
/// passing uncompared.
const CASE_NAMES: [&str; 6] = [
    "bare-mix",
    "with-build-info",
    "with-before-after",
    "artifact-emptiness",
    "multiline-details",
    "empty-results",
];

fn expected_path() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("../../../conformance/corpus/report.expected.json")
}

fn expected_cases() -> BTreeMap<String, String> {
    let recorded = std::fs::read_to_string(expected_path()).expect("oracle document readable");
    let document: serde_json::Value =
        serde_json::from_str(&recorded).expect("recorded oracle document is JSON");
    let cases = document["cases"].as_array().expect("cases is an array");
    assert_eq!(
        cases.len(),
        CASE_NAMES.len(),
        "the recorded case count drifted from CASE_NAMES; a duplicate \
         name would otherwise collapse silently in the map"
    );
    let map: BTreeMap<String, String> = cases
        .iter()
        .map(|case| {
            (
                case["name"].as_str().expect("case name").to_string(),
                case["markdown"]
                    .as_str()
                    .expect("case markdown")
                    .to_string(),
            )
        })
        .collect();
    assert_eq!(
        map.keys().map(String::as_str).collect::<Vec<_>>(),
        {
            let mut names = CASE_NAMES.to_vec();
            names.sort_unstable();
            names
        },
        "the recorded cases drifted from CASE_NAMES in this test"
    );
    map
}

/// The pass/fail pair the first three cases share. Keep in step with
/// probe_report.py.
fn pair() -> Vec<RunResult> {
    vec![
        RunResult {
            result_version: Some(RESULT_SCHEMA_VERSION),
            recipe_name: "login".to_string(),
            passed: false,
            exit_code: Some(1),
            duration_seconds: 1.25,
            priority: "P0".to_string(),
            execution: "scripted".to_string(),
            renderer: "default".to_string(),
            score: 0.5,
            steps: vec![StepResult {
                name: "menu-open".to_string(),
                passed: true,
                detail: "screen contains 'MENU'".to_string(),
                screen: "MENU\nitem one".to_string(),
            }],
            assertions: vec![AssertionResult {
                name: "screen_contains".to_string(),
                passed: false,
                detail: "menu missing".to_string(),
            }],
            // `notes` is outside the evidence key list both sides walk.
            artifacts: BTreeMap::from([
                (
                    "screenshot".to_string(),
                    "/tmp/evidence/final.png".to_string(),
                ),
                ("notes".to_string(), "ignored.txt".to_string()),
            ]),
        },
        RunResult {
            result_version: Some(RESULT_SCHEMA_VERSION),
            recipe_name: "search".to_string(),
            passed: true,
            exit_code: Some(0),
            duration_seconds: 0.5,
            priority: "P1".to_string(),
            execution: "agent-driven".to_string(),
            renderer: "ink".to_string(),
            score: 1.0,
            steps: vec![StepResult {
                name: "type-query".to_string(),
                passed: true,
                detail: "typed 'hello'".to_string(),
                screen: "hello".to_string(),
            }],
            assertions: vec![AssertionResult {
                name: "exit_code".to_string(),
                passed: true,
                detail: "exit 0".to_string(),
            }],
            artifacts: BTreeMap::from([
                ("cast".to_string(), "search.cast".to_string()),
                ("screenshot".to_string(), "search.png".to_string()),
            ]),
        },
    ]
}

/// A result carrying only what `before_after` reads.
fn outcome(recipe_name: &str, renderer: &str, passed: bool) -> RunResult {
    RunResult {
        result_version: Some(RESULT_SCHEMA_VERSION),
        recipe_name: recipe_name.to_string(),
        passed,
        exit_code: Some(i32::from(!passed)),
        duration_seconds: 0.0,
        priority: "P0".to_string(),
        execution: "scripted".to_string(),
        renderer: renderer.to_string(),
        score: if passed { 1.0 } else { 0.0 },
        steps: vec![],
        assertions: vec![],
        artifacts: BTreeMap::new(),
    }
}

fn bare(
    recipe_name: &str,
    passed: bool,
    score: f64,
    artifacts: BTreeMap<String, String>,
) -> RunResult {
    let mut result = outcome(recipe_name, "default", passed);
    result.score = score;
    result.artifacts = artifacts;
    result
}

/// The Python document reconstructed from this side's: `section`
/// inserted where the Python generator puts it, between the header's
/// blank line and the table.
fn with_python_only_section(rust: &str, section: &str) -> String {
    let (head, tail) = rust
        .split_once("\n\n")
        .expect("the report header is followed by a blank line");
    format!("{head}\n\n{section}{tail}")
}

#[test]
fn the_aggregate_markdown_report_matches_the_python_one() {
    let expected = expected_cases();

    // Bare results: byte for byte, no allowance.
    assert_eq!(
        generate_markdown(&pair()),
        expected["bare-mix"],
        "bare-mix diverged; regenerate the oracle only if the Python side \
         is the one that changed — see conformance/README.md"
    );

    // Build provenance is a Python-only section (#209): this side must
    // still lack it, and inserting the pinned block must reproduce the
    // Python document exactly, so any other drift in the case fails.
    let rust = generate_markdown(&pair());
    assert!(
        !rust.contains("## Build Provenance"),
        "the Rust report now renders build provenance; remove the \
         PYTHON_ONLY_BUILD_INFO_SECTION allowance in this test"
    );
    assert_eq!(
        with_python_only_section(&rust, PYTHON_ONLY_BUILD_INFO_SECTION),
        expected["with-build-info"],
        "with-build-info diverged beyond the Python-only section"
    );

    // Before/after likewise (#209), tied first to this crate's own
    // rendering of the same comparison so the pinned text cannot rot.
    let before_after = build_before_after(
        vec![
            outcome("login", "default", true),
            outcome("search", "ink", true),
        ],
        pair(),
    );
    assert_eq!(
        before_after.to_markdown(),
        "**Behavioral deltas:**\n\n- login [default]: PASS -> FAIL\n",
        "the Rust before/after rendering moved; update \
         PYTHON_ONLY_BEFORE_AFTER_SECTION in this test"
    );
    assert!(
        !rust.contains("Behavioral deltas"),
        "the Rust report now embeds before/after deltas; remove the \
         PYTHON_ONLY_BEFORE_AFTER_SECTION allowance in this test"
    );
    assert_eq!(
        with_python_only_section(&rust, PYTHON_ONLY_BEFORE_AFTER_SECTION),
        expected["with-before-after"],
        "with-before-after diverged beyond the Python-only section"
    );

    // Empty artifacts agree; empty-string values diverge on exactly the
    // pinned rows (#209) and nowhere else in the document.
    let artifacts = generate_markdown(&[
        bare("no-evidence", true, 1.0, BTreeMap::new()),
        bare(
            "blank-evidence",
            true,
            1.0,
            BTreeMap::from([
                ("screenshot".to_string(), String::new()),
                ("video".to_string(), String::new()),
            ]),
        ),
        bare(
            "mixed-evidence",
            false,
            0.0,
            BTreeMap::from([
                ("screenshot".to_string(), String::new()),
                ("cast".to_string(), "run.cast".to_string()),
            ]),
        ),
    ]);
    let python_lines: Vec<&str> = expected["artifact-emptiness"].split('\n').collect();
    let rust_lines: Vec<&str> = artifacts.split('\n').collect();
    assert_eq!(
        rust_lines.len(),
        python_lines.len(),
        "artifact-emptiness changed shape, not just evidence cells"
    );
    let differing: Vec<(&str, &str)> = python_lines
        .iter()
        .copied()
        .zip(rust_lines)
        .filter(|(python, rust)| python != rust)
        .collect();
    assert_eq!(
        differing.as_slice(),
        &DIVERGENT_EVIDENCE_ROWS[..],
        "artifact-emptiness diverged beyond the pinned evidence rows; \
         if empty-string artifacts now agree, remove the allowance"
    );

    // Multiline details are embedded verbatim on both sides.
    let mut chatty = outcome("chatty", "default", false);
    chatty.steps = vec![StepResult {
        name: "boot".to_string(),
        passed: false,
        detail: "first line\nsecond line".to_string(),
        screen: String::new(),
    }];
    chatty.assertions = vec![AssertionResult {
        name: "contains".to_string(),
        passed: false,
        detail: "wanted X\n\ngot Y".to_string(),
    }];
    assert_eq!(generate_markdown(&[chatty]), expected["multiline-details"]);

    // No results at all is legal on both sides: header and table only.
    assert_eq!(generate_markdown(&[]), expected["empty-results"]);
}
