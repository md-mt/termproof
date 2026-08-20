//! Canonical result model — mirrors `termproof/models.py`.
//!
//! JSON keys use `snake_case` to preserve byte-stable serialization.
//!
//! # Versioning
//!
//! A [`RunResult`] outlives the process that produced it: a report step reads
//! it, [`crate::parity`] compares two of them, and a human opens one months
//! later. So it carries [`RESULT_SCHEMA_VERSION`] in a `result_version` key,
//! and [`can_read`] says whether this build understands what it is looking at.
//!
//! **Absent is not a version.** A payload written by another implementation has
//! no `result_version` at all, and that is a different fact from "written one
//! version back". They are kept apart on purpose: the field is `Option<u32>`
//! rather than a `u32` that defaults to `1`, because a default would erase the
//! distinction at parse time, before any reader could act on it. See
//! [`can_read`] for the rule absent gets, and the condition under which that
//! rule is removed.

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// The `result_version` this build writes.
pub const RESULT_SCHEMA_VERSION: u32 = 1;

/// The oldest `result_version` this build reads: current, and one back.
///
/// One back rather than all-of-history because every version kept readable is
/// a shape that has to keep being handled; one back is enough for a reader and
/// a writer to be deployed in either order.
pub const OLDEST_READABLE_RESULT_VERSION: u32 = if RESULT_SCHEMA_VERSION > 1 {
    RESULT_SCHEMA_VERSION - 1
} else {
    1
};

/// Why a payload could not be read as a [`RunResult`].
#[derive(Debug, Clone, PartialEq, Eq, Error)]
pub enum ResultReadError {
    /// The payload declares a version outside the readable window.
    ///
    /// The message names the version found *and* the window, because an error
    /// that says only "unsupported" sends the reader to the source to find out
    /// what would have been supported.
    #[error(
        "result_version {found} is not readable by this build: it reads \
         {oldest}..={newest}, and payloads with no `result_version` at all"
    )]
    UnsupportedVersion {
        /// The version the payload declared.
        found: u32,
        /// Oldest version this build reads.
        oldest: u32,
        /// Newest version this build reads, i.e. the one it writes.
        newest: u32,
    },
    /// The payload is not shaped like a [`RunResult`].
    #[error("payload is not a RunResult: {message}")]
    Malformed {
        /// What went wrong.
        message: String,
    },
}

/// Whether this build can read a payload declaring `version`.
///
/// Two rules, deliberately separate:
///
/// - **`Some(v)`** — readable when `v` is in
///   `OLDEST_READABLE_RESULT_VERSION..=RESULT_SCHEMA_VERSION`.
/// - **`None`** — always readable, and *not* folded into that window.
///
/// Folding absent into the window as "version 0" would look harmless today and
/// break the first time [`RESULT_SCHEMA_VERSION`] is bumped: every payload from
/// an implementation that has no version field at all would fall out of the
/// window at once, and would surface as the comparison tool refusing to run
/// inside a change that had nothing to do with comparison.
///
/// # When the absent rule is removed
///
/// Not "eventually" — this condition, and only it: **delete the `None => true`
/// arm in the first release after the reference Python implementation writes
/// `result_version` into its own result payloads.** That is one observable
/// fact, checkable by looking at that implementation's result writer, not a
/// date and not a judgement call. Until it holds, absent means "written by
/// something that predates the version scheme", which is readable. Once it
/// holds, absent means "written by something older than every current writer",
/// which is not — and at that point `None` should return `false` and take the
/// same [`ResultReadError::UnsupportedVersion`] path.
pub fn can_read(version: Option<u32>) -> bool {
    match version {
        // See "When the absent rule is removed" above before changing this arm.
        None => true,
        Some(v) => (OLDEST_READABLE_RESULT_VERSION..=RESULT_SCHEMA_VERSION).contains(&v),
    }
}

/// [`can_read`], as a `Result` that names the version and the window.
pub fn check_readable(version: Option<u32>) -> Result<(), ResultReadError> {
    match version {
        v if can_read(v) => Ok(()),
        // Unreachable for `None` while the absent rule stands; written this way
        // so removing that rule needs no change here.
        None => Err(ResultReadError::UnsupportedVersion {
            found: 0,
            oldest: OLDEST_READABLE_RESULT_VERSION,
            newest: RESULT_SCHEMA_VERSION,
        }),
        Some(found) => Err(ResultReadError::UnsupportedVersion {
            found,
            oldest: OLDEST_READABLE_RESULT_VERSION,
            newest: RESULT_SCHEMA_VERSION,
        }),
    }
}

