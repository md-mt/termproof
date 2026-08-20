//! Collecting evidence as a run proceeds.
//!
//! The rest of [`evidence`](crate::evidence) can render a screen, dedupe it,
//! upload it and write a report. None of it decides *when* a screen is worth
//! keeping, so every consumer invented its own step model and the artifact
//! layout came out different each time. This module is that missing middle:
//! an ordered, labelled list of captures, and one pass that turns the list
//! into files on disk.
//!
//! ```no_run
//! use termproof::evidence::collector::{EvidenceCollector, EvidencePublisher, RunIdentity};
//! # use termproof::terminal::{InMemorySession, Session};
//! # use termproof::result::RunResult;
//! # let mut session = InMemorySession::new(vec![], "/tmp/x.cast".into(), 80, 24);
//! # fn finished_run() -> RunResult { unimplemented!() }
//! let mut evidence = EvidenceCollector::new();
//!
//! evidence.capture("menu-open", &mut session);
//! session.press("down").ok();
//! evidence.capture("moved-down", &mut session);
//!
//! let run_dir = std::path::Path::new("/tmp/run-1");
//! let identity = RunIdentity::from_run_dir(run_dir, "login", "default");
//! let mut publisher = EvidencePublisher::new(run_dir.join("evidence"), identity);
//! let manifest = evidence.publish(&mut publisher).expect("published");
//!
//! let mut result = finished_run();
//! manifest.attach_to(&mut result).expect("same run");
//! ```
//!
//! # Capture is eager, publish is deferred
//!
//! [`capture`](EvidenceCollector::capture) copies the screen *now*; nothing is
//! rendered, written or uploaded until [`publish`](EvidenceCollector::publish).
//! That split is what makes the rest work. Rendering at capture time would
//! stall the run behind a rasteriser, and — more importantly — it would leave
//! [`Deduper`] nothing to plug into, because by publish time the session has
//! moved on and the earlier grids are gone. The collector keeps the
//! [`AttributedScreen`], not the PNG, precisely so the comparison is still
//! possible later.
//!
//! # One capture is one instant
//!
//! [`ScreenSource`] has a single method for a reason: reading the text and the
//! grid through two calls lets a running program advance between them, and the
//! artifacts then disagree about which instant they describe. See
//! [`ScreenSource::capture_screen`].
//!
//! # Steps sit *beside* [`RunResult`], not inside it
//!
//! Publishing writes an `evidence.json` manifest;
//! [`attach_to`](EvidenceManifest::attach_to) puts one artifact entry on the
//! result and refuses a manifest that belongs to a different run. `RunResult`
//! is unchanged: its schema, its serialization and every existing reader are
//! exactly as they were, and `RunResult::steps` keeps meaning what it has
//! always meant — the per-step *verdict*, not the per-step evidence. The two
//! models are related but not the same shape: a recipe commonly captures
//! either side of one step, and a failure capture has no step of its own.
//!
//! # Screen text is always written
//!
//! A PNG shows a human what happened. It does not show what an assertion
//! matched against, and a failed assertion whose run wrote `step-00.png` but
//! no `step-00.txt` is undiagnosable afterwards. So every captured step gets
//! its text file, including the ones whose image was deduped away: the image
//! is the expensive artifact and the one worth sharing, the text is the one
//! worth grepping.
//!
//! Raw output is kept only for [`capture_failure`](EvidenceCollector::capture_failure).
//! A session's raw output is the whole log so far rather than the delta, so a
//! copy per checkpoint is quadratic in the length of the run and every copy
//! but the last is a prefix of a later one.
//!
//! # A whole-session recording is five steps, and four of them can fail
//!
//! [`record_session`](EvidenceCollector::record_session) is the wiring between
//! the pieces above: it saves the live session's cast through a caller-supplied
//! closure, appends the captured checkpoints to it with
//! [`append_checkpoint_frames`], converts it to a video, uploads the video, and
//! records the outcome on a [`Recording`]. Every consumer that needed a video
//! of the whole run wrote that sequence itself, and what they got wrong was
//! never the happy path — it was which step is allowed to fail, and what the
//! run is told when one does. See
//! [`record_session`](EvidenceCollector::record_session) for the rule.

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};

use crate::evidence::cast_video::{append_checkpoint_frames, CastVideoConverter};
use crate::evidence::dedup::Deduper;
use crate::evidence::screenshot::ScreenshotRenderer;
use crate::evidence::uploader::ArtifactUploader;
use crate::result::RunResult;
use crate::store::{atomic_write_text, sanitize_component};
use crate::terminal::attributed::{
    attributed_screen_from_text, AttributedScreen, DEFAULT_COLUMNS, DEFAULT_ROWS,
};
use crate::terminal::session::Session;

/// Schema version of the published manifest.
pub const EVIDENCE_MANIFEST_VERSION: u32 = 1;

/// Manifest filename written into the publish directory.
pub const MANIFEST_FILE: &str = "evidence.json";

/// Longest label fragment allowed in a generated filename.
const MAX_LABEL_IN_FILENAME: usize = 40;

/// Names of the four fallible steps of
/// [`record_session`](EvidenceCollector::record_session), as they appear at the
/// front of a [`Recording::error`].
///
/// Spelled once each, and asserted literally in the tests, because "which step
/// failed" is the whole point of the field: a report that says only that
/// something went wrong sends a reader back to the machine that produced it.
/// The Python implementation writes the same four strings.
const STEP_SAVE_CAST: &str = "save cast";
const STEP_APPEND_FRAMES: &str = "append checkpoint frames";
const STEP_CONVERT: &str = "convert";
const STEP_UPLOAD: &str = "upload";

/// Step 3's failure when the publisher was never given a converter.
const NO_VIDEO_CONVERTER: &str = "no video converter configured";

/// Step 4's failure when the uploader declined without saying why.
const NO_URL: &str = "uploader returned no URL";

/// Whether a capture should carry the raw output log with it.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RawOutput {
    /// Include it — the caller is recording a failure.
    Keep,
    /// Leave it out. The log is cumulative, so a copy per checkpoint is
    /// quadratic and every copy but the last is a prefix of a later one.
    Skip,
}

/// One self-consistent reading of a screen.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ScreenCapture {
    /// Screen text at the captured instant.
    pub screen: String,
    /// The grid at the same instant, when the source has attributes to report.
    pub attributed: Option<AttributedScreen>,
    /// The raw output log, when [`RawOutput::Keep`] was asked for.
    pub raw_output: Option<String>,
}

/// Something a collector can read a screen from.
///
/// # Why this is not just [`Session`]
///
/// [`Session`] is a *control* interface: sixteen methods, `Send`, owning a
/// live child process, a cast path and an exit code. Demanding one in order to
/// keep a screenshot would mean the only thing evidence can ever be collected
/// from is a running program — not a replayed cast, not a golden screen in a
/// test, not a grid reconstructed from a log. None of those can answer
/// `close()` or `cast_path()` honestly.
///
/// A second trait that merely *duplicates* `Session` would be the worse
/// outcome, so this one is not parallel to it — it is a view of it. The
/// blanket impl below means every `Session`, present or future, is a
/// `ScreenSource` for free: no backend implements anything twice, and the two
/// cannot drift apart because there is no way to have one without the other.
pub trait ScreenSource {
    /// Read the screen once, as of one instant.
    ///
    /// # Why this is one method and not three
    ///
    /// Text, grid and raw log have to describe the same moment, and against a
    /// live program they will not if they are fetched separately. This is not
    /// hypothetical for the backends in this crate:
    ///
    /// - the pty path serves [`Session::screen`] from a snapshot taken at the
    ///   last sync point, while [`Session::screen_attributed`] reads the live
    ///   screen mutex a reader thread is still feeding;
    /// - the tmux path re-runs `capture-pane` *inside*
    ///   [`Session::screen_attributed`] and replaces its cached screen and raw
    ///   buffers as a side effect — which, after a close or a dead session,
    ///   can replace real text with an empty capture.
    ///
    /// Fetched one at a time, the result is a manifest that validates
    /// perfectly and lies: `step-NN.txt` describing the screen before an
    /// action while `step-NN.png` and the deduplication verdict describe the
    /// screen after it. Reading once removes the window rather than narrowing
    /// it, so an implementor cannot reintroduce the bug by being careless
    /// about call order.
    fn capture_screen(&mut self, raw: RawOutput) -> ScreenCapture;
}

impl<T: Session + ?Sized> ScreenSource for T {
    fn capture_screen(&mut self, raw: RawOutput) -> ScreenCapture {
        // Order is the whole point of doing this in one call.
        //
        // `screen_attributed` is the live read on every backend that has one,
        // and on the tmux path it is also the refresh: it replaces the cached
        // screen and raw buffers before returning. Taking it first means the
        // text and log read afterwards describe the state it just established
        // rather than the one before it.
        let attributed = Session::screen_attributed(self);
        let screen = match &attributed {
            // One grid, one text. Deriving the text from the same cells the
            // PNG and the dedup fingerprint come from is what closes the
            // window on the pty path, where `Session::screen` is a snapshot
            // and the grid is live. `grid_text` applies the same
            // normalisation `Session::screen` does, so the file still reads as
            // the thing an assertion matched against.
            Some(grid) => grid_text(grid),
            None => Session::screen(self).to_string(),
        };
        let raw_output = match raw {
            RawOutput::Keep => Some(Session::raw_output(self).to_string()),
            RawOutput::Skip => None,
        };
        ScreenCapture {
            screen,
            attributed,
            raw_output,
        }
    }
}

