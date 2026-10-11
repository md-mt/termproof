//! Port half of the build-info differential harness.
//!
//! Builds the scenario `conformance/probe_build_info.py` builds and compares
//! the serialised provenance documents — key order normalised — against what
//! the oracle recorded in `conformance/corpus/build_info.expected.json`.
//!
//! # What is, and is not, exercised
//!
//! The Python half records its real serialiser, `BuildInfo.to_dict`. This
//! crate has **no serialiser for [`BuildInfo`]** — no `Serialize`, no
//! `to_dict` equivalent — so [`document`] below is a test-side transcription:
//! one JSON key per struct field, under the field's own name, `None` as
//! `null`. What is pinned is therefore the struct's field names and types
//! and `verify_provenance`, not a production JSON writer. The scenario uses
//! exhaustive struct literals, so a field added to the Rust struct breaks
//! compilation here, and a key added to the Python document fails the whole
//! comparison; neither can drift silently. Neither half calls its
//! constructors (`from_installed`, `from_source_build`, `from_command`, …):
//! those probe `<binary> --version`, ask git for a commit and read the clock,
//! so version probing, git discovery and the timestamp *spelling*
//! (`"%Y-%m-%d %H:%M:%S"` here, ISO `T`-separated in Python) are known
//! differences this harness does not pin — see `conformance/README.md`.
//!
//! `verify_provenance` stats the binary path, so both halves point the
//! scenario at a real temporary file and record it as `@BIN`.
//!
//! # Allowed differences (#209)
//!
//! The documents are compared whole apart from the named allowances below,
//! each asserted so it fails when the divergence it records stops existing.
//! Anything else differing — a key added, removed or renamed on either side,
//! a value's JSON type — fails the comparison.
//!
//! ```sh
//! cargo test -p termproof --test differential_build_info -- --nocapture
//! ```

use std::path::{Path, PathBuf};

use termproof::build_info::{BuildInfo, MODE_INSTALLED, MODE_PACKAGE, MODE_SOURCE};

/// The fixed timestamp both halves hand-set. The constructors would spell
/// the clock differently on each side; that difference is not pinned here.
const TIMESTAMP: &str = "2026-01-02T03:04:05";

/// Fields carrying the same value under different names, as
/// `(rust, python)` (#209): `change_id` is Python's `source_ref`,
/// `commit_hash` its `git_commit`, and `build_timestamp` its `timestamp`
/// (an `Option` here, a plain string there — the scenario always sets it).
const RENAMED_KEYS: [(&str, &str); 3] = [
    ("change_id", "source_ref"),
    ("commit_hash", "git_commit"),
    ("build_timestamp", "timestamp"),
];

/// The Python document's `command` per scenario entry (#209). The Rust
/// struct has no command field at all, so the key is asserted against this
/// transcription before it is set aside.
const PYTHON_COMMANDS: [&[&str]; 6] = [
    &["@BIN", "--serve"],
    &["@BIN"],
    &["@BIN"],
    &["@BIN"],
    &["@BIN"],
    &[],
];

/// Scenario entries whose provenance verdict diverges, as
/// `(entry, python, rust)` (#209). Entries 2 and 3 put an empty string where
/// a revision or target belongs: Python's `bool("")` treats it as absent,
/// this side's `is_some()` treats `Some("")` as present. Entry 4 is
/// [`MODE_PACKAGE`], which verifies here and is an unknown mode — never
/// verified — in Python. Every other entry's recorded
/// `provenance_verified` must equal [`BuildInfo::verify_provenance`].
const PROVENANCE_DIVERGENCES: [(usize, bool, bool); 3] =
    [(2, false, true), (3, false, true), (4, false, true)];

/// Scenario entries with no binary (#209): Python records `null`
/// (`binary_path: str | None`), this side spells absence `""`
/// (`binary_path: String`).
const EMPTY_BINARY_PATH: [usize; 1] = [5];

fn expected_path() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../../conformance/corpus/build_info.expected.json")
}

/// The fixed scenario. Keep in step with probe_build_info.py.
fn scenario(binary: &str) -> Vec<BuildInfo> {
    // 0: installed, real binary — verified on both sides.
    // 1: source with target and both revision spellings — verified.
    // 2: source whose revision fields are empty strings, not None.
    // 3: source whose build target is an empty string, not None.
    // 4: the Rust-only "package" mode.
    // 5: no binary at all — binary_path spells absence "".
    vec![
        BuildInfo {
            mode: MODE_INSTALLED.to_string(),
            binary_path: binary.to_string(),
            version: "tool 1.2.3".to_string(),
            change_id: None,
            commit_hash: Some("abc123".to_string()),
            build_target: None,
            build_timestamp: Some(TIMESTAMP.to_string()),
        },
        BuildInfo {
            mode: MODE_SOURCE.to_string(),
            binary_path: binary.to_string(),
            version: "tool 1.2.3".to_string(),
            change_id: Some("PR-42".to_string()),
            commit_hash: Some("abc123".to_string()),
            build_target: Some("//app:cli".to_string()),
            build_timestamp: Some(TIMESTAMP.to_string()),
        },
        BuildInfo {
            mode: MODE_SOURCE.to_string(),
            binary_path: binary.to_string(),
            version: "tool 1.2.3".to_string(),
            change_id: Some(String::new()),
            commit_hash: Some(String::new()),
            build_target: Some("//app:cli".to_string()),
            build_timestamp: Some(TIMESTAMP.to_string()),
        },
        BuildInfo {
            mode: MODE_SOURCE.to_string(),
            binary_path: binary.to_string(),
            version: "tool 1.2.3".to_string(),
            change_id: Some("PR-42".to_string()),
            commit_hash: None,
            build_target: Some(String::new()),
            build_timestamp: Some(TIMESTAMP.to_string()),
        },
        BuildInfo {
            mode: MODE_PACKAGE.to_string(),
            binary_path: binary.to_string(),
            version: "tool 1.2.3".to_string(),
            change_id: None,
            commit_hash: None,
            build_target: None,
            build_timestamp: Some(TIMESTAMP.to_string()),
        },
        BuildInfo {
            mode: MODE_INSTALLED.to_string(),
            binary_path: String::new(),
            version: "unknown".to_string(),
            change_id: None,
            commit_hash: None,
            build_target: None,
            build_timestamp: Some(TIMESTAMP.to_string()),
        },
    ]
}

