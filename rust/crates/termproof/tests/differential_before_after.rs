//! Port half of the before/after differential harness.
//!
//! Replays `conformance/corpus/before_after_cases.json` through
//! `termproof::before_after` and compares the whole recording — every delta
//! field under the name it carries, in the order it came out, plus the rendered
//! markdown — against what the oracle recorded in
//! `conformance/corpus/before_after.expected.json`.
//!
//! # Why this exists
//!
//! Until #204 these were not two bindings of one thing. They were separate
//! implementations that disagreed on the delta field names, on both markdown
//! forms and on the order the deltas came out in, and nothing failed: each side
//! asserted its own wording in its own unit tests and no test ever ran both. A
//! consumer with a validator in each language could delete its local copy on the
//! Rust side and not on the Python side, for the same feature — which is what
//! "shared" was supposed to mean.
//!
//! Both halves of the recording are compared and for different reasons. The
//! **deltas** are the API a consumer's own reporter reads, so the field names
//! decide whether upstream can be swapped in for a local copy. The **markdown**
//! is the report a human reviewer reads, so a divergence there is visible in
//! published output rather than only in a type signature.
//!
//! There is no agreement ratchet here, as there is for steps and assertions:
//! the two implementations either produce the same report or they do not, and a
//! partial score for a report format is not a useful number.
//!
//! ```sh
//! cargo test -p termproof --test differential_before_after
//! ```

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

use termproof::before_after::build_before_after;
use termproof::result::{RunResult, RESULT_SCHEMA_VERSION};

fn corpus_dir() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("../../../conformance/corpus")
}

/// A `RunResult` carrying only the three fields this layer reads.
///
/// The rest are fixed rather than absent: the comparison reads `recipe_name`,
/// `renderer` and `passed` and nothing else, so anything varying here would be
/// measuring a different module.
fn result(spec: &serde_json::Value) -> RunResult {
    let passed = spec["passed"].as_bool().expect("passed is a bool");
    RunResult {
        result_version: Some(RESULT_SCHEMA_VERSION),
        recipe_name: spec["recipe"]
            .as_str()
            .expect("recipe is a string")
            .to_string(),
        passed,
        exit_code: Some(if passed { 0 } else { 1 }),
        duration_seconds: 0.0,
        priority: "P0".to_string(),
        execution: "scripted".to_string(),
        renderer: spec["renderer"]
            .as_str()
            .expect("renderer is a string")
            .to_string(),
        score: if passed { 1.0 } else { 0.0 },
        steps: vec![],
        assertions: vec![],
        artifacts: BTreeMap::new(),
    }
}

fn results(specs: &serde_json::Value) -> Vec<RunResult> {
    specs
        .as_array()
        .expect("a side is an array")
        .iter()
        .map(result)
        .collect()
}

#[test]
fn the_computed_deltas_match_the_python_recording() {
    let corpus = corpus_dir();
    let cases: serde_json::Value = serde_json::from_str(
        &std::fs::read_to_string(corpus.join("before_after_cases.json")).expect("cases readable"),
    )
    .expect("cases are JSON");
    let expected: serde_json::Value = serde_json::from_str(
        &std::fs::read_to_string(corpus.join("before_after.expected.json"))
            .expect("oracle recording readable"),
    )
    .expect("oracle recording is JSON");

    let actual: Vec<serde_json::Value> = cases
        .as_array()
        .expect("the corpus is an array of cases")
        .iter()
        .map(|case| {
            let outcome = build_before_after(results(&case["before"]), results(&case["after"]));
            serde_json::json!({
                "name": case["name"],
                // A list, not a set or a map: the order is part of what is
                // compared, and it is the half of this that a cosmetic refactor
                // is most likely to undo.
                "deltas": outcome.deltas.iter().map(|delta| serde_json::json!({
                    "recipe": delta.recipe,
                    "renderer": delta.renderer,
                    "before_outcome": delta.before_outcome,
                    "after_outcome": delta.after_outcome,
                    "explanation": delta.explanation(),
                })).collect::<Vec<_>>(),
                "markdown": outcome.to_markdown(),
            })
        })
        .collect();

    assert_eq!(
        serde_json::to_string_pretty(&expected).unwrap(),
        serde_json::to_string_pretty(&serde_json::Value::Array(actual)).unwrap(),
        "the Rust before/after report diverged from the recorded Python one; \
         regenerate the oracle only if the Python side is the one that changed \
         — see conformance/README.md"
    );
}