/// Result of a single step.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct StepResult {
    /// Step display name.
    pub name: String,
    /// Whether the step passed.
    pub passed: bool,
    /// Human-readable detail.
    pub detail: String,
    /// Screen snapshot at step boundary (normalized text).
    pub screen: String,
}

/// Result of a single assertion.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct AssertionResult {
    /// Assertion name / type.
    pub name: String,
    /// Whether the assertion passed.
    pub passed: bool,
    /// Human-readable detail.
    pub detail: String,
}

/// Canonical verification result — one recipe × one renderer.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct RunResult {
    /// Schema version of this payload, or `None` when it was written by
    /// something that does not version its results.
    ///
    /// Omitted from the JSON when `None`, so reading a foreign payload and
    /// writing it back does not launder it into a version-stamped one: this
    /// build did not produce it and must not claim to have.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub result_version: Option<u32>,
    /// Recipe identifier.
    pub recipe_name: String,
    /// Overall pass/fail.
    pub passed: bool,
    /// Process exit code, if available.
    pub exit_code: Option<i32>,
    /// Wall-clock duration in seconds.
    pub duration_seconds: f64,
    /// Priority label (P0/P1/P2).
    pub priority: String,
    /// Execution mode (`scripted`, `agent-driven`, …).
    pub execution: String,
    /// Renderer name (`default`, …).
    pub renderer: String,
    /// Fraction of assertions that held, in `0.0..=1.0`.
    ///
    /// **A run that asserted nothing scores `1.0`, not `0.0`.** That is part of
    /// this contract rather than a choice each producer makes, because a score
    /// is read comparatively: a consumer that scored the empty set `0.0` would
    /// publish numbers that look like these and rank against them wrongly. The
    /// reading is "no assertion failed", which is what an empty set reports;
    /// "nothing was verified" is carried by `assertions` being empty, and a
    /// caller that cares about it should read that rather than the score.
    ///
    /// [`score_from`] computes it from a name → passed map and
    /// [`RunResult::score_from_assertions`] from an [`AssertionResult`] list;
    /// both are the same rule, and neither should be re-derived by a caller.
    pub score: f64,
    /// Per-step results in order.
    pub steps: Vec<StepResult>,
    /// Per-assertion results.
    pub assertions: Vec<AssertionResult>,
    /// Artifact map: logical name → absolute path string.
    pub artifacts: BTreeMap<String, String>,
}

/// [`RunResult::score`] for a name → passed map: the fraction that held.
///
/// **An empty map scores `1.0`.** See [`RunResult::score`] for why that is the
/// contract and not each caller's decision.
///
/// The map's ordering cannot affect the result — only how many values are true
/// and how many there are — so a caller that collected its assertions in a
/// different order gets the same number. Two entries under one name are one
/// entry, which is the difference from
/// [`RunResult::score_from_assertions`]: a list keeps duplicates and weighs
/// each of them.
pub fn score_from(assertions: &BTreeMap<String, bool>) -> f64 {
    score_of(assertions.values().copied())
}

/// The map [`score_from`] scores, from `(name, passed)` pairs.
///
/// The last pair for a name wins, as inserting into the map would.
pub fn assertion_map<I, S>(pairs: I) -> BTreeMap<String, bool>
where
    I: IntoIterator<Item = (S, bool)>,
    S: Into<String>,
{
    pairs
        .into_iter()
        .map(|(name, passed)| (name.into(), passed))
        .collect()
}

/// The one scoring rule, over whatever the caller counted as an assertion.
pub(crate) fn score_of(values: impl IntoIterator<Item = bool>) -> f64 {
    let mut total = 0usize;
    let mut passed = 0usize;
    for value in values {
        total += 1;
        passed += usize::from(value);
    }
    if total == 0 || passed == total {
        1.0
    } else {
        passed as f64 / total as f64
    }
}

impl RunResult {
    /// [`RunResult::score`] from assertion results (all pass → 1.0, else fraction).
    pub fn score_from_assertions(assertions: &[AssertionResult]) -> f64 {
        score_of(assertions.iter().map(|a| a.passed))
    }

    /// Serialize to canonical JSON value (BTreeMap ensures stable key ordering).
    pub fn to_json_value(&self) -> serde_json::Value {
        serde_json::to_value(self).expect("RunResult is serializable")
    }

