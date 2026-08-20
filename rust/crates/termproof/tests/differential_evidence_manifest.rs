//! Port half of the evidence-manifest differential harness.
//!
//! Builds the scenario `conformance/probe_evidence_manifest.py` builds, in the
//! same order, publishes it, and compares both the resulting `evidence.json`
//! and the contents of every file the publish wrote against what the oracle
//! recorded in `conformance/corpus/evidence_manifest.expected.json`.
//!
//! # Why this exists
//!
//! The two implementations claim to produce one document format, and until
//! this test the claim was checked by a Python unit test that spelled the Rust
//! field names out from having read the Rust structs. That catches a rename on
//! the Python side. It cannot catch a rename on the Rust side, a field added to
//! one and not the other, or a value the two spell differently — and it was
//! never run against a Rust manifest at all.
//!
//! Comparing whole documents catches all of those, and it fails on the side
//! that changed rather than in whatever reads both.
//!
//! The file contents are compared as well as the manifest, because the manifest
//! is a set of paths and agreeing on paths is not agreeing on files. The first
//! run of this harness found exactly that: byte-identical manifests pointing at
//! step text that differed by a trailing newline.
//!
//! The same reasoning covers the cast written into the publish directory: a
//! manifest agreeing about a recording's path is not agreeing about the
//! recording, and once `append_checkpoint_frames` puts the evidence sequence on
//! the end of one, the cast is the artifact a reviewer actually watches.
//!
//! # Determinism
//!
//! Two things about the scenario are properties of the machine rather than of
//! either implementation, and both halves neutralise them the same way:
//!
//! - The rasteriser. `ScreenshotRenderer` shells out to `rsvg-convert`, so on a
//!   host without it every step would record a render error whose text is the
//!   operating system's. Both halves stub the tool and write a fixed byte.
//! - The publish directory, which is a fresh temporary directory. Both halves
//!   substitute it for `@DIR` before comparing.

// The collector is the `evidence` module, so there is no manifest to compare
// without it. The oracle has no equivalent switch — Python builds one package —
// so this is a feature gate on the port half only.
#![cfg(feature = "evidence")]

use std::path::Path;

use termproof::evidence::cast_video::append_checkpoint_frames;
use termproof::evidence::collector::{
    CaptureKind, EvidenceCollector, EvidencePublisher, Recording, RunIdentity,
};
use termproof::evidence::screenshot::ScreenshotRenderer;
use termproof::evidence::uploader::ArtifactUploader;
use termproof::terminal::inmemory::InMemorySession;

/// Stands in for the publish directory. Matches the oracle's placeholder.
const DIRECTORY_PLACEHOLDER: &str = "@DIR";

/// A recorded session for the checkpoint frames to be appended to. Written out
/// by hand rather than by a recorder: a real header carries a wall-clock
/// timestamp and the host's `SHELL` and `TERM`, none of which either
/// implementation controls.
///
/// It opens by setting a scroll region, because that is what a full-screen TUI
/// leaves behind and it is the state an append has to undo: without the
/// `\x1b[r` in the repaint prefix, a checkpoint taller than the region scrolls
/// rows out of the frame. The corpus records the prefix bytes, so both
/// implementations are held to resetting it.
const BASE_CAST: &str = "{\"version\":2,\"width\":80,\"height\":24}\n\
     [0.5,\"o\",\"\\u001b[3;20rMENU\"]\n\
     [1.25,\"o\",\"\\r\\nitem one\"]\n";

/// Filename for that cast inside the publish directory.
const CHECKPOINT_CAST: &str = "session-with-checkpoints.cast";

/// A second append over the same steps at an explicit, fractional hold. The
/// default-hold cast above lands on whole and quarter seconds, which any
/// rounding rule reproduces; 0.1 + 0.2 does not, and this is what holds the two
/// implementations to the same six-decimal answer. It also covers the explicit
/// `hold_seconds` path, which the default cast cannot.
const FRACTIONAL_HOLD: f64 = 0.2;
const FRACTIONAL_HOLD_CAST: &str = "session-with-fractional-hold.cast";
const FRACTIONAL_BASE_CAST: &str =
    "{\"version\":2,\"width\":80,\"height\":24}\n[0.1,\"o\",\"MENU\"]\n";

/// The document the oracle recorded. Loaded at runtime, as the other
/// differential tests load their corpora.
fn expected_path() -> std::path::PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../../conformance/corpus/evidence_manifest.expected.json")
}

/// The identity both halves publish under.
fn identity() -> RunIdentity {
    RunIdentity::new("login", "default", "20240101-000000-000000-login-default-1")
}

/// Returns a deterministic URL derived from the filename.
struct StubUploader;

impl ArtifactUploader for StubUploader {
    fn upload(&mut self, path: &str) -> Option<String> {
        let name = Path::new(path).file_name()?.to_string_lossy().to_string();
        Some(format!("https://example.invalid/{name}"))
    }

    fn last_error(&self) -> Option<&str> {
        None
    }
}

/// A session serving `screen` and `raw`, the Rust equivalent of the oracle's
/// `static_source`.
fn source(screen: &str, raw: &str) -> InMemorySession {
    let mut session = InMemorySession::new(vec![], "/tmp/x.cast".into(), 80, 24);
    session.set_screen(screen);
    session.set_raw(raw);
    session
}

