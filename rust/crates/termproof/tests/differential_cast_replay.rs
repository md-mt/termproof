//! Port half of the cast-replay differential harness.
//!
//! Replays `conformance/corpus/cast_replay_cases.json` through
//! `CastVideoConverter::frames_from_cast` — a one-event cast of each case's
//! `columns` x `rows` whose output is the case's `output` — and compares the
//! final frame, as each row's cells' `text` and `width` plus the cursor,
//! against what the oracle recorded in
//! `conformance/corpus/cast_replay.expected.json`.
//!
//! # Why this exists
//!
//! No other harness reaches a terminal emulator's grid. The step corpus drives
//! a real child but compares a verdict and a detail string; the
//! evidence-manifest scenario replays a cast here and then throws the frames
//! away. So the two emulators behind cast playback — `avt` here, `pyte` in the
//! oracle — were compared by nothing, and a wide glyph overwritten on its
//! second column came back as three different screens from `pyte`, `avt` 0.16
//! and `avt` 0.18 with every gate green (#209, found reviewing #220).
//!
//! Only `text`, `width` and the cursor are compared. Colour and the SGR
//! attributes are a different question with known answers of their own — the
//! oracle's emulator has no dim — and comparing them here would make every case
//! about that.
//!
//! ```sh
//! cargo test -p termproof --test differential_cast_replay -- --nocapture
//! ```

// Cast playback is the `evidence` module, so there is nothing to replay
// without it. The oracle has no equivalent switch — Python builds one package —
// so this is a feature gate on the port half only.
//
// `frames_from_cast` is `pub` only under `_test-harness`, which is deliberately
// *not* named here. The crate's self dev-dependency turns it on for every test
// build, so losing that is a compile error in this file rather than a harness
// that quietly compiles to nothing and reports green.
#![cfg(feature = "evidence")]

use std::path::{Path, PathBuf};

use termproof::evidence::cast_video::CastVideoConverter;