    /// Serialize to pretty-printed JSON string with trailing newline.
    pub fn to_json_pretty(&self) -> String {
        let mut s = serde_json::to_string_pretty(self).expect("RunResult is serializable");
        s.push('\n');
        s
    }

    /// Read a payload, refusing a version this build does not understand.
    ///
    /// The version is checked before the rest is deserialized, so an
    /// unreadable payload is reported as its version rather than as whichever
    /// field happened to have changed shape.
    pub fn from_json_value(value: &serde_json::Value) -> Result<Self, ResultReadError> {
        check_readable(declared_version(value)?)?;
        serde_json::from_value(value.clone()).map_err(|e| ResultReadError::Malformed {
            message: e.to_string(),
        })
    }

    /// [`RunResult::from_json_value`], from JSON text.
    pub fn from_json_str(text: &str) -> Result<Self, ResultReadError> {
        let value: serde_json::Value =
            serde_json::from_str(text).map_err(|e| ResultReadError::Malformed {
                message: e.to_string(),
            })?;
        Self::from_json_value(&value)
    }
}

/// The `result_version` a payload declares, if any.
///
/// A missing key and an explicit `null` both read as absent. A key holding
/// anything that is not a `u32` is malformed rather than absent: silently
/// treating `"1"` or `-1` as "no version" would put a payload onto the absent
/// rule that never asked to be there.
fn declared_version(value: &serde_json::Value) -> Result<Option<u32>, ResultReadError> {
    match value.get("result_version") {
        None | Some(serde_json::Value::Null) => Ok(None),
        Some(found) => found
            .as_u64()
            .and_then(|n| u32::try_from(n).ok())
            .map(Some)
            .ok_or_else(|| ResultReadError::Malformed {
                message: format!("`result_version` is not an unsigned integer: {found}"),
            }),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn run(result_version: Option<u32>) -> RunResult {
        RunResult {
            result_version,
            recipe_name: "login".to_string(),
            passed: true,
            exit_code: Some(0),
            duration_seconds: 0.0,
            priority: "P0".to_string(),
            execution: "scripted".to_string(),
            renderer: "default".to_string(),
            score: 1.0,
            steps: vec![],
            assertions: vec![],
            artifacts: BTreeMap::new(),
        }
    }

    fn assertion(name: &str, passed: bool) -> AssertionResult {
        AssertionResult {
            name: name.to_string(),
            passed,
            detail: String::new(),
        }
    }

    #[test]
    fn an_empty_assertion_map_scores_one_not_zero() {
        // The contract decision this function exists to make once: see the
        // `RunResult::score` docs.
        assert_eq!(score_from(&BTreeMap::new()), 1.0);
    }

    #[test]
    fn a_map_scores_the_fraction_that_held() {
        assert_eq!(score_from(&assertion_map([("a", true), ("b", true)])), 1.0);
        assert_eq!(
            score_from(&assertion_map([("a", false), ("b", false)])),
            0.0
        );
        assert_eq!(score_from(&assertion_map([("a", true), ("b", false)])), 0.5);
        assert_eq!(
            score_from(&assertion_map([("a", true), ("b", true), ("c", false)])),
            2.0 / 3.0
        );
    }

    #[test]
    fn the_order_the_pairs_arrived_in_cannot_move_the_score() {
        let forwards = assertion_map([("a", true), ("b", false), ("c", false)]);
        let backwards = assertion_map([("c", false), ("b", false), ("a", true)]);
        assert_eq!(score_from(&forwards), score_from(&backwards));
    }

    #[test]
    fn a_repeated_name_is_one_assertion_and_the_last_value_wins() {
        let map = assertion_map([("a", true), ("a", false)]);
        assert_eq!(map.len(), 1);
        assert_eq!(score_from(&map), 0.0);
    }

    #[test]
    fn the_list_and_the_map_score_the_same_assertions_alike() {
        // One rule, two shapes: the list keeps duplicates, so this is only
        // stated for distinct names.
        let cases: [&[(&str, bool)]; 4] = [
            &[],
            &[("a", true)],
            &[("a", false), ("b", false)],
            &[("a", true), ("b", false), ("c", true)],
        ];
        for case in cases {
            let list: Vec<_> = case.iter().map(|(n, p)| assertion(n, *p)).collect();
            assert_eq!(
                RunResult::score_from_assertions(&list),
                score_from(&assertion_map(case.iter().copied())),
                "{case:?}"
            );
        }
    }

    #[test]
    fn a_payload_this_build_writes_declares_its_version() {
        let json = run(Some(RESULT_SCHEMA_VERSION)).to_json_value();
        assert_eq!(json["result_version"], RESULT_SCHEMA_VERSION);
    }

    #[test]
    fn an_absent_version_is_readable_and_is_not_version_zero() {
        // The whole point of the separate rule: absent is accepted, but it is
        // not a number, so a future bump cannot sweep it out of the window.
        assert!(can_read(None));
        assert!(!can_read(Some(0)));
    }

    #[test]
    fn the_readable_window_is_current_and_one_back() {
        assert!(can_read(Some(RESULT_SCHEMA_VERSION)));
        assert!(can_read(Some(OLDEST_READABLE_RESULT_VERSION)));
        assert!(!can_read(Some(RESULT_SCHEMA_VERSION + 1)));
    }

    #[test]
    fn refusing_names_the_version_found_and_the_window_supported() {
        // An error that says only "unsupported" sends the reader to the source.
        let err = check_readable(Some(RESULT_SCHEMA_VERSION + 9)).expect_err("unreadable");
        let message = err.to_string();
        assert!(
            message.contains(&(RESULT_SCHEMA_VERSION + 9).to_string()),
            "{message}"
        );
        assert!(
            message.contains(&format!(
                "{OLDEST_READABLE_RESULT_VERSION}..={RESULT_SCHEMA_VERSION}"
            )),
            "{message}"
        );
    }

    #[test]
    fn a_foreign_payload_with_no_version_still_reads() {
        let mut json = run(None).to_json_value();
        assert!(
            json.get("result_version").is_none(),
            "absent must stay absent: {json}"
        );
        // And an unrecognised key from a foreign writer is ignored, not fatal.
        json["something_we_do_not_know"] = serde_json::json!(true);
        let back = RunResult::from_json_value(&json).expect("foreign payload reads");
        assert_eq!(back.result_version, None);
        assert_eq!(back.recipe_name, "login");
    }

    #[test]
    fn reading_a_foreign_payload_does_not_stamp_it_with_a_version() {
        // Round-tripping must not launder someone else's payload into one that
        // claims this build's schema.
        let foreign = run(None).to_json_value();
        let back = RunResult::from_json_value(&foreign).expect("reads");
        assert_eq!(back.to_json_value(), foreign);
    }

    #[test]
    fn a_payload_from_the_future_is_refused_by_version_not_by_field() {
        let mut json = run(Some(RESULT_SCHEMA_VERSION + 1)).to_json_value();
        json.as_object_mut().expect("object").remove("score");
        assert_eq!(
            RunResult::from_json_value(&json),
            Err(ResultReadError::UnsupportedVersion {
                found: RESULT_SCHEMA_VERSION + 1,
                oldest: OLDEST_READABLE_RESULT_VERSION,
                newest: RESULT_SCHEMA_VERSION,
            })
        );
    }

    #[test]
    fn a_version_that_is_not_a_number_is_malformed_not_absent() {
        let mut json = run(Some(RESULT_SCHEMA_VERSION)).to_json_value();
        json["result_version"] = serde_json::json!("1");
        assert!(matches!(
            RunResult::from_json_value(&json),
            Err(ResultReadError::Malformed { .. })
        ));
    }

    #[test]
    fn an_explicit_null_version_reads_as_absent() {
        let mut json = run(Some(RESULT_SCHEMA_VERSION)).to_json_value();
        json["result_version"] = serde_json::Value::Null;
        let back = RunResult::from_json_value(&json).expect("null reads as absent");
        assert_eq!(back.result_version, None);
    }

    #[test]
    fn a_payload_predating_the_version_field_still_deserialises() {
        // The additive guarantee, stated as a test: everything that already
        // reads a RunResult keeps working on payloads written before this
        // change.
        let text = r#"{
            "recipe_name": "login", "passed": true, "exit_code": 0,
            "duration_seconds": 1.5, "priority": "P0", "execution": "scripted",
            "renderer": "default", "score": 1.0,
            "steps": [], "assertions": [], "artifacts": {}
        }"#;
        let parsed: RunResult = serde_json::from_str(text).expect("plain serde still works");
        assert_eq!(parsed.result_version, None);
        assert_eq!(
            RunResult::from_json_str(text).expect("checked read"),
            parsed
        );
    }
}
