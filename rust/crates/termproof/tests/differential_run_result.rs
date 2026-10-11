//! Port half of the run-result differential harness.
//!
//! Builds the scenario `conformance/probe_run_result.py` builds, serialises
//! each [`RunResult`] to a JSON document, and compares the documents — key
//! order normalised, not the bytes of `result.json` — against what the
//! oracle recorded in `conformance/corpus/run_result.expected.json`. The
//! scenario hand-sets `Some(RESULT_SCHEMA_VERSION)`, transcribing the stamp
//! `Runner::run` writes rather than calling it, so this test does not prove
//! the runner still stamps its results.
//!
//! # Why this exists
//!
//! A `RunResult` outlives the process that produced it — the run cache reads
//! it back, the CI evidence step aggregates it, `parity` compares two of
//! them — so its JSON keys are a contract consumers read, whichever
//! implementation wrote the file. Until this test, nothing compared the two
//! serialisations: a field added to one side, renamed on one side, or spelled
//! with a different type moved no number anywhere (#209).
//!
//! # The one allowed difference
//!
//! The documents are compared whole except for
//! [`ALLOWED_RUST_ONLY_KEYS`]: this implementation stamps every result it
//! writes with `result_version` (`RESULT_SCHEMA_VERSION`) and the Python
//! implementation writes no such key at all — item 1 of #209, recorded here
//! rather than fixed in either implementation. The allowance is asserted in
//! both directions below, so it cannot outlive the divergence it records:
//! if Python gains the key (the condition `result::can_read` names for
//! removing its absent rule) or Rust stops writing it, this test fails and
//! the allowance is revisited deliberately instead of quietly widening.
//!
//! ```sh
//! cargo test -p termproof --test differential_run_result -- --nocapture
//! ```

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

use termproof::result::{AssertionResult, RunResult, StepResult, RESULT_SCHEMA_VERSION};

/// Top-level keys the Rust document carries that the Python one does not.
///
/// Exactly one, and named rather than diffed away: `result_version`, which
/// this build writes as [`RESULT_SCHEMA_VERSION`] and Python does not write
/// at all (#209). Anything else differing — a key added, removed or renamed
/// on either side, a nested step or assertion key, a value's JSON type —
/// fails the comparison below.
const ALLOWED_RUST_ONLY_KEYS: [&str; 1] = ["result_version"];

fn expected_path() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../../conformance/corpus/run_result.expected.json")
}

/// The fixed scenario. Keep in step with probe_run_result.py.
fn scenario() -> Vec<RunResult> {
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
            score: 0.0,
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
            artifacts: BTreeMap::from([(
                "screenshot".to_string(),
                "/tmp/evidence/final.png".to_string(),
            )]),
        },
        RunResult {
            result_version: Some(RESULT_SCHEMA_VERSION),
            recipe_name: "empty".to_string(),
            passed: true,
            exit_code: None,
            duration_seconds: 0.0,
            priority: "P2".to_string(),
            execution: "scripted".to_string(),
            renderer: "default".to_string(),
            score: 1.0,
            steps: vec![],
            assertions: vec![],
            artifacts: BTreeMap::new(),
        },
    ]
}

#[test]
fn the_serialised_run_result_matches_the_python_document() {
    let recorded = std::fs::read_to_string(expected_path()).expect("oracle document readable");
    let expected: serde_json::Value =
        serde_json::from_str(&recorded).expect("recorded oracle document is JSON");
    let expected = expected.as_array().expect("the recording is an array");

    let mut actual: Vec<serde_json::Value> =
        scenario().iter().map(RunResult::to_json_value).collect();
    assert_eq!(actual.len(), expected.len(), "scenario size drifted");

    for (rust, python) in actual.iter_mut().zip(expected) {
        let python = python.as_object().expect("a Python result is an object");
        let rust = rust.as_object_mut().expect("a Rust result is an object");
        for key in ALLOWED_RUST_ONLY_KEYS {
            // Both directions, so the allowance fails when the divergence it
            // records stops existing (#209): Rust must still write the key,
            // with this build's version, and the recorded Python document
            // must still lack it.
            assert!(
                !python.contains_key(key),
                "the Python document now carries `{key}`; remove the allowance \
                 in this test and see `result::can_read` on the absent rule"
            );
            assert_eq!(
                rust.remove(key),
                Some(serde_json::json!(RESULT_SCHEMA_VERSION)),
                "Rust no longer writes `{key}`; remove the allowance in this test"
            );
        }
    }

    assert_eq!(
        serde_json::to_string_pretty(&serde_json::Value::Array(expected.clone())).unwrap(),
        serde_json::to_string_pretty(&serde_json::Value::Array(actual)).unwrap(),
        "the Rust run-result document diverged from the recorded Python one \
         beyond the allowed keys; regenerate the oracle only if the Python \
         side is the one that changed — see conformance/README.md"
    );
}