/// Grid text, normalised the way a session normalises its own screen text:
/// trailing whitespace off each row, then trailing blank rows dropped.
fn grid_text(screen: &AttributedScreen) -> String {
    let mut lines = screen.text_lines(true);
    while lines.last().is_some_and(|line| line.is_empty()) {
        lines.pop();
    }
    lines.join("\n")
}

/// Why a step was captured.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum CaptureKind {
    /// An ordinary point of interest during the run.
    Checkpoint,
    /// The screen at the moment something failed.
    Failure,
}

impl CaptureKind {
    fn raw_output(self) -> RawOutput {
        match self {
            CaptureKind::Failure => RawOutput::Keep,
            CaptureKind::Checkpoint => RawOutput::Skip,
        }
    }
}

/// One captured screen, in capture order.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CapturedStep {
    /// Position in capture order, zero-based. Filenames use the same number.
    pub index: usize,
    /// Caller-supplied label.
    pub label: String,
    /// Why it was captured.
    pub kind: CaptureKind,
    /// Screen text at capture time.
    pub screen: String,
    /// The grid at capture time, synthesised from the text when the source had
    /// no attributed screen of its own.
    pub attributed: AttributedScreen,
    /// Raw output log, kept for [`CaptureKind::Failure`] only.
    pub raw_output: Option<String>,
}

impl CapturedStep {
    /// Filename stem shared by this step's artifacts.
    pub fn file_stem(&self) -> String {
        let label: String = self.label.chars().take(MAX_LABEL_IN_FILENAME).collect();
        format!("step-{:02}-{}", self.index, sanitize_component(&label))
    }
}

/// A recording of a whole session, as against one screen out of it.
///
/// Captures are instants; this is the span between them. Keeping the two apart
/// is deliberate — a recording has no grid, cannot be deduplicated against its
/// neighbours and does not belong in capture order — but they are published
/// together because a reader wants the video and the stills side by side.
///
/// `error` is one field rather than separate conversion and upload errors:
/// they are mutually exclusive, since a conversion that failed leaves nothing
/// to upload.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Recording {
    /// Caller-supplied label.
    pub label: String,
    /// Path to the terminal recording itself, normally an asciinema cast.
    pub cast: String,
    /// Path to the encoded video, when one was produced.
    pub video: Option<String>,
    /// Shareable URL for `video`, when an uploader was configured and worked.
    pub url: Option<String>,
    /// Why there is no video, or no URL for one.
    pub error: Option<String>,
}

impl Recording {
    /// A recording of `cast` with nothing derived from it yet.
    pub fn new(label: impl Into<String>, cast: impl Into<String>) -> Self {
        Recording {
            label: label.into(),
            cast: cast.into(),
            video: None,
            url: None,
            error: None,
        }
    }

    /// The same recording, carrying the video that was encoded from it.
    pub fn with_video(mut self, video: impl Into<String>, url: Option<String>) -> Self {
        self.video = Some(video.into());
        self.url = url;
        self
    }

    /// The same recording, carrying why it produced no video or no URL.
    pub fn with_error(mut self, error: impl Into<String>) -> Self {
        self.error = Some(error.into());
        self
    }
}

/// An ordered, labelled record of what the screen looked like during a run.
#[derive(Debug, Clone)]
pub struct EvidenceCollector {
    steps: Vec<CapturedStep>,
    recordings: Vec<Recording>,
    columns: usize,
    rows: usize,
}

impl Default for EvidenceCollector {
    fn default() -> Self {
        EvidenceCollector {
            steps: Vec::new(),
            recordings: Vec::new(),
            columns: DEFAULT_COLUMNS,
            rows: DEFAULT_ROWS,
        }
    }
}

impl EvidenceCollector {
    /// A collector with the default grid.
    pub fn new() -> Self {
        Self::default()
    }

    /// A collector whose text-only fallback grid is `columns` × `rows`.
    ///
    /// Only used for sources that report no attributed screen; a grid that
    /// exists carries its own dimensions.
    pub fn with_grid(columns: usize, rows: usize) -> Self {
        EvidenceCollector {
            columns,
            rows,
            ..Self::default()
        }
    }

    /// Capture the screen as an ordinary checkpoint.
    pub fn capture<S: ScreenSource + ?Sized>(&mut self, label: &str, source: &mut S) {
        self.record(label, CaptureKind::Checkpoint, source);
    }

    /// Capture the screen as a failure, keeping the raw output log with it.
    pub fn capture_failure<S: ScreenSource + ?Sized>(&mut self, label: &str, source: &mut S) {
        self.record(label, CaptureKind::Failure, source);
    }

    /// Record a screen the caller already holds, with no source to read from.
    ///
    /// [`capture`](Self::capture) and [`capture_failure`](Self::capture_failure)
    /// pull from a [`ScreenSource`], which presumes there is something live to
    /// pull from. Not every screen worth keeping arrives that way: text
    /// recovered from a log, the screen a step returned before the session
    /// moved on, a golden file in a test. Without this, recording one of those
    /// means writing a throwaway `ScreenSource` whose only job is to hand back a
    /// string it was constructed with.
    ///
    /// No raw output log is attached, even for [`CaptureKind::Failure`]: there
    /// is no source to ask for one. A caller holding the log can write it out
    /// alongside.
    pub fn capture_text(&mut self, label: &str, screen: &str, kind: CaptureKind) {
        let attributed = attributed_screen_from_text(screen, self.columns, self.rows);
        self.steps.push(CapturedStep {
            index: self.steps.len(),
            label: label.to_string(),
            kind,
            screen: screen.to_string(),
            attributed,
            raw_output: None,
        });
    }

    fn record<S: ScreenSource + ?Sized>(&mut self, label: &str, kind: CaptureKind, source: &mut S) {
        let capture = source.capture_screen(kind.raw_output());
        let attributed = capture.attributed.unwrap_or_else(|| {
            attributed_screen_from_text(&capture.screen, self.columns, self.rows)
        });
        self.steps.push(CapturedStep {
            index: self.steps.len(),
            label: label.to_string(),
            kind,
            screen: capture.screen,
            attributed,
            raw_output: capture.raw_output,
        });
    }

    /// Attach a whole-session recording.
    ///
    /// The collector does not produce recordings — encoding a cast is a
    /// tool-shelling job with its own failure modes, and which tool is the
    /// caller's business. It carries them so that
    /// [`publish`](Self::publish) can put the stills and the video in one
    /// manifest, which is how a reader wants to find them.
    pub fn attach_recording(&mut self, recording: Recording) {
        self.recordings.push(recording);
    }