/// A case the two emulators are known to disagree on, and the one frame the
/// port is accepted to produce for it.
struct Residual {
    name: &'static str,
    /// Each row's cells as `(text, width)`.
    rows: &'static [&'static [(&'static str, u64)]],
    /// `(row, column, hidden)`.
    cursor: (u64, u64, bool),
}

impl Residual {
    /// The pinned frame in the shape `replay` produces.
    fn frame(&self) -> serde_json::Value {
        let (row, column, hidden) = self.cursor;
        serde_json::json!({
            "name": self.name,
            "rows": self.rows.iter().map(|row| {
                row.iter()
                    .map(|(text, width)| serde_json::json!({"text": text, "width": width}))
                    .collect::<Vec<_>>()
            }).collect::<Vec<_>>(),
            "cursor": {"row": row, "column": column, "hidden": hidden},
        })
    }
}

/// Cases the two emulators are known to disagree on. Exact rather than a
/// floor, twice over. By name: a listed case that starts agreeing fails the
/// test just as an unlisted one that stops does, so the list cannot outlive the
/// divergence it records. And by frame: a listed case has to replay to exactly
/// the screen pinned here, because "differs from the oracle" is true of every
/// wrong screen at once — `avt` 0.16's answer to this case differs from
/// `pyte`'s too, and a name alone would have accepted it.
///
/// The frames live here and not in `conformance/corpus/`: an `*.expected.json`
/// there is the oracle's testimony, and this is the port's. Each entry is
/// explained under "Known residual" in `conformance/README.md`.
const KNOWN_RESIDUAL: &[Residual] = &[Residual {
    name: "wide-glyph-overwritten-on-its-second-column",
    rows: &[
        &[("A", 1), (" ", 1), ("界", 2), ("", 0)],
        &[(" ", 1), (" ", 1), (" ", 1), (" ", 1)],
    ],
    cursor: (0, 4, false),
}];

fn corpus_dir() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("../../../conformance/corpus")
}

fn replay(case: &serde_json::Value, directory: &Path) -> serde_json::Value {
    let cast = directory.join("case.cast");
    let header =
        serde_json::json!({"version": 2, "width": case["columns"], "height": case["rows"]});
    let event = serde_json::json!([0.0, "o", case["output"]]);
    std::fs::write(&cast, format!("{header}\n{event}\n")).expect("cast written");
    // The last frame is the final screen on both sides; how many frames lead up
    // to it is frame timing, which is not what this layer compares.
    let frames = CastVideoConverter::new()
        .frames_from_cast(&cast.to_string_lossy())
        .expect("cast replays");
    let last = frames.last().expect("a replay has a final frame");
    serde_json::json!({
        "name": case["name"],
        "rows": last.rows.iter().map(|row| {
            row.iter()
                .map(|cell| serde_json::json!({"text": cell.text, "width": cell.width}))
                .collect::<Vec<_>>()
        }).collect::<Vec<_>>(),
        "cursor": {
            "row": last.cursor_row,
            "column": last.cursor_column,
            "hidden": last.cursor_hidden,
        },
    })
}

/// One recorded frame as a line per row plus the cursor, for the report.
fn describe(frame: &serde_json::Value) -> String {
    let rows: Vec<String> = frame["rows"]
        .as_array()
        .expect("rows is an array")
        .iter()
        .map(|row| {
            row.as_array()
                .expect("a row is an array")
                .iter()
                .map(|cell| {
                    format!(
                        "[{:?} w{}]",
                        cell["text"].as_str().unwrap_or("?"),
                        cell["width"]
                    )
                })
                .collect()
        })
        .collect();
    format!("{} cursor {}", rows.join(" / "), frame["cursor"])
}

#[test]
fn differential_cast_replay_against_python() {
    let corpus = corpus_dir();
    let cases: serde_json::Value = serde_json::from_str(
        &std::fs::read_to_string(corpus.join("cast_replay_cases.json")).expect("cases readable"),
    )
    .expect("cases are JSON");
    let document: serde_json::Value = serde_json::from_str(
        &std::fs::read_to_string(corpus.join("cast_replay.expected.json"))
            .expect("oracle recording readable"),
    )
    .expect("oracle recording is JSON");
    let cases = cases.as_array().expect("the corpus is an array of cases");
    let expected = document["cases"].as_array().expect("recorded cases array");
    assert_eq!(
        cases.len(),
        expected.len(),
        "the recording is not of this corpus"
    );

    let tmp = tempfile::tempdir().expect("tempdir");
    let mut diverged: Vec<&str> = Vec::new();
    let mut unpinned: Vec<&str> = Vec::new();
    println!("\n=== differential harness: cast replay ===");
    println!("oracle environment: {}", document["environment"]);
    for (case, want) in cases.iter().zip(expected) {
        let name = case["name"].as_str().expect("a case has a name");
        let got = replay(case, tmp.path());
        if got != *want {
            diverged.push(name);
            println!(
                "  {name}:\n    python: {}\n    rust:   {}",
                describe(want),
                describe(&got)
            );
            let pinned = KNOWN_RESIDUAL.iter().find(|residual| residual.name == name);
            if let Some(pinned) = pinned.map(Residual::frame).filter(|pinned| *pinned != got) {
                unpinned.push(name);
                println!("    pinned: {}", describe(&pinned));
            }
        }
    }
    let total = cases.len();
    println!(
        "\nfull agreement (rows + cursor): {}/{total}",
        total - diverged.len()
    );
    println!(
        "known residual:                 {}/{total}",
        KNOWN_RESIDUAL.len()
    );

    let known: Vec<&str> = KNOWN_RESIDUAL
        .iter()
        .map(|residual| residual.name)
        .collect();
    assert_eq!(
        diverged, known,
        "the cases the two emulators disagree on are not the recorded ones; a \
         new name is a new divergence, and a missing one has been closed and \
         comes off the list — see conformance/README.md"
    );
    assert!(
        unpinned.is_empty(),
        "{unpinned:?} still disagree with the oracle, but not with the screen \
         pinned in KNOWN_RESIDUAL; the port's output for a known residual has \
         changed, which is a new divergence and not the recorded one — see \
         conformance/README.md"
    );
}
