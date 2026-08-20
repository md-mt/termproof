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
//! The scenario also drives `record_session` down each of its outcomes, because
//! the `error` it writes onto a `Recording` is a string in the manifest and has
//! to be the *same* string on both sides — "which step failed" is only useful to
//! a reader if it does not depend on which implementation produced the run.
//!
//! Two failures are deliberately left out, both because the two implementations
//! word them differently and pinning either would make this harness certify a
//! divergence: an **append that fails**, whose message comes from
//! `append_checkpoint_frames` itself, and an **upload that declines with a
//! reason**, whose message comes from `ArtifactUploader::last_error` — which the
//! oracle's `UploaderLike` has no counterpart for. `no-url` and `blank-url`
//! therefore pin the shared fallback, not the shipped behaviour; see
//! `conformance/README.md`.
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

use termproof::evidence::cast_video::{append_checkpoint_frames, CastVideoConverter};
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

/// A second append over the same steps at an explicit, fractional hold, which
/// the default-hold cast cannot cover.
///
/// Its base ends on a seventh decimal on purpose. That is what a Rust-recorded
/// cast ends on — `CastRecorder` writes `as_secs_f64()` unrounded — and it is
/// the only input shape that tells the two languages' rounding apart:
/// `round(at, 6)` writes 0.9 and 1.3 for the second and fourth frames where the
/// rule both sides actually run writes 0.900001 and 1.300001. Over a
/// whole-decimal base the two agree everywhere, so a corpus built on one would
/// regenerate byte-for-byte with the Python transcription reverted.
const FRACTIONAL_HOLD: f64 = 0.2;
const FRACTIONAL_HOLD_CAST: &str = "session-with-fractional-hold.cast";
const FRACTIONAL_BASE_CAST: &str =
    "{\"version\":2,\"width\":80,\"height\":24}\n[0.5000005,\"o\",\"MENU\"]\n";

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

/// Returns an empty string, which is no URL.
///
/// A distinct scenario from [`RefusingUploader`] even though both produce the
/// same message: the two implementations reject the empty string in their own
/// code, so this is what stops one of them keeping it.
struct BlankUploader;

impl ArtifactUploader for BlankUploader {
    fn upload(&mut self, _path: &str) -> Option<String> {
        Some(String::new())
    }

    fn last_error(&self) -> Option<&str> {
        None
    }
}

/// Declines without saying why. Reports no `last_error` so that this half falls
/// back on the shared message, which is all the oracle's protocol can express.
struct RefusingUploader;

impl ArtifactUploader for RefusingUploader {
    fn upload(&mut self, _path: &str) -> Option<String> {
        None
    }

    fn last_error(&self) -> Option<&str> {
        None
    }
}

/// A converter whose tools write a fixed byte instead of running.
///
/// `convert` still replays the cast and renders every frame; the oracle's
/// counterpart is a hand-written stub that writes the same byte and reads
/// nothing. Neither the frame count nor the encoder reaches the manifest — the
/// video *path* and the file at it are what the two sides have to agree on.
fn stub_converter() -> CastVideoConverter {
    CastVideoConverter::with_runner(Box::new(|exe, args, _timeout| {
        let (path, bytes): (&String, &[u8]) = if exe.ends_with("ffmpeg") {
            (args.last().ok_or("stub converter: no output")?, b"mp4")
        } else {
            let at = args
                .iter()
                .position(|a| a == "--output")
                .ok_or("stub converter: no --output argument")?;
            (args.get(at + 1).ok_or("stub converter: no output")?, b"png")
        };
        std::fs::write(path, bytes).map_err(|e| e.to_string())
    }))
}

/// Fails with a message neither language contributes to.
fn broken_converter() -> CastVideoConverter {
    CastVideoConverter::with_runner(Box::new(|_, _, _| Err("encoder exploded".to_string())))
}

/// Reports success and writes nothing.
///
/// Every invocation exits cleanly and produces no file, which is what a real
/// `ffmpeg` misconfigured for its output looks like. Both implementations have
/// to refuse it, and to refuse it with the same words.
fn silent_converter() -> CastVideoConverter {
    CastVideoConverter::with_runner(Box::new(|_, _, _| Ok(())))
}

/// Writes [`BASE_CAST`], the way a real `save_cast` would.
fn save_base_cast(dest: &Path) -> Result<(), String> {
    std::fs::write(dest, BASE_CAST).map_err(|e| e.to_string())
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

    // `record_session`, once per outcome. Every publisher writes into the same
    // directory and differs only in the seam under test, so the recordings are
    // numbered consecutively and their artifacts all land in `files`.
    let mut working = EvidencePublisher::new(&directory, identity())
        .with_renderer(stub_renderer())
        .with_uploader(Box::new(StubUploader))
        .with_video_converter(stub_converter());
    // All five steps succeed: cast, appended evidence, video, URL.
    collector.record_session("recorded", &mut working, save_base_cast);
    // Step 1 fails, so nothing downstream runs.
    collector.record_session("unsaveable", &mut working, |_| {
        Err("disk on fire".to_string())
    });
    // Step 1 fails quietly, which is still step 1.
    collector.record_session("silent-save", &mut working, |_| Ok(()));
    // Step 3 has nothing to convert with.
    let mut no_converter = EvidencePublisher::new(&directory, identity())
        .with_renderer(stub_renderer())
        .with_uploader(Box::new(StubUploader));
    collector.record_session("no-converter", &mut no_converter, save_base_cast);
    // Step 3 fails, so step 4 is not attempted: no URL, and no upload error.
    let mut bad_encode = EvidencePublisher::new(&directory, identity())
        .with_renderer(stub_renderer())
        .with_uploader(Box::new(StubUploader))
        .with_video_converter(broken_converter());
    collector.record_session("bad-encode", &mut bad_encode, save_base_cast);
    // Step 3 reports success and writes nothing, which is step 3 lying — the
    // same guard as `silent-save`, one step further down.
    let mut silent_encode = EvidencePublisher::new(&directory, identity())
        .with_renderer(stub_renderer())
        .with_uploader(Box::new(StubUploader))
        .with_video_converter(silent_converter());
    collector.record_session("silent-encode", &mut silent_encode, save_base_cast);
    // Step 4 fails, which costs the URL and not the video.
    let mut no_url = EvidencePublisher::new(&directory, identity())
        .with_renderer(stub_renderer())
        .with_uploader(Box::new(RefusingUploader))
        .with_video_converter(stub_converter());
    collector.record_session("no-url", &mut no_url, save_base_cast);
    // Step 4 returning an empty string, which is no URL.
    let mut blank_url = EvidencePublisher::new(&directory, identity())
        .with_renderer(stub_renderer())
        .with_uploader(Box::new(BlankUploader))
        .with_video_converter(stub_converter());
    collector.record_session("blank-url", &mut blank_url, save_base_cast);
    // An empty label, the one input on which the two filename schemes could
    // part: this half builds the stem through `sanitize_component`, which
    // substitutes "default" for a component that sanitises to nothing, and the
    // oracle's `_sanitize` does not. That half applies the same fallback, and
    // this is what holds it there.
    collector.record_session("", &mut working, save_base_cast);

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