    /// Save the session's cast, derive a video from it, upload it, and record
    /// the outcome.
    ///
    /// The five steps, in order:
    ///
    /// 1. write the live session's cast, by calling `save_cast` with the path
    ///    to write to — the collector picks the path so the cast lands beside
    ///    the stills it belongs with;
    /// 2. append the captured checkpoints to that cast as held trailing frames,
    ///    through [`append_checkpoint_frames`];
    /// 3. convert the cast to a video, through the publisher's
    ///    [`video_converter`](EvidencePublisher::video_converter);
    /// 4. upload the video, through the publisher's
    ///    [`uploader`](EvidencePublisher::uploader);
    /// 5. attach a [`Recording`] describing what came of all that, which
    ///    [`publish`](Self::publish) then writes into the manifest.
    ///
    /// `&mut self` because it appends that recording; [`publish`](Self::publish)
    /// stays `&self`.
    ///
    /// # No failure fails the run
    ///
    /// There is no `Result` here on purpose. A recording is evidence *about* a
    /// run, not part of its verdict, so a missing video degrades the report and
    /// nothing else. Every failure instead lands on the `Recording`, prefixed
    /// with the name of the step that produced it — `save cast`,
    /// `append checkpoint frames`, `convert` or `upload` — and reaches the
    /// report from there. Two failures in one call are joined with `"; "`, so
    /// neither is lost to the other.
    ///
    /// Step 5 is the only one that cannot fail: it appends to a `Vec`.
    ///
    /// # Which later steps run after a failure
    ///
    /// **A step runs only when the step before it produced the thing it works
    /// on.** That is the whole rule, and it decides every case:
    ///
    /// | step that failed | what still runs | why |
    /// |---|---|---|
    /// | 1, save cast | nothing | there is no cast to append to, convert or upload |
    /// | 2, append frames | 3 and 4 | the cast is still on disk and still convertible; it just ends on the session instead of on the evidence |
    /// | 3, convert | nothing after it | there is no video to upload |
    /// | 4, upload | — | it is last; `video` is still recorded, only `url` is missing |
    ///
    /// The case worth naming is the one a hand-written version gets wrong:
    /// **an upload is never attempted after a failed conversion.** Uploading
    /// the path a conversion did not produce is how a run ends up reporting a
    /// store error for a video that was never encoded.
    ///
    /// A publisher with no uploader is not a failure — it is a publisher that
    /// was not asked to upload, exactly as in [`publish`](Self::publish). A
    /// publisher with no *converter* is a failure, because converting is what
    /// this method was called to do.
    ///
    /// # `save_cast`
    ///
    /// Returns `Ok(())` having written a cast to the path it was handed, or
    /// `Err` describing why it could not. A closure that reports success and
    /// writes nothing is treated as step 1 failing, rather than left for step 2
    /// to discover as a missing file: the step that lied is the one worth
    /// naming.
    ///
    /// ```no_run
    /// # use termproof::evidence::collector::{EvidenceCollector, EvidencePublisher, RunIdentity};
    /// # use termproof::evidence::cast_video::CastVideoConverter;
    /// # let mut evidence = EvidenceCollector::new();
    /// # let identity = RunIdentity::new("login", "default", "run-1");
    /// # let live_cast = std::path::PathBuf::from("/tmp/session.cast");
    /// let mut publisher = EvidencePublisher::new("/tmp/run-1/evidence", identity)
    ///     .with_video_converter(CastVideoConverter::new());
    ///
    /// evidence.record_session("full-session", &mut publisher, |dest| {
    ///     std::fs::copy(&live_cast, dest).map(|_| ()).map_err(|e| e.to_string())
    /// });
    /// let manifest = evidence.publish(&mut publisher).expect("published");
    /// ```
    pub fn record_session<F>(
        &mut self,
        label: &str,
        publisher: &mut EvidencePublisher,
        save_cast: F,
    ) where
        F: FnOnce(&Path) -> Result<(), String>,
    {
        let stem = recording_file_stem(self.recordings.len(), label);
        let cast_path = publisher.dir.join(format!("{stem}.cast"));
        let mut recording = Recording::new(label, path_string(&cast_path));
        let mut errors: Vec<String> = Vec::new();

        // 1. Write the cast. The directory is created here rather than left to
        //    the closure: the collector chose the path, so the collector owes
        //    it somewhere to be written.
        let saved = std::fs::create_dir_all(&publisher.dir)
            .map_err(|e| e.to_string())
            .and_then(|()| save_cast(&cast_path))
            .and_then(|()| {
                if cast_path.is_file() {
                    Ok(())
                } else {
                    Err(format!(
                        "reported success but wrote no file at {}",
                        path_string(&cast_path)
                    ))
                }
            });
        if let Err(message) = saved {
            recording.error = Some(format!("{STEP_SAVE_CAST}: {message}"));
            self.recordings.push(recording);
            return;
        }

        // 2. Put the evidence sequence on the end of it. Non-fatal: the cast is
        //    on disk either way, and a recording that stops on the session is
        //    worth more than no recording at all.
        let cast_string = path_string(&cast_path);
        if let Err(message) = append_checkpoint_frames(&cast_string, &self.steps, None) {
            errors.push(format!("{STEP_APPEND_FRAMES}: {message}"));
        }

        // 3. Encode it.
        let video_path = path_string(&publisher.dir.join(format!("{stem}.mp4")));
        let converted = match &publisher.video_converter {
            Some(converter) => converter.convert(&cast_string, Some(&video_path)),
            None => Err(NO_VIDEO_CONVERTER.to_string()),
        };
        match converted {
            Ok(video) => {
                recording.video = Some(video.clone());
                // 4. Share it. Only reachable with a video in hand.
                if let Some(uploader) = publisher.uploader.as_mut() {
                    match uploader.upload(&video) {
                        Some(url) => recording.url = Some(url),
                        None => {
                            let detail = uploader
                                .last_error()
                                .filter(|e| !e.is_empty())
                                .unwrap_or(NO_URL);
                            errors.push(format!("{STEP_UPLOAD}: {detail}"));
                        }
                    }
                }
            }
            Err(message) => errors.push(format!("{STEP_CONVERT}: {message}")),
        }

        // 5. Record what happened, including which step it happened in.
        if !errors.is_empty() {
            recording.error = Some(errors.join("; "));
        }
        self.recordings.push(recording);
    }

    /// The attached recordings, in the order they were attached.
    pub fn recordings(&self) -> &[Recording] {
        &self.recordings
    }

    /// The captured steps, in capture order.
    pub fn steps(&self) -> &[CapturedStep] {
        &self.steps
    }

    /// How many steps have been captured.
    pub fn len(&self) -> usize {
        self.steps.len()
    }

    /// Whether nothing has been captured.
    pub fn is_empty(&self) -> bool {
        self.steps.is_empty()
    }

    /// Render, dedupe, upload and write the manifest.
    ///
    /// Takes `&self`: publishing reads the captures, so a collector can be
    /// published to more than one destination, and a caller that publishes
    /// mid-run keeps everything captured so far.
    ///
    /// Returns `Err` only when the *manifest itself* could not be written. A
    /// screenshot that fails to render is recorded on the step as an `error`
    /// and does not fail the run: the text is already on disk, which is the
    /// part an assertion is diagnosed from.
    pub fn publish(&self, publisher: &mut EvidencePublisher) -> Result<EvidenceManifest, String> {
        let mut deduper = Deduper::default();
        // The image the deduper's answer refers to. `Deduper::check` reports a
        // label, and labels are caller-supplied and may repeat; tracking the
        // step alongside is exact, because the deduper only ever looks back one
        // rendered step and this is it.
        let mut last_rendered: Option<(ReusedFrom, String, Option<String>)> = None;
        let mut published = Vec::with_capacity(self.steps.len());

        for step in &self.steps {
            let stem = step.file_stem();
            let text_path = publisher.dir.join(format!("{stem}.txt"));
            atomic_write_text(&text_path, &step.screen).map_err(|e| e.to_string())?;

            let raw_output = match &step.raw_output {
                Some(raw) => {
                    let raw_path = publisher.dir.join(format!("{stem}-raw.txt"));
                    atomic_write_text(&raw_path, raw).map_err(|e| e.to_string())?;
                    Some(path_string(&raw_path))
                }
                None => None,
            };

            let mut entry = PublishedStep {
                index: step.index,
                label: step.label.clone(),
                kind: step.kind,
                screen_text: path_string(&text_path),
                raw_output,
                screenshot: None,
                url: None,
                same_as: None,
                error: None,
            };

            match deduper.check(&step.label, &step.attributed) {
                Some(_) => {
                    if let Some((source, png, url)) = &last_rendered {
                        entry.same_as = Some(source.clone());
                        entry.screenshot = Some(png.clone());
                        entry.url = url.clone();
                    }
                }
                None => {
                    let png = path_string(&publisher.dir.join(format!("{stem}.png")));
                    match publisher
                        .renderer
                        .render(&step.screen, &png, Some(&step.attributed))
                    {
                        Ok(path) => {
                            let url = publisher.uploader.as_mut().and_then(|u| u.upload(&path));
                            entry.screenshot = Some(path.clone());
                            entry.url = url.clone();
                            last_rendered = Some((
                                ReusedFrom {
                                    index: step.index,
                                    label: step.label.clone(),
                                },
                                path,
                                url,
                            ));
                        }
                        Err(message) => {
                            // `Deduper::forget`'s contract. Without it the next
                            // identical screen is told to reuse an image that
                            // was never produced.
                            deduper.forget();
                            last_rendered = None;
                            entry.error = Some(message);
                        }
                    }
                }
            }

            published.push(entry);
        }

        let manifest = EvidenceManifest {
            manifest_version: EVIDENCE_MANIFEST_VERSION,
            run: publisher.identity.clone(),
            steps: published,
            recordings: self.recordings.clone(),
            path: publisher.manifest_path(),
        };
        atomic_write_text(&manifest.path, &manifest.to_json_pretty()).map_err(|e| e.to_string())?;
        Ok(manifest)
    }
}

/// Filename stem shared by a recording's cast and video.
///
/// Numbered like [`CapturedStep::file_stem`] and for the same reason: labels are
/// caller-supplied and may repeat, and two recordings called `full-session`
/// must not overwrite each other's cast.
fn recording_file_stem(index: usize, label: &str) -> String {
    let label: String = label.chars().take(MAX_LABEL_IN_FILENAME).collect();
    format!("recording-{:02}-{}", index, sanitize_component(&label))
}

/// Which run a manifest belongs to.
///
/// Evidence sits beside [`RunResult`] rather than inside it, so nothing about
/// the file layout stops a caller pointing run A's result at run B's evidence.
/// This is what lets a reader — and [`EvidenceManifest::attach_to`] — notice.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct RunIdentity {
    /// Recipe this evidence came from; matches [`RunResult::recipe_name`].
    pub recipe_name: String,
    /// Renderer this evidence came from; matches [`RunResult::renderer`].
    pub renderer: String,
    /// Identifier for this run in particular.
    ///
    /// Recipe and renderer separate two different runs; they do not separate
    /// two runs of the *same* recipe. [`RunResult`] has no field to check this
    /// against, so it is recorded rather than verified: a reader holding a run
    /// directory can compare it, and two manifests can be told apart.
    pub run_id: String,
}