/// The struct as a JSON document, one key per field under the field's own
/// name. A transcription in the test — the crate serialises `BuildInfo`
/// nowhere — with the temporary binary spelled `@BIN` as recorded.
fn document(info: &BuildInfo, binary: &str) -> serde_json::Value {
    let binary_path = if info.binary_path == binary {
        "@BIN"
    } else {
        info.binary_path.as_str()
    };
    serde_json::json!({
        "mode": info.mode,
        "binary_path": binary_path,
        "version": info.version,
        "change_id": info.change_id,
        "commit_hash": info.commit_hash,
        "build_target": info.build_target,
        "build_timestamp": info.build_timestamp,
    })
}

#[test]
fn the_serialised_build_info_matches_the_python_document() {
    let tmp = tempfile::tempdir().expect("tempdir");
    let binary_path = tmp.path().join("built");
    std::fs::write(&binary_path, b"x").expect("write the binary the scenario names");
    let binary = binary_path.to_str().expect("temp path is UTF-8");

    let recorded = std::fs::read_to_string(expected_path()).expect("oracle document readable");
    let expected: serde_json::Value =
        serde_json::from_str(&recorded).expect("recorded oracle document is JSON");
    let mut expected: Vec<serde_json::Value> = expected
        .as_array()
        .expect("the recording is an array")
        .clone();

    let infos = scenario(binary);
    let mut actual: Vec<serde_json::Value> =
        infos.iter().map(|info| document(info, binary)).collect();
    assert_eq!(actual.len(), expected.len(), "scenario size drifted");

    let mut empty_binary_path = Vec::new();
    for (index, ((info, rust), python)) in
        infos.iter().zip(&mut actual).zip(&mut expected).enumerate()
    {
        let python = python
            .as_object_mut()
            .expect("a Python record is an object");
        let rust = rust.as_object_mut().expect("a Rust record is an object");

        // `provenance_verified` is a key only the Python serialiser writes;
        // here it is the `verify_provenance` method. Asserted per entry
        // rather than compared, so a listed divergence must keep diverging
        // exactly as pinned and an unlisted one must not start (#209).
        let python_provenance = python
            .remove("provenance_verified")
            .and_then(|value| value.as_bool())
            .expect("the Python document carries `provenance_verified`");
        match PROVENANCE_DIVERGENCES
            .iter()
            .find(|(entry, _, _)| *entry == index)
        {
            Some((_, pinned_python, pinned_rust)) => assert_eq!(
                (python_provenance, info.verify_provenance()),
                (*pinned_python, *pinned_rust),
                "entry {index}'s provenance divergence changed; remove or \
                 update its PROVENANCE_DIVERGENCES allowance in this test"
            ),
            None => assert_eq!(
                python_provenance,
                info.verify_provenance(),
                "entry {index}'s provenance verdict diverged beyond the \
                 pinned allowances (#209)"
            ),
        }

        // `command` exists only on the Python side (#209).
        assert!(
            !rust.contains_key("command"),
            "the Rust document now carries `command`; remove the allowance \
             in this test"
        );
        assert_eq!(
            python.remove("command"),
            Some(serde_json::json!(PYTHON_COMMANDS[index])),
            "entry {index}'s Python `command` moved; update the allowance \
             in this test only if the Python side is the one that changed"
        );

        // Renamed fields (#209): both directions, so renaming either side
        // to match fails here instead of silently retiring the allowance.
        for (rust_key, python_key) in RENAMED_KEYS {
            assert!(
                !python.contains_key(rust_key),
                "the Python document now carries `{rust_key}`; remove the \
                 rename allowance in this test"
            );
            assert!(
                python.contains_key(python_key),
                "the Python document no longer carries `{python_key}`"
            );
            let value = rust
                .remove(rust_key)
                .unwrap_or_else(|| panic!("the Rust document carries `{rust_key}`"));
            rust.insert(python_key.to_string(), value);
        }

        // An absent binary is `null` there and `""` here (#209).
        if rust.get("binary_path") == Some(&serde_json::json!("")) {
            assert_eq!(
                python.get("binary_path"),
                Some(&serde_json::Value::Null),
                "entry {index}: an empty Rust `binary_path` must pair with \
                 a null Python one"
            );
            rust.insert("binary_path".to_string(), serde_json::Value::Null);
            empty_binary_path.push(index);
        }
    }
    assert_eq!(
        empty_binary_path, EMPTY_BINARY_PATH,
        "the entries spelling an absent binary changed; update the \
         EMPTY_BINARY_PATH allowance in this test"
    );

    assert_eq!(
        serde_json::to_string_pretty(&serde_json::Value::Array(expected)).unwrap(),
        serde_json::to_string_pretty(&serde_json::Value::Array(actual)).unwrap(),
        "the Rust build-info document diverged from the recorded Python \
         one beyond the allowed differences; regenerate the oracle only \
         if the Python side is the one that changed — see \
         conformance/README.md"
    );
}