/// A renderer that writes a fixed byte instead of shelling out.
fn stub_renderer() -> ScreenshotRenderer {
    ScreenshotRenderer::with_runner(Box::new(|_tool, args, _timeout| {
        // `--output <png> <svg>`: the path to write is the argument after
        // `--output`, which is how the real rasteriser is invoked.
        let png = args
            .iter()
            .position(|a| a == "--output")
            .and_then(|i| args.get(i + 1))
            .ok_or_else(|| "stub renderer: no --output argument".to_string())?;
        std::fs::write(png, b"png").map_err(|e| e.to_string())
    }))
}

/// Replace the publish directory with [`DIRECTORY_PLACEHOLDER`] everywhere it
/// appears, and sort object keys so the two halves are comparable as text.
fn normalize(value: &serde_json::Value, directory: &str) -> serde_json::Value {
    match value {
        serde_json::Value::Object(map) => serde_json::Value::Object(
            map.iter()
                .map(|(k, v)| (k.clone(), normalize(v, directory)))
                .collect(),
        ),
        serde_json::Value::Array(items) => {
            serde_json::Value::Array(items.iter().map(|v| normalize(v, directory)).collect())
        }
        serde_json::Value::String(s) => {
            serde_json::Value::String(s.replace(directory, DIRECTORY_PLACEHOLDER))
        }
        other => other.clone(),
    }
}

#[test]
fn the_published_manifest_matches_the_python_document() {
    let tmp = tempfile::tempdir().expect("tempdir");
    let directory = tmp.path().join("evidence");

    let mut collector = EvidenceCollector::new();

    // A plain checkpoint read from a source.
    collector.capture("menu-open", &mut source("MENU\nitem one", ""));
    // The same screen again: dedup, so `same_as` points back at step 0 and no
    // second image is written.
    collector.capture("menu-open-again", &mut source("MENU\nitem one", ""));
    // A screen the caller already held, with no source to read it from.
    collector.capture_text("from-log", "RECOVERED", CaptureKind::Checkpoint);
    // A text capture marked as a failure still carries no raw output: there is
    // no source to ask for one.
    collector.capture_text("post-mortem", "LAST SCREEN", CaptureKind::Failure);
    // A failure read from a source does carry the log.
    collector.capture_failure("boom", &mut source("ERROR", "log bytes"));
    // Two screens whose text differs only by SGR escapes. Both sides build the
    // grid for a text capture from plain lines rather than by parsing ANSI, so
    // whether these dedupe together is a statement about that choice — and one
    // the two implementations have to make the same way, since the dedup
    // verdict reaches the manifest.
    collector.capture_text("styled", "\x1b[31mALERT\x1b[0m", CaptureKind::Checkpoint);
    collector.capture_text("unstyled", "ALERT", CaptureKind::Checkpoint);

    collector.attach_recording(
        Recording::new("full-session", "/tmp/session.cast").with_video(
            "/tmp/session.mp4",
            Some("https://example.invalid/session.mp4".to_string()),
        ),
    );
    collector.attach_recording(
        Recording::new("failed-encode", "/tmp/broken.cast").with_error("video conversion failed"),
    );

    let mut publisher = EvidencePublisher::new(&directory, identity())
        .with_renderer(stub_renderer())
        .with_uploader(Box::new(StubUploader));
    let manifest = collector.publish(&mut publisher).expect("published");

    let written = std::fs::read_to_string(manifest.path()).expect("manifest readable");
    let document: serde_json::Value = serde_json::from_str(&written).expect("manifest is JSON");

    // The evidence sequence written onto the end of a recording. Every captured
    // screen above goes in, including the SGR-escaped one and the two-line one,
    // so the appended payloads exercise both JSON escaping and the carriage
    // returns a raw terminal needs.
    let cast = directory.join(CHECKPOINT_CAST);
    std::fs::write(&cast, BASE_CAST).expect("base cast written");
    append_checkpoint_frames(&cast.to_string_lossy(), collector.steps(), None)
        .expect("checkpoint frames appended");

    let fractional = directory.join(FRACTIONAL_HOLD_CAST);
    std::fs::write(&fractional, FRACTIONAL_BASE_CAST).expect("fractional base cast written");
    append_checkpoint_frames(
        &fractional.to_string_lossy(),
        collector.steps(),
        Some(FRACTIONAL_HOLD),
    )
    .expect("checkpoint frames appended at a fractional hold");

    // `evidence.json` is excluded: it is `document`, and recording it twice
    // would let the two copies disagree.
    let mut files = serde_json::Map::new();
    let mut entries: Vec<_> = std::fs::read_dir(&directory)
        .expect("publish directory readable")
        .map(|e| e.expect("entry readable").path())
        .collect();
    entries.sort();
    for path in entries {
        let name = path.file_name().unwrap().to_string_lossy().to_string();
        if !path.is_file() || name == "evidence.json" {
            continue;
        }
        let content = std::fs::read_to_string(&path).expect("artifact readable");
        files.insert(name, serde_json::Value::String(content));
    }

    let actual = normalize(
        &serde_json::json!({ "manifest": document, "files": files }),
        &directory.to_string_lossy(),
    );
    let recorded = std::fs::read_to_string(expected_path()).expect("oracle document readable");
    let expected: serde_json::Value =
        serde_json::from_str(&recorded).expect("recorded oracle document is JSON");

    assert_eq!(
        serde_json::to_string_pretty(&expected).unwrap(),
        serde_json::to_string_pretty(&actual).unwrap(),
        "the Rust manifest diverged from the recorded Python document; \
         regenerate the oracle only if the Python side is the one that changed \
         — see conformance/README.md"
    );
}