impl RunIdentity {
    /// Identity from its three parts.
    pub fn new(
        recipe_name: impl Into<String>,
        renderer: impl Into<String>,
        run_id: impl Into<String>,
    ) -> Self {
        RunIdentity {
            recipe_name: recipe_name.into(),
            renderer: renderer.into(),
            run_id: run_id.into(),
        }
    }

    /// Identity for the run that produced `run_dir`, taking the directory's
    /// own name as the run id.
    ///
    /// [`new_run_dir`](crate::store::new_run_dir) already builds a name unique
    /// per timestamp, pid and process entropy, so it is the run identifier the
    /// crate has rather than a second one invented here.
    pub fn from_run_dir(run_dir: &Path, recipe_name: &str, renderer: &str) -> Self {
        let run_id = run_dir
            .file_name()
            .map(|name| name.to_string_lossy().to_string())
            .unwrap_or_default();
        RunIdentity::new(recipe_name, renderer, run_id)
    }

    /// Whether `result` is the run this identity describes.
    ///
    /// Compares what the two documents share. See [`run_id`](Self::run_id) for
    /// what this cannot rule out.
    pub fn matches(&self, result: &RunResult) -> bool {
        self.recipe_name == result.recipe_name && self.renderer == result.renderer
    }
}

/// Where published evidence goes and how it gets there.
pub struct EvidencePublisher {
    /// Directory the artifacts are written into.
    pub dir: PathBuf,
    /// Which run this evidence belongs to. Required rather than optional: a
    /// manifest that cannot say whose it is cannot be checked by anyone.
    pub identity: RunIdentity,
    /// Renders a captured grid to a PNG.
    pub renderer: ScreenshotRenderer,
    /// Optional upload seam. Uploads are best-effort: a failure leaves the
    /// step's `url` empty rather than failing the publish.
    pub uploader: Option<Box<dyn ArtifactUploader>>,
    /// Optional cast-to-video seam, used by
    /// [`EvidenceCollector::record_session`] and by nothing else —
    /// [`publish`](EvidenceCollector::publish) renders stills and does not
    /// encode.
    ///
    /// Optional rather than defaulted because a converter is two more binaries
    /// on the host (`rsvg-convert` and `ffmpeg`), and a publisher that is only
    /// ever going to write stills should not imply them. A `record_session`
    /// against a publisher without one records that as the `convert` step
    /// failing.
    pub video_converter: Option<CastVideoConverter>,
}

impl std::fmt::Debug for EvidencePublisher {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("EvidencePublisher")
            .field("dir", &self.dir)
            .field("identity", &self.identity)
            .field("uploader", &self.uploader.is_some())
            .field("video_converter", &self.video_converter.is_some())
            .finish()
    }
}

impl EvidencePublisher {
    /// Publish `identity`'s evidence into `dir` with the default renderer and
    /// no uploader.
    pub fn new(dir: impl Into<PathBuf>, identity: RunIdentity) -> Self {
        EvidencePublisher {
            dir: dir.into(),
            identity,
            renderer: ScreenshotRenderer::new(),
            uploader: None,
            video_converter: None,
        }
    }

    /// Use `renderer` instead of the default.
    pub fn with_renderer(mut self, renderer: ScreenshotRenderer) -> Self {
        self.renderer = renderer;
        self
    }

    /// Upload every rendered screenshot through `uploader`.
    pub fn with_uploader(mut self, uploader: Box<dyn ArtifactUploader>) -> Self {
        self.uploader = Some(uploader);
        self
    }

    /// Encode session recordings through `converter`.
    ///
    /// Needed by [`EvidenceCollector::record_session`]; nothing else consults
    /// it.
    pub fn with_video_converter(mut self, converter: CastVideoConverter) -> Self {
        self.video_converter = Some(converter);
        self
    }

    /// Where the manifest is written.
    pub fn manifest_path(&self) -> PathBuf {
        self.dir.join(MANIFEST_FILE)
    }
}

/// The step whose screenshot another step reuses.
///
/// Both halves, because either alone is not enough: labels are caller-supplied
/// and may repeat, so `"check"` does not say *which* `check`; the index alone
/// says which but makes the manifest unreadable without cross-referencing.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ReusedFrom {
    /// Capture-order index of the step that owns the image.
    pub index: usize,
    /// That step's label.
    pub label: String,
}

/// One step as it came out of [`EvidenceCollector::publish`].
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct PublishedStep {
    /// Position in capture order, zero-based.
    pub index: usize,
    /// Caller-supplied label.
    pub label: String,
    /// Why it was captured.
    pub kind: CaptureKind,
    /// Path to the screen text. Always present.
    pub screen_text: String,
    /// Path to the raw output log, for failure captures.
    pub raw_output: Option<String>,
    /// Path to the PNG — this step's own, or the reused one when `same_as` is
    /// set. Absent when the render failed; see `error`.
    pub screenshot: Option<String>,
    /// Shareable URL for `screenshot`, when an uploader was configured and
    /// succeeded.
    pub url: Option<String>,
    /// The earlier step whose image this one reuses, when its screen was
    /// identical to the one immediately before it.
    pub same_as: Option<ReusedFrom>,
    /// Why this step has no screenshot.
    pub error: Option<String>,
}

/// What a publish produced.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct EvidenceManifest {
    /// Schema version of this document, present from its first release.
    pub manifest_version: u32,
    /// Which run this evidence belongs to.
    pub run: RunIdentity,
    /// Published steps, in capture order.
    pub steps: Vec<PublishedStep>,
    /// Whole-session recordings, in the order they were attached.
    ///
    /// Omitted from the JSON entirely when there are none, so a run that
    /// records nothing writes the same document it wrote before this field
    /// existed. That is what lets it be added without a
    /// [`EVIDENCE_MANIFEST_VERSION`] bump, and what keeps the Python
    /// implementation reading manifests it does not yet write.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub recordings: Vec<Recording>,
    /// Where the manifest was written. Not serialized: a file does not need to
    /// record its own location, and baking it in would make the document
    /// wrong the moment the directory moved.
    #[serde(skip)]
    path: PathBuf,
}

impl EvidenceManifest {
    /// Where this manifest lives on disk.
    pub fn path(&self) -> &Path {
        &self.path
    }

    /// Point `result` at this manifest, refusing a mismatched pair.
    ///
    /// This is the supported way to join the two documents. Evidence sits
    /// beside [`RunResult`], so the pairing is the one thing the layout cannot
    /// enforce on its own — an unchecked `artifacts` insert would let run A's
    /// evidence hang off run B's result with both files still schema-valid.
    ///
    /// Returns `Err` describing the mismatch, and leaves `result` untouched.
    pub fn attach_to(&self, result: &mut RunResult) -> Result<(), String> {
        if !self.run.matches(result) {
            return Err(format!(
                "evidence for {}/{} cannot be attached to a result for {}/{}",
                self.run.recipe_name, self.run.renderer, result.recipe_name, result.renderer,
            ));
        }
        result.artifacts.extend(self.artifacts());
        Ok(())
    }

    /// Entries pointing at this manifest, unchecked.
    ///
    /// Prefer [`attach_to`](Self::attach_to), which will not pair a manifest
    /// with a result from another run. This is for callers building an index
    /// that is not a [`RunResult`].
    ///
    /// One entry, not one per step: the manifest is the index, and a caller
    /// that wants the per-step paths reads it rather than having them
    /// duplicated into a flat map that has no way to express order.
    pub fn artifacts(&self) -> BTreeMap<String, String> {
        BTreeMap::from([("evidence_manifest".to_string(), path_string(&self.path))])
    }

    /// Steps whose screen was identical to the one before, so no image of
    /// their own was rendered.
    pub fn deduped(&self) -> impl Iterator<Item = &PublishedStep> {
        self.steps.iter().filter(|s| s.same_as.is_some())
    }

    /// Serialize to pretty-printed JSON with a trailing newline.
    pub fn to_json_pretty(&self) -> String {
        let mut s = serde_json::to_string_pretty(self).expect("EvidenceManifest is serializable");
        s.push('\n');
        s
    }
}

fn path_string(path: &Path) -> String {
    path.to_string_lossy().to_string()
}

#[cfg(test)]
mod tests {
    use std::sync::{Arc, Mutex};

    use super::*;
    use crate::terminal::attributed::attributed_screen_from_ansi_text;
    use crate::terminal::inmemory::InMemorySession;
    use crate::terminal::screen::TerminalScreen;

    /// A source that is not a `Session` — the case the trait exists for.
    struct Replay {
        frames: Vec<String>,
        at: usize,
    }

    impl ScreenSource for Replay {
        fn capture_screen(&mut self, raw: RawOutput) -> ScreenCapture {
            let screen = self.frames[self.at].clone();
            self.at += 1;
            ScreenCapture {
                screen,
                attributed: None,
                raw_output: match raw {
                    RawOutput::Keep => Some(self.frames[..self.at].join("")),
                    RawOutput::Skip => None,
                },
            }
        }
    }

    /// A session whose grid and snapshot text disagree, the way a live pty's
    /// do: `screen()` serves the last sync point, the grid is now.
    struct DriftingSession {
        snapshot: InMemorySession,
        live: &'static str,
    }

    impl DriftingSession {
        fn new(stale: &str, live: &'static str) -> Self {
            let mut snapshot = InMemorySession::new(vec![], PathBuf::from("/tmp/x.cast"), 80, 24);
            snapshot.set_screen(stale);
            DriftingSession { snapshot, live }
        }
    }

    impl Session for DriftingSession {
        fn send_text(&mut self, t: &str) -> Result<(), crate::terminal::error::SessionError> {
            self.snapshot.send_text(t)
        }
        fn send_line(&mut self, t: &str) -> Result<(), crate::terminal::error::SessionError> {
            self.snapshot.send_line(t)
        }
        fn press(&mut self, k: &str) -> Result<(), crate::terminal::error::SessionError> {
            self.snapshot.press(k)
        }
        fn wait_for_text(
            &mut self,
            t: &str,
            d: std::time::Duration,
        ) -> Result<bool, crate::terminal::error::SessionError> {
            self.snapshot.wait_for_text(t, d)
        }
        fn wait_for_idle(
            &mut self,
            s: std::time::Duration,
            t: std::time::Duration,
        ) -> Result<bool, crate::terminal::error::SessionError> {
            self.snapshot.wait_for_idle(s, t)
        }
        fn wait_for_exit(
            &mut self,
            t: std::time::Duration,
        ) -> Result<Option<i32>, crate::terminal::error::SessionError> {
            self.snapshot.wait_for_exit(t)
        }
        fn read_available(
            &mut self,
            t: std::time::Duration,
        ) -> Result<(), crate::terminal::error::SessionError> {
            self.snapshot.read_available(t)
        }
        fn is_alive(&mut self) -> bool {
            self.snapshot.is_alive()
        }
        fn close(&mut self) -> Result<(), crate::terminal::error::SessionError> {
            self.snapshot.close()
        }
        fn screen(&self) -> &str {
            self.snapshot.screen()
        }
        fn screen_attributed(&mut self) -> Option<AttributedScreen> {
            Some(attributed_screen_from_text(self.live, 80, 24))
        }
        fn raw_output(&self) -> &str {
            self.snapshot.raw_output()
        }
        fn exit_code(&self) -> Option<i32> {
            self.snapshot.exit_code()
        }
        fn cols(&self) -> u16 {
            self.snapshot.cols()
        }
        fn rows(&self) -> u16 {
            self.snapshot.rows()
        }
        fn argv(&self) -> &[String] {
            self.snapshot.argv()
        }
        fn cast_path(&self) -> &Path {
            self.snapshot.cast_path()
        }
    }

    fn session(screen: &str) -> InMemorySession {
        let mut s = InMemorySession::new(vec![], PathBuf::from("/tmp/x.cast"), 80, 24);
        s.set_screen(screen);
        s
    }

    fn identity() -> RunIdentity {
        RunIdentity::new("login", "default", "20240101-000000-000000-login-default-1")
    }

    fn run_result(recipe_name: &str, renderer: &str) -> RunResult {
        RunResult {
            result_version: Some(crate::result::RESULT_SCHEMA_VERSION),
            recipe_name: recipe_name.to_string(),
            passed: true,
            exit_code: Some(0),
            duration_seconds: 1.0,
            priority: "P0".to_string(),
            execution: "scripted".to_string(),
            renderer: renderer.to_string(),
            score: 1.0,
            steps: vec![],
            assertions: vec![],
            artifacts: BTreeMap::new(),
        }
    }

    /// A publisher whose renderer touches the PNG instead of shelling out.
    fn publisher(dir: &Path) -> EvidencePublisher {
        EvidencePublisher::new(dir, identity()).with_renderer(ScreenshotRenderer::with_runner(
            Box::new(|_, args, _| std::fs::write(&args[1], b"png").map_err(|e| e.to_string())),
        ))
    }

    /// A publisher that records which PNGs were asked for.
    fn counting_publisher(dir: &Path) -> (EvidencePublisher, Arc<Mutex<Vec<String>>>) {
        let seen = Arc::new(Mutex::new(Vec::new()));
        let sink = seen.clone();
        let publisher = EvidencePublisher::new(dir, identity()).with_renderer(
            ScreenshotRenderer::with_runner(Box::new(move |_, args, _| {
                sink.lock().expect("poisoned").push(args[1].clone());
                std::fs::write(&args[1], b"png").map_err(|e| e.to_string())
            })),
        );
        (publisher, seen)
    }

    #[test]
    fn a_session_is_a_screen_source_without_implementing_anything() {
        // The whole point of the blanket impl: no backend implements a second
        // trait, and `&mut dyn Session` works too, which is what a caller
        // holding a boxed session or a driver has.
        let mut owned = session("menu");
        let mut collector = EvidenceCollector::new();
        collector.capture("owned", &mut owned);

        let mut boxed: Box<dyn Session> = Box::new(session("menu"));
        collector.capture("dyn", boxed.as_mut());

        // And through the scenario-facing layer, which is what a caller
        // driving a run actually holds.
        let mut driver = crate::terminal::driver::SessionDriver::new(Box::new(session("menu")));
        collector.capture("driver", driver.session_mut());

        assert_eq!(collector.len(), 3);
        assert!(collector.steps().iter().all(|s| s.screen == "menu"));
    }

    #[test]
    fn text_and_grid_describe_the_same_instant() {
        // The pty shape: `screen()` serves a snapshot from the last sync point
        // while the grid is read live. Fetched separately, the text file would
        // say "before" while the PNG and the dedup verdict say "after".
        let mut drifting = DriftingSession::new("before", "after");
        let mut collector = EvidenceCollector::new();
        collector.capture("mid-flight", &mut drifting);

        let step = &collector.steps()[0];
        assert_eq!(step.screen, "after");
        assert_eq!(step.attributed.to_text(true), "after");
    }

    #[test]
    fn grid_text_matches_what_a_session_reports_as_its_screen() {
        // Deriving the text from the grid is only safe if it normalises the
        // same way — otherwise the file stops reading as the thing an
        // assertion matched against, which is the reason it is written.
        let mut screen = TerminalScreen::new(80, 24);
        screen.feed_str("hello\r\n  world  \r\n");
        assert_eq!(grid_text(&screen.attributed()), screen.contents());

        let mut empty = TerminalScreen::new(80, 24);
        empty.feed_str("");
        assert_eq!(grid_text(&empty.attributed()), empty.contents());
    }

    #[test]
    fn a_non_session_source_can_be_captured() {
        let mut replay = Replay {
            frames: vec!["one".into(), "two".into()],
            at: 0,
        };
        let mut collector = EvidenceCollector::new();
        collector.capture("first", &mut replay);
        collector.capture("second", &mut replay);
        let screens: Vec<&str> = collector
            .steps()
            .iter()
            .map(|s| s.screen.as_str())
            .collect();
        assert_eq!(screens, ["one", "two"]);
    }

    #[test]
    fn text_can_be_captured_without_a_source() {
        let mut s = session("live");
        let mut collector = EvidenceCollector::new();
        collector.capture("from-session", &mut s);
        collector.capture_text("from-log", "recovered", CaptureKind::Checkpoint);
        collector.capture_text("post-mortem", "last screen", CaptureKind::Failure);

        // A text capture is a step like any other: same sequence, same
        // numbering, so filenames and the manifest do not develop a gap.
        let steps = collector.steps();
        assert_eq!(steps.len(), 3);
        assert_eq!(steps[1].index, 1);
        assert_eq!(steps[1].screen, "recovered");
        assert_eq!(steps[1].attributed.to_text(true), "recovered");
        assert_eq!(steps[2].kind, CaptureKind::Failure);
        // Nothing to ask for a log, so there is none — even for a failure.
        assert!(steps[2].raw_output.is_none());
    }

    #[test]
    fn recordings_reach_the_manifest_alongside_the_steps() {
        let dir = tempfile::tempdir().unwrap();
        let mut s = session("screen");
        let mut collector = EvidenceCollector::new();
        collector.capture("one", &mut s);
        collector.attach_recording(
            Recording::new("full-session", "/tmp/session.cast")
                .with_video("/tmp/session.mp4", Some("https://x/v".into())),
        );

        let mut publisher = EvidencePublisher::new(dir.path(), identity());
        let manifest = collector.publish(&mut publisher).unwrap();

        assert_eq!(1, manifest.steps.len());
        assert_eq!(1, manifest.recordings.len());
        assert_eq!("full-session", manifest.recordings[0].label);
        assert_eq!(Some("https://x/v".to_string()), manifest.recordings[0].url);
        assert!(manifest.to_json_pretty().contains("\"recordings\""));
    }

    #[test]
    fn a_run_with_no_recordings_writes_the_document_it_always_wrote() {
        // The field is additive precisely because it disappears when empty.
        // If this breaks, `EVIDENCE_MANIFEST_VERSION` has to move with it.
        let dir = tempfile::tempdir().unwrap();
        let mut s = session("screen");
        let mut collector = EvidenceCollector::new();
        collector.capture("one", &mut s);

        let mut publisher = EvidencePublisher::new(dir.path(), identity());
        let manifest = collector.publish(&mut publisher).unwrap();

        assert!(manifest.recordings.is_empty());
        assert!(!manifest.to_json_pretty().contains("recordings"));
    }

    #[test]
    fn a_recording_carries_why_it_produced_no_video() {
        let recording =
            Recording::new("full-session", "/tmp/s.cast").with_error("video conversion failed");
        assert!(recording.video.is_none());
        assert!(recording.url.is_none());
        assert_eq!(Some("video conversion failed".to_string()), recording.error);
    }

    #[test]
    fn a_recordings_debug_reaches_nothing_but_its_own_strings() {
        // `Recording` derives `Debug`, and a derive is a door: it renders every
        // field, so a field whose type came from a dependency would publish
        // that dependency's formatting — which is how `PyRegex` ended up
        // printing an engine-version-dependent pattern (see `pyregex`, #177).
        //
        // Deriving is safe *here* only because all five fields are `String` or
        // `Option<String>`. Pinning the exact string is what makes that a
        // checked property rather than a claim: adding a field of any other
        // type fails this test rather than silently widening the public API.
        let recording = Recording::new("full-session", "/tmp/s.cast")
            .with_video("/tmp/s.mp4", Some("https://x/v".to_string()));
        assert_eq!(
            format!("{recording:?}"),
            r#"Recording { label: "full-session", cast: "/tmp/s.cast", video: Some("/tmp/s.mp4"), url: Some("https://x/v"), error: None }"#
        );
    }

    // -- record_session ------------------------------------------------------

    /// A cast with one event, the shape `save_cast` is expected to produce.
    const A_CAST: &str = "{\"version\":2,\"width\":10,\"height\":3}\n[0.5,\"o\",\"live\"]\n";

    /// Writes `A_CAST` and reports success, the way a real `save_cast` would.
    fn save_a_cast(dest: &Path) -> Result<(), String> {
        std::fs::write(dest, A_CAST).map_err(|e| e.to_string())
    }

    /// A converter whose tools write a fixed byte instead of running.
    ///
    /// `convert` still replays the cast and renders every frame, so this
    /// exercises the real code up to the two `Command` invocations — which is
    /// as far as a test can go without `rsvg-convert` and `ffmpeg` installed.
    fn stub_converter() -> CastVideoConverter {
        CastVideoConverter::with_runner(Box::new(|exe, args, _| {
            let (path, bytes): (&String, &[u8]) = if exe.ends_with("ffmpeg") {
                (args.last().ok_or("stub: no output")?, b"mp4")
            } else {
                let at = args
                    .iter()
                    .position(|a| a == "--output")
                    .ok_or("stub: no --output")?;
                (args.get(at + 1).ok_or("stub: no output")?, b"png")
            };
            std::fs::write(path, bytes).map_err(|e| e.to_string())
        }))
    }

    /// A converter that cannot encode anything.
    fn broken_converter() -> CastVideoConverter {
        CastVideoConverter::with_runner(Box::new(|_, _, _| Err("encoder exploded".to_string())))
    }

    /// An uploader that counts what it was asked to upload.
    struct CountingUploader(Arc<Mutex<Vec<String>>>);

    impl ArtifactUploader for CountingUploader {
        fn upload(&mut self, path: &str) -> Option<String> {
            self.0.lock().expect("poisoned").push(path.to_string());
            Some("https://example/video".to_string())
        }
        fn last_error(&self) -> Option<&str> {
            None
        }
    }

    fn one_capture() -> EvidenceCollector {
        let mut collector = EvidenceCollector::new();
        collector.capture("only", &mut session("screen text"));
        collector
    }

    #[test]
    fn record_session_runs_the_five_steps_in_order() {
        let dir = tempfile::tempdir().expect("tempdir");
        let uploaded = Arc::new(Mutex::new(Vec::new()));
        let mut publisher = publisher(dir.path())
            .with_video_converter(stub_converter())
            .with_uploader(Box::new(CountingUploader(uploaded.clone())));

        let mut collector = one_capture();
        collector.record_session("full-session", &mut publisher, save_a_cast);

        let recording = &collector.recordings()[0];
        assert_eq!(recording.label, "full-session");
        assert_eq!(recording.error, None);

        // 1. The cast is where the collector said it would be.
        let cast = Path::new(&recording.cast);
        assert!(cast.exists(), "{:?}", recording.cast);
        assert_eq!(
            cast.file_name().map(|n| n.to_string_lossy().to_string()),
            Some("recording-00-full-session.cast".to_string())
        );

        // 2. With the captured screen appended to it, which is the whole reason
        //    step 2 exists — the session's own last frame is not the evidence.
        let contents = std::fs::read_to_string(cast).expect("cast readable");
        assert!(contents.starts_with(A_CAST), "the session's cast is intact");
        assert!(contents.contains("screen text"), "{contents}");

        // 3 and 4.
        let video = recording.video.as_deref().expect("video");
        assert!(video.ends_with("recording-00-full-session.mp4"), "{video}");
        assert_eq!(std::fs::read_to_string(video).expect("video"), "mp4");
        assert_eq!(recording.url.as_deref(), Some("https://example/video"));
        assert_eq!(*uploaded.lock().expect("poisoned"), vec![video.to_string()]);

        // 5. And all of it reaches the manifest, which is what a report reads.
        let manifest = collector.publish(&mut publisher).expect("published");
        assert_eq!(manifest.recordings, collector.recordings());
    }

    #[test]
    fn a_cast_that_cannot_be_saved_stops_the_sequence() {
        // Nothing downstream has anything to work on, so nothing downstream
        // runs — and the recording says which step it was.
        let dir = tempfile::tempdir().expect("tempdir");
        let uploaded = Arc::new(Mutex::new(Vec::new()));
        let mut publisher = publisher(dir.path())
            .with_video_converter(stub_converter())
            .with_uploader(Box::new(CountingUploader(uploaded.clone())));

        let mut collector = one_capture();
        collector.record_session("full-session", &mut publisher, |_| {
            Err("disk on fire".to_string())
        });

        let recording = &collector.recordings()[0];
        assert_eq!(
            recording.error.as_deref(),
            Some("save cast: disk on fire"),
            "the failure has to name the step"
        );
        assert_eq!(recording.video, None);
        assert_eq!(recording.url, None);
        assert!(
            uploaded.lock().expect("poisoned").is_empty(),
            "nothing to upload, so nothing was uploaded"
        );
        assert!(!Path::new(&recording.cast).exists());
    }

    #[test]
    fn a_save_that_writes_nothing_is_the_save_step_failing() {
        // A closure that reports success and writes no file is step 1 going
        // wrong, not step 2 finding a missing file: blaming the append would
        // send a reader to the wrong code.
        let dir = tempfile::tempdir().expect("tempdir");
        let mut publisher = publisher(dir.path()).with_video_converter(stub_converter());

        let mut collector = one_capture();
        collector.record_session("full-session", &mut publisher, |_| Ok(()));

        let error = collector.recordings()[0].error.clone().expect("error");
        assert!(error.starts_with("save cast: "), "{error}");
        assert!(error.contains("wrote no file"), "{error}");
        assert_eq!(collector.recordings()[0].video, None);
    }

    #[test]
    fn an_append_failure_does_not_stop_the_conversion() {
        // Step 2 is the one non-fatal step: the cast is on disk either way, and
        // a recording that ends on the session is worth more than none.
        //
        // The only append failure reachable through `record_session` is a cast
        // that cannot be read or is empty — the hold is not caller-supplied
        // here — and `CastVideoConverter` cannot read one of those either. So
        // what this pins is that step 3 was *attempted* after step 2 failed and
        // both failures survived; were the sequence to stop at step 2, only the
        // first of these two would be recorded.
        let dir = tempfile::tempdir().expect("tempdir");
        let mut publisher = publisher(dir.path()).with_video_converter(stub_converter());

        let mut collector = one_capture();
        collector.record_session("empty", &mut publisher, |dest| {
            std::fs::write(dest, "").map_err(|e| e.to_string())
        });

        let error = collector.recordings()[0].error.clone().expect("error");
        assert_eq!(
            error,
            "append checkpoint frames: empty cast file; convert: empty cast file"
        );
    }

    #[test]
    fn a_publisher_with_no_video_converter_says_so() {
        // Not silence: `record_session` was called to produce a video, so a
        // publisher that cannot is a failure of the convert step.
        let dir = tempfile::tempdir().expect("tempdir");
        let mut publisher = publisher(dir.path());

        let mut collector = one_capture();
        collector.record_session("full-session", &mut publisher, save_a_cast);

        let recording = &collector.recordings()[0];
        assert_eq!(
            recording.error.as_deref(),
            Some("convert: no video converter configured")
        );
        // Steps 1 and 2 still happened, so the cast is still evidence.
        assert!(Path::new(&recording.cast).exists());
        assert!(std::fs::read_to_string(&recording.cast)
            .expect("cast")
            .contains("screen text"));
        assert_eq!(recording.video, None);
    }

    #[test]
    fn a_failed_conversion_is_never_uploaded() {
        // The error path a hand-written version gets wrong: uploading the path
        // a conversion did not produce, and reporting a store failure for a
        // video that was never encoded.
        let dir = tempfile::tempdir().expect("tempdir");
        let uploaded = Arc::new(Mutex::new(Vec::new()));
        let mut publisher = publisher(dir.path())
            .with_video_converter(broken_converter())
            .with_uploader(Box::new(CountingUploader(uploaded.clone())));

        let mut collector = one_capture();
        collector.record_session("full-session", &mut publisher, save_a_cast);

        let recording = &collector.recordings()[0];
        assert_eq!(
            recording.error.as_deref(),
            Some("convert: encoder exploded")
        );
        assert_eq!(recording.video, None);
        assert_eq!(recording.url, None);
        assert!(
            uploaded.lock().expect("poisoned").is_empty(),
            "an upload was attempted for a video that does not exist"
        );
    }

    #[test]
    fn a_failed_upload_keeps_the_video() {
        // Step 4 is last, so its failure costs the URL and nothing else. The
        // video is still on disk and still worth naming.
        struct Refuses;
        impl ArtifactUploader for Refuses {
            fn upload(&mut self, _: &str) -> Option<String> {
                None
            }
            fn last_error(&self) -> Option<&str> {
                Some("store down")
            }
        }
        let dir = tempfile::tempdir().expect("tempdir");
        let mut publisher = publisher(dir.path())
            .with_video_converter(stub_converter())
            .with_uploader(Box::new(Refuses));

        let mut collector = one_capture();
        collector.record_session("full-session", &mut publisher, save_a_cast);

        let recording = &collector.recordings()[0];
        assert_eq!(recording.error.as_deref(), Some("upload: store down"));
        assert!(recording.video.is_some());
        assert_eq!(recording.url, None);
    }

    #[test]
    fn an_uploader_that_declines_without_a_reason_still_names_the_step() {
        struct Silent;
        impl ArtifactUploader for Silent {
            fn upload(&mut self, _: &str) -> Option<String> {
                None
            }
            fn last_error(&self) -> Option<&str> {
                None
            }
        }
        let dir = tempfile::tempdir().expect("tempdir");
        let mut publisher = publisher(dir.path())
            .with_video_converter(stub_converter())
            .with_uploader(Box::new(Silent));

        let mut collector = one_capture();
        collector.record_session("full-session", &mut publisher, save_a_cast);

        assert_eq!(
            collector.recordings()[0].error.as_deref(),
            Some("upload: uploader returned no URL")
        );
    }

    #[test]
    fn a_publisher_with_no_uploader_is_not_a_failure() {
        // Absent is not broken: a publisher without an uploader was not asked
        // to upload, exactly as in `publish`.
        let dir = tempfile::tempdir().expect("tempdir");
        let mut publisher = publisher(dir.path()).with_video_converter(stub_converter());

        let mut collector = one_capture();
        collector.record_session("full-session", &mut publisher, save_a_cast);

        let recording = &collector.recordings()[0];
        assert_eq!(recording.error, None);
        assert!(recording.video.is_some());
        assert_eq!(recording.url, None);
    }

    #[test]
    fn two_recordings_with_one_label_do_not_share_a_cast() {
        // Labels are caller-supplied and may repeat; the second recording must
        // not overwrite the first one's evidence.
        let dir = tempfile::tempdir().expect("tempdir");
        let mut publisher = publisher(dir.path()).with_video_converter(stub_converter());

        let mut collector = one_capture();
        collector.record_session("full-session", &mut publisher, save_a_cast);
        collector.record_session("full-session", &mut publisher, save_a_cast);

        let recordings = collector.recordings();
        assert_ne!(recordings[0].cast, recordings[1].cast);
        assert_ne!(recordings[0].video, recordings[1].video);
        assert!(recordings[1]
            .cast
            .ends_with("recording-01-full-session.cast"));
        assert!(recordings.iter().all(|r| r.error.is_none()));
    }

    #[test]
    fn a_recorded_session_sits_beside_a_hand_attached_one() {
        // `record_session` and `attach_recording` write to the same list, in
        // call order, so a caller that encodes its own video is not shut out.
        let dir = tempfile::tempdir().expect("tempdir");
        let mut publisher = publisher(dir.path()).with_video_converter(stub_converter());

        let mut collector = one_capture();
        collector.attach_recording(Recording::new("hand-made", "/tmp/other.cast"));
        collector.record_session("full-session", &mut publisher, save_a_cast);

        let manifest = collector.publish(&mut publisher).expect("published");
        let labels: Vec<&str> = manifest
            .recordings
            .iter()
            .map(|r| r.label.as_str())
            .collect();
        assert_eq!(labels, ["hand-made", "full-session"]);
    }

    #[test]
    fn captures_keep_their_order_and_labels() {
        let mut s = session("a");
        let mut collector = EvidenceCollector::new();
        collector.capture("first", &mut s);
        s.set_screen("b");
        collector.capture_failure("blew-up", &mut s);

        assert_eq!(collector.steps()[0].index, 0);
        assert_eq!(collector.steps()[1].index, 1);
        assert_eq!(collector.steps()[1].label, "blew-up");
        assert_eq!(collector.steps()[1].kind, CaptureKind::Failure);
    }

    #[test]
    fn raw_output_is_kept_for_failures_only() {
        // It is the whole log, not the delta, so one copy per checkpoint is
        // quadratic and every copy but the last is a prefix of a later one.
        let mut s = session("screen");
        s.set_raw("all of it");
        let mut collector = EvidenceCollector::new();
        collector.capture("fine", &mut s);
        collector.capture_failure("broken", &mut s);

        assert_eq!(collector.steps()[0].raw_output, None);
        assert_eq!(
            collector.steps()[1].raw_output.as_deref(),
            Some("all of it")
        );
    }

    #[test]
    fn a_text_only_source_still_gets_a_grid() {
        let mut replay = Replay {
            frames: vec!["hello".into()],
            at: 0,
        };
        let mut collector = EvidenceCollector::with_grid(20, 2);
        collector.capture("only-text", &mut replay);
        assert_eq!(collector.steps()[0].attributed.to_text(true), "hello");
    }

    #[test]
    fn publish_writes_text_for_every_step() {
        // The reason this module persists text at all: a PNG shows a human
        // what happened, it does not show what an assertion matched against.
        let dir = tempfile::tempdir().expect("tempdir");
        let mut s = session("first screen");
        let mut collector = EvidenceCollector::new();
        collector.capture("start", &mut s);
        s.set_screen("second screen");
        collector.capture("end", &mut s);

        let manifest = collector
            .publish(&mut publisher(dir.path()))
            .expect("published");

        for step in &manifest.steps {
            assert!(Path::new(&step.screen_text).exists(), "{:?}", step);
        }
        assert_eq!(
            std::fs::read_to_string(&manifest.steps[0].screen_text).expect("read"),
            "first screen"
        );
    }

    #[test]
    fn a_deduped_step_still_gets_its_own_text() {
        // The image is the expensive artifact and the one worth sharing; the
        // text is the one worth grepping, and it costs a couple of kilobytes.
        let dir = tempfile::tempdir().expect("tempdir");
        let mut s = session("unchanged");
        let mut collector = EvidenceCollector::new();
        collector.capture("before", &mut s);
        collector.capture("after", &mut s);

        let (mut publisher, rendered) = counting_publisher(dir.path());
        let manifest = collector.publish(&mut publisher).expect("published");

        assert_eq!(rendered.lock().expect("poisoned").len(), 1);
        assert_eq!(
            manifest.steps[1].same_as,
            Some(ReusedFrom {
                index: 0,
                label: "before".to_string()
            })
        );
        assert_eq!(manifest.steps[0].screenshot, manifest.steps[1].screenshot);
        assert_ne!(manifest.steps[0].screen_text, manifest.steps[1].screen_text);
        assert!(Path::new(&manifest.steps[1].screen_text).exists());
    }

    #[test]
    fn a_reused_image_names_which_step_owns_it_even_when_labels_repeat() {
        // Labels are caller-supplied and may repeat. `same_as: "check"` in a
        // run with two steps called `check` points at nothing a reader can
        // resolve, so the index travels with it.
        let dir = tempfile::tempdir().expect("tempdir");
        let mut s = session("one");
        let mut collector = EvidenceCollector::new();
        collector.capture("check", &mut s);
        s.set_screen("two");
        collector.capture("other", &mut s);
        s.set_screen("three");
        collector.capture("check", &mut s);
        collector.capture("after", &mut s);

        let manifest = collector
            .publish(&mut publisher(dir.path()))
            .expect("published");
        let reused = manifest.steps[3].same_as.as_ref().expect("reused");
        assert_eq!(reused.label, "check");
        assert_eq!(reused.index, 2);
        assert_eq!(
            manifest.steps[3].screenshot, manifest.steps[2].screenshot,
            "the index must name the step that actually owns the image"
        );
    }

    #[test]
    fn dedup_only_looks_back_one_step() {
        // Capture order is publish order, which is what makes the deduper's
        // one-step lookback mean what it says.
        let dir = tempfile::tempdir().expect("tempdir");
        let mut s = session("one");
        let mut collector = EvidenceCollector::new();
        collector.capture("a", &mut s);
        s.set_screen("two");
        collector.capture("b", &mut s);
        s.set_screen("one");
        collector.capture("c", &mut s);

        let manifest = collector
            .publish(&mut publisher(dir.path()))
            .expect("published");
        assert_eq!(manifest.deduped().count(), 0);
        assert_eq!(manifest.steps[2].same_as, None);
    }

    #[test]
    fn same_text_different_colour_is_not_deduped() {
        let dir = tempfile::tempdir().expect("tempdir");
        struct Coloured(&'static str);
        impl ScreenSource for Coloured {
            fn capture_screen(&mut self, _: RawOutput) -> ScreenCapture {
                ScreenCapture {
                    screen: "hi".to_string(),
                    attributed: Some(attributed_screen_from_ansi_text(self.0, 20, 2)),
                    raw_output: None,
                }
            }
        }
        let mut collector = EvidenceCollector::new();
        collector.capture("red", &mut Coloured("\x1b[31mhi"));
        collector.capture("green", &mut Coloured("\x1b[32mhi"));

        let manifest = collector
            .publish(&mut publisher(dir.path()))
            .expect("published");
        assert_eq!(manifest.steps[1].same_as, None);
    }

    #[test]
    fn a_failed_render_does_not_make_the_next_identical_screen_reuse_it() {
        // `Deduper::forget`'s contract, exercised end to end: without it the
        // second step points at a PNG that was never produced.
        let dir = tempfile::tempdir().expect("tempdir");
        let attempts = Arc::new(Mutex::new(0usize));
        let sink = attempts.clone();
        let mut publisher = EvidencePublisher::new(dir.path(), identity()).with_renderer(
            ScreenshotRenderer::with_runner(Box::new(move |_, _, _| {
                *sink.lock().expect("poisoned") += 1;
                Err("rsvg-convert missing".to_string())
            })),
        );

        let mut s = session("unchanged");
        let mut collector = EvidenceCollector::new();
        collector.capture("before", &mut s);
        collector.capture("after", &mut s);
        let manifest = collector.publish(&mut publisher).expect("published");

        assert_eq!(*attempts.lock().expect("poisoned"), 2);
        assert_eq!(manifest.steps[1].same_as, None);
        assert!(manifest.steps.iter().all(|s| s.screenshot.is_none()));
        assert!(manifest.steps[0]
            .error
            .as_deref()
            .expect("error")
            .contains("rsvg-convert"));
        // The text is still there, so the failure is still diagnosable.
        assert!(Path::new(&manifest.steps[0].screen_text).exists());
    }

    #[test]
    fn uploads_are_best_effort() {
        struct Nope;
        impl ArtifactUploader for Nope {
            fn upload(&mut self, _: &str) -> Option<String> {
                None
            }
            fn last_error(&self) -> Option<&str> {
                Some("store down")
            }
        }
        let dir = tempfile::tempdir().expect("tempdir");
        let mut p = publisher(dir.path()).with_uploader(Box::new(Nope));
        let mut collector = EvidenceCollector::new();
        collector.capture("only", &mut session("x"));

        let manifest = collector.publish(&mut p).expect("published");
        assert_eq!(manifest.steps[0].url, None);
        assert!(manifest.steps[0].screenshot.is_some());
    }

    #[test]
    fn a_deduped_step_reuses_the_url_as_well_as_the_image() {
        struct Counting(usize);
        impl ArtifactUploader for Counting {
            fn upload(&mut self, _: &str) -> Option<String> {
                self.0 += 1;
                Some(format!("https://example/{}", self.0))
            }
            fn last_error(&self) -> Option<&str> {
                None
            }
        }
        let dir = tempfile::tempdir().expect("tempdir");
        let mut p = publisher(dir.path()).with_uploader(Box::new(Counting(0)));
        let mut s = session("same");
        let mut collector = EvidenceCollector::new();
        collector.capture("before", &mut s);
        collector.capture("after", &mut s);

        let manifest = collector.publish(&mut p).expect("published");
        assert_eq!(manifest.steps[0].url.as_deref(), Some("https://example/1"));
        assert_eq!(manifest.steps[1].url, manifest.steps[0].url);
    }

    #[test]
    fn the_manifest_is_written_and_reads_back() {
        let dir = tempfile::tempdir().expect("tempdir");
        let mut collector = EvidenceCollector::new();
        collector.capture("only", &mut session("x"));
        let manifest = collector
            .publish(&mut publisher(dir.path()))
            .expect("published");

        let written = std::fs::read_to_string(dir.path().join(MANIFEST_FILE)).expect("read");
        let parsed: EvidenceManifest = serde_json::from_str(&written).expect("parse");
        assert_eq!(parsed.manifest_version, EVIDENCE_MANIFEST_VERSION);
        assert_eq!(parsed.run, identity());
        assert_eq!(parsed.steps, manifest.steps);
        // Not serialized: the document does not record its own location.
        assert!(!written.contains(MANIFEST_FILE));
    }

    #[test]
    fn attaching_to_the_matching_run_records_the_manifest() {
        let dir = tempfile::tempdir().expect("tempdir");
        let mut collector = EvidenceCollector::new();
        collector.capture("only", &mut session("x"));
        let manifest = collector
            .publish(&mut publisher(dir.path()))
            .expect("published");

        let mut result = run_result("login", "default");
        manifest.attach_to(&mut result).expect("attached");
        assert_eq!(
            result
                .artifacts
                .get("evidence_manifest")
                .map(String::as_str),
            Some(path_string(&dir.path().join(MANIFEST_FILE)).as_str())
        );
    }

    #[test]
    fn evidence_from_another_run_is_refused() {
        // The cost of putting steps beside `RunResult` instead of inside it:
        // nothing in the file layout stops the wrong pair being made, so the
        // attach API is where it gets caught.
        let dir = tempfile::tempdir().expect("tempdir");
        let mut collector = EvidenceCollector::new();
        collector.capture("only", &mut session("x"));
        let manifest = collector
            .publish(&mut publisher(dir.path()))
            .expect("published");

        let mut other = run_result("checkout", "default");
        let error = manifest.attach_to(&mut other).expect_err("refused");
        assert!(error.contains("login"), "{error}");
        assert!(error.contains("checkout"), "{error}");
        // Refused means untouched, not half-attached.
        assert!(other.artifacts.is_empty());

        let mut other_renderer = run_result("login", "tmux");
        assert!(manifest.attach_to(&mut other_renderer).is_err());
    }

    #[test]
    fn a_run_id_comes_from_the_run_directory() {
        // Recipe and renderer separate two different recipes; they do not
        // separate two runs of the same one. `new_run_dir` already builds a
        // name unique per timestamp, pid and entropy, so that is the run id
        // rather than a second one invented here.
        let base = Path::new("/tmp/out");
        let first = crate::store::new_run_dir(base, "login", "default");
        let identity = RunIdentity::from_run_dir(&first, "login", "default");
        assert_eq!(
            identity.run_id,
            first.file_name().expect("name").to_string_lossy()
        );
        assert!(identity.run_id.contains("login"));
        assert!(identity.matches(&run_result("login", "default")));
    }

    #[test]
    fn filenames_are_ordered_and_sanitized() {
        let step = CapturedStep {
            index: 7,
            label: "menu/open: 100%".to_string(),
            kind: CaptureKind::Checkpoint,
            screen: String::new(),
            attributed: AttributedScreen::default(),
            raw_output: None,
        };
        assert_eq!(step.file_stem(), "step-07-menu-open--100-");
    }

    #[test]
    fn a_long_label_does_not_produce_a_long_filename() {
        let step = CapturedStep {
            index: 0,
            label: "x".repeat(200),
            kind: CaptureKind::Checkpoint,
            screen: String::new(),
            attributed: AttributedScreen::default(),
            raw_output: None,
        };
        assert_eq!(step.file_stem().len(), "step-00-".len() + 40);
    }

    #[test]
    fn publishing_twice_is_allowed() {
        // `publish` takes `&self`, so a run can write evidence to a scratch
        // directory mid-run and to its final home at the end.
        let dir = tempfile::tempdir().expect("tempdir");
        let other = tempfile::tempdir().expect("tempdir");
        let mut collector = EvidenceCollector::new();
        collector.capture("only", &mut session("x"));

        let first = collector
            .publish(&mut publisher(dir.path()))
            .expect("published");
        let second = collector
            .publish(&mut publisher(other.path()))
            .expect("published");
        assert_ne!(first.path(), second.path());
        assert_eq!(first.steps.len(), second.steps.len());
    }

    #[test]
    fn publishing_nothing_still_writes_a_manifest() {
        let dir = tempfile::tempdir().expect("tempdir");
        let manifest = EvidenceCollector::new()
            .publish(&mut publisher(dir.path()))
            .expect("published");
        assert!(manifest.steps.is_empty());
        assert!(dir.path().join(MANIFEST_FILE).exists());
    }
}
