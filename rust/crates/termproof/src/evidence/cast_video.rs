//! Video from a cast, rendered by the same code as the screenshots.
//!
//! [`AggFfmpegBackend`](crate::evidence::video::AggFfmpegBackend) shells out to `agg`,
//! which has its own fonts and its own colour handling. That works, but it
//! means a still and a frame of the same screen come from two unrelated
//! renderers and do not look alike.
//!
//! This backend replays the cast through the terminal emulator, samples the
//! grid at a fixed frame rate, and renders each frame with
//! [`screen_svg`](crate::terminal::attributed::screen_svg) — the same
//! function behind [`crate::evidence::screenshot`]. The video is literally the
//! screenshots in sequence. That holds for this backend only: `agg_ffmpeg` is
//! still the configured default, so choosing it is what buys the shared visual
//! language.
//!
//! It also drops a binary dependency: `rsvg-convert` and `ffmpeg`, no `agg`.
//!
//! # Why this one still uses `avt`
//!
//! The rest of the crate emulates with `vt100`. Cast *playback* — replaying
//! timed output events and sampling the grid between them — is what `avt`
//! exists for, and reimplementing it on `vt100` would be rebuilding a player to
//! avoid a dependency the format's own tooling uses. Stated here rather than
//! left for a reviewer to notice.
//!
//! # Trailing checkpoint frames
//!
//! [`append_checkpoint_frames`] writes the captured screens onto the end of a
//! cast as held frames, so the recording finishes by replaying the evidence
//! sequence instead of stopping on whatever the last keystroke painted. It is
//! the reason a reviewer watches one artifact rather than opening fifteen
//! stills, and it works on a closed cast — nothing about it needs the session
//! that produced the file to still be running.

use std::fs;
use std::io::Write;
use std::path::Path;
use std::process::Command;
use std::time::Duration;

use avt::Vt;

use crate::evidence::collector::CapturedStep;
use crate::terminal::attributed::palette_color;
use crate::terminal::attributed::rgb_color;
use crate::terminal::attributed::screen_svg;
use crate::terminal::attributed::AttributedCell;
use crate::terminal::attributed::AttributedScreen;
use crate::terminal::attributed::SvgMetrics;
use crate::terminal::attributed::DEFAULT_CELL_H;
use crate::terminal::attributed::DEFAULT_CELL_W;
use crate::terminal::attributed::DEFAULT_COLUMNS;
use crate::terminal::attributed::DEFAULT_FONT_PX;
use crate::terminal::attributed::DEFAULT_PADDING;
use crate::terminal::attributed::DEFAULT_ROWS;
use crate::terminal::proc::combined_output;
use crate::terminal::proc::run_with_timeout;

const RSVG_CONVERT: &str = "/usr/bin/rsvg-convert";
const FFMPEG: &str = "/usr/local/bin/ffmpeg";
const RSVG_TIMEOUT: Duration = Duration::from_secs(30);
const FFMPEG_TIMEOUT: Duration = Duration::from_secs(120);

/// Seconds an appended checkpoint screen stays up before the next one paints.
///
/// Long enough to read a screen of terminal text, short enough that fifteen of
/// them are still a recording someone sits through. The same three seconds
/// `agg --last-frame-duration` and the Python `DEFAULT_CHECKPOINT_HOLD` use, so
/// a recording's closing hold does not change pace depending on who wrote it.
pub const DEFAULT_CHECKPOINT_HOLD: f64 = 3.0;

/// Repaint the whole grid: reset the pen, home the cursor, clear the screen.
///
/// A checkpoint screen is a complete picture, not a delta, so it is painted
/// over whatever the previous frame left rather than after it.
const REPAINT_PREFIX: &str = "\x1b[m\x1b[H\x1b[2J";

/// Written once after the last checkpoint, purely to keep the recording
/// running for one more hold.
///
/// A cast ends at its final event, so without this the last screen — the one
/// the run ended on, and the one a reviewer skipped to the end for — would
/// flash for an instant instead of being held like every screen before it. An
/// SGR reset is the cheapest event that changes nothing on screen.
const HOLD_TERMINATOR: &str = "\x1b[m";

/// `(executable, args, timeout)` -> `Ok(())` or an error message.
pub type ToolRunner = Box<dyn Fn(&str, &[String], Duration) -> Result<(), String> + Send + Sync>;

/// Default runner: invoke the tool, error on non-zero exit.
pub fn default_runner() -> ToolRunner {
    Box::new(|executable, args, timeout| {
        let mut cmd = Command::new(executable);
        cmd.args(args);
        let output = run_with_timeout(cmd, timeout).map_err(|e| e.to_string())?;
        if !output.status.success() {
            return Err(format!(
                "{} exited {}: {}",
                executable,
                output.status.code().unwrap_or(-1),
                combined_output(&output),
            ));
        }
        Ok(())
    })
}

/// Renders an asciinema v2 cast file to an MP4.
pub struct CastVideoConverter {
    /// 2 fps sampled a 30s session 59 times and missed every transient state;
    /// the reference recording that reads well is 24.
    pub fps: u32,
    /// Longest gap, in seconds, that a pause in the cast is played back at
    /// before it is truncated. Keeps a session that sat idle for a minute from
    /// producing a minute of unchanging video.
    pub idle_time_limit: f64,
    /// Grid width, in cells.
    pub columns: usize,
    /// Grid height, in cells.
    pub rows: usize,
    /// Cell width, in SVG units.
    pub cell_w: f64,
    /// Cell height, in SVG units.
    pub cell_h: f64,
    /// Font size, in SVG units.
    pub font_px: u32,
    /// Margin around the grid, in SVG units.
    pub padding: u32,
    /// Frame size; derived from the grid when `None`.
    pub width: Option<usize>,
    /// Frame height; derived from the grid when `None`. See
    /// [`width`](Self::width).
    pub height: Option<usize>,
    runner: ToolRunner,
}

impl Default for CastVideoConverter {
    fn default() -> Self {
        CastVideoConverter {
            fps: 24,
            idle_time_limit: 1.0,
            columns: DEFAULT_COLUMNS,
            rows: DEFAULT_ROWS,
            cell_w: DEFAULT_CELL_W,
            cell_h: DEFAULT_CELL_H,
            font_px: DEFAULT_FONT_PX,
            padding: DEFAULT_PADDING,
            width: None,
            height: None,
            runner: default_runner(),
        }
    }
}

impl CastVideoConverter {
    /// A converter with the default frame rate, grid and encoding tool.
    pub fn new() -> Self {
        Self::default()
    }

    /// A default converter that shells out through `runner` instead of the
    /// real encoder. This is the seam the tests use.
    pub fn with_runner(runner: ToolRunner) -> Self {
        CastVideoConverter {
            runner,
            ..Self::default()
        }
    }

    /// Canvas geometry for each frame, honouring [`width`](Self::width) and
    /// [`height`](Self::height) if they are set.
    pub fn metrics(&self) -> SvgMetrics {
        let mut metrics = SvgMetrics {
            columns: self.columns,
            rows: self.rows,
            cell_w: self.cell_w,
            cell_h: self.cell_h,
            font_px: self.font_px,
            padding: self.padding,
            width: 0,
            height: 0,
        };
        metrics.width = self.width.unwrap_or_else(|| metrics.derived_width());
        metrics.height = self.height.unwrap_or_else(|| metrics.derived_height());
        metrics
    }

    /// Frame width, in pixels.
    pub fn frame_width(&self) -> usize {
        self.metrics().width
    }

    /// Frame height, in pixels.
    pub fn frame_height(&self) -> usize {
        self.metrics().height
    }

    /// The default output path for `cast_path`: the same path with an `.mp4`
    /// extension.
    pub fn output_path_for(&self, cast_path: &str) -> String {
        let p = Path::new(cast_path);
        p.with_extension("mp4").to_string_lossy().to_string()
    }

    /// Convert `cast_path` to MP4 and return the video path.
    pub fn convert(&self, cast_path: &str, video_path: Option<&str>) -> Result<String, String> {
        let output_path = video_path
            .map(|s| s.to_string())
            .unwrap_or_else(|| self.output_path_for(cast_path));
        if let Some(parent) = Path::new(&output_path).parent() {
            if !parent.as_os_str().is_empty() {
                fs::create_dir_all(parent).map_err(|e| e.to_string())?;
            }
        }

        let frames = self.frames_from_cast(cast_path)?;
        let tmpdir = tempfile::Builder::new()
            .prefix("termproof_cast_frames_")
            .tempdir()
            .map_err(|e| e.to_string())?;

        let metrics = self.metrics();
        for (index, frame) in frames.iter().enumerate() {
            let svg_path = tmpdir.path().join(format!("frame-{:05}.svg", index));
            let png_path = tmpdir.path().join(format!("frame-{:05}.png", index));
            fs::write(&svg_path, screen_svg(frame, &metrics)).map_err(|e| e.to_string())?;
            (self.runner)(
                RSVG_CONVERT,
                &[
                    "--output".to_string(),
                    png_path.to_string_lossy().to_string(),
                    svg_path.to_string_lossy().to_string(),
                ],
                RSVG_TIMEOUT,
            )?;
        }

        let frame_glob = tmpdir.path().join("frame-%05d.png");
        (self.runner)(
            FFMPEG,
            &[
                "-y".to_string(),
                "-framerate".to_string(),
                self.fps.to_string(),
                "-i".to_string(),
                frame_glob.to_string_lossy().to_string(),
                "-c:v".to_string(),
                "libx264".to_string(),
                // yuv444p, not yuv420p: 4:2:0 subsamples chroma 2x2, which
                // smears the edges of coloured text. Terminal frames are almost
                // all text, so the extra bitrate is worth it.
                "-pix_fmt".to_string(),
                "yuv444p".to_string(),
                "-crf".to_string(),
                "15".to_string(),
                "-preset".to_string(),
                "slower".to_string(),
                "-tune".to_string(),
                "stillimage".to_string(),
                "-movflags".to_string(),
                "+faststart".to_string(),
                output_path.clone(),
            ],
            FFMPEG_TIMEOUT,
        )?;
        Ok(output_path)
    }

    fn frames_from_cast(&self, cast_path: &str) -> Result<Vec<AttributedScreen>, String> {
        let contents = fs::read_to_string(cast_path).map_err(|e| e.to_string())?;
        let mut lines = contents.lines();
        let header_line = lines.next().ok_or("empty cast file")?;
        let header: serde_json::Value =
            serde_json::from_str(header_line).map_err(|e| e.to_string())?;
        let width = header
            .get("width")
            .and_then(|v| v.as_u64())
            .map(|v| v as usize)
            .unwrap_or(self.columns);
        let height = header
            .get("height")
            .and_then(|v| v.as_u64())
            .map(|v| v as usize)
            .unwrap_or(self.rows);
        let mut vt = Vt::new(width.max(1), height.max(1));

        let mut frames: Vec<AttributedScreen> = Vec::new();
        let mut next_frame_at = 0.0_f64;
        let mut playback_time = 0.0_f64;
        let mut previous_cast_time = 0.0_f64;
        let frame_interval = 1.0 / self.fps as f64;

        for line in lines {
            if line.trim().is_empty() {
                continue;
            }
            let event: serde_json::Value = serde_json::from_str(line).map_err(|e| e.to_string())?;
            let arr = match event.as_array() {
                Some(a) if a.len() >= 3 => a,
                _ => continue,
            };
            let event_type = arr[1].as_str().unwrap_or("");
            if event_type != "o" {
                continue;
            }
            let timestamp = arr[0].as_f64().unwrap_or(0.0);
            let data = arr[2].as_str().unwrap_or("");
            let elapsed = (timestamp - previous_cast_time).max(0.0);
            // Collapse a long pause to idle_time_limit so a session that sat
            // waiting on the model does not become minutes of still frames.
            playback_time += elapsed.min(self.idle_time_limit);
            previous_cast_time = timestamp;
            vt.feed_str(data);
            while next_frame_at <= playback_time {
                frames.push(attributed_screen_from_avt(&vt));
                next_frame_at += frame_interval;
            }
        }

        let final_snapshot = attributed_screen_from_avt(&vt);
        if frames.is_empty() || frames.last() != Some(&final_snapshot) {
            frames.push(final_snapshot);
        }
        Ok(frames)
    }
}

/// Append each captured screen to `cast_path` as a held trailing frame.
///
/// A cast stops at whatever the last keystroke painted, which is rarely the
/// evidence — the checkpoints that made the run reviewable have already
/// scrolled away by then. This writes them back onto the end, in capture
/// order, each one repainting the whole grid and held for `hold_seconds`
/// (default [`DEFAULT_CHECKPOINT_HOLD`]) before the next. A reviewer then
/// watches one recording instead of opening every still beside it.
///
/// Returns how many frames were appended. An empty `steps` is a silent no-op:
/// the file is not opened, let alone rewritten.
///
/// # What it does to the file
///
/// Appends only. The header and every recorded event are left exactly as the
/// session wrote them, and the new events carry on from the last timestamp in
/// the file rather than restarting at zero, so the result is still a valid
/// asciinema v2 cast with timestamps that only increase. The session does not
/// have to be running — this reads and appends to a closed file, which is what
/// lets it run after `close()` has already reported the exit code.
///
/// Every captured step is appended, [`CaptureKind::Failure`](crate::evidence::CaptureKind)
/// included. A run's failure screen is the frame a reviewer most wants held,
/// so filtering by kind would drop exactly the wrong one.
///
/// The first checkpoint lands one hold after the session's final event, which
/// leaves the live ending on screen for a beat before the replay starts.
///
/// # Errors
///
/// If the cast cannot be read or appended to, if it has no header line, or if
/// `hold_seconds` is not a positive, finite number of seconds — a hold that is
/// not would stall or reverse the timestamps this promises to keep increasing.
pub fn append_checkpoint_frames(
    cast_path: &str,
    steps: &[CapturedStep],
    hold_seconds: Option<f64>,
) -> Result<usize, String> {
    if steps.is_empty() {
        return Ok(0);
    }
    let hold = hold_seconds.unwrap_or(DEFAULT_CHECKPOINT_HOLD);
    if !hold.is_finite() || hold <= 0.0 {
        return Err(format!(
            "checkpoint hold must be a positive number of seconds, got {hold}"
        ));
    }

    let contents = fs::read_to_string(cast_path).map_err(|e| e.to_string())?;
    let mut lines = contents.lines();
    lines.next().ok_or("empty cast file")?;
    let last_event_at = last_event_time(lines);

    let mut appended = String::new();
    // A cast written by a crashed recorder can lack its final newline, and
    // appending to it blind would splice two events into one unparseable line.
    if !contents.ends_with('\n') {
        appended.push('\n');
    }
    for (offset, step) in steps.iter().enumerate() {
        let at = last_event_at + hold * (offset + 1) as f64;
        appended.push_str(&cast_event_line(at, &repaint(&step.screen))?);
    }
    let end = last_event_at + hold * (steps.len() + 1) as f64;
    appended.push_str(&cast_event_line(end, HOLD_TERMINATOR)?);

    let mut file = fs::OpenOptions::new()
        .append(true)
        .open(cast_path)
        .map_err(|e| e.to_string())?;
    file.write_all(appended.as_bytes())
        .map_err(|e| e.to_string())?;
    Ok(steps.len())
}

/// The latest timestamp already in the cast, so the appended frames continue
/// from the session instead of restarting at zero.
///
/// The largest rather than the last: a cast is written in order, but reading
/// the maximum costs nothing and keeps the monotonicity promise even against a
/// file some other tool has already appended to out of order.
fn last_event_time<'a>(lines: impl Iterator<Item = &'a str>) -> f64 {
    lines
        .filter_map(|line| serde_json::from_str::<serde_json::Value>(line).ok())
        .filter_map(|event| event.get(0).and_then(|v| v.as_f64()))
        .filter(|at| at.is_finite())
        .fold(0.0_f64, f64::max)
}

/// One screen's worth of output data: a full repaint, with the newlines a
/// terminal needs rather than the ones a text file has.
fn repaint(screen: &str) -> String {
    format!(
        "{REPAINT_PREFIX}{}",
        screen.replace("\r\n", "\n").replace('\n', "\r\n")
    )
}

/// Serialise one `[timestamp, "o", data]` event, newline included.
///
/// The Python implementation writes these same lines, and pins its encoder to
/// `serde_json`'s shape — compact separators, raw UTF-8 — so the two produce
/// the same bytes for the same screens and the conformance pair can compare
/// them literally.
fn cast_event_line(at: f64, data: &str) -> Result<String, String> {
    // Six decimals, matching what the recorders on both sides write, so the
    // appended lines do not carry more precision than the ones above them.
    let at = (at * 1e6).round() / 1e6;
    let event = serde_json::json!([at, "o", data]);
    let line = serde_json::to_string(&event).map_err(|e| e.to_string())?;
    Ok(format!("{line}\n"))
}

/// Build an attributed screen from an `avt` grid.
///
/// Lives here rather than in [`crate::terminal`] so that module stays
/// `vt100`-only: cast playback is the one place `avt` earns its keep, and a
/// second emulator in the terminal layer would be a cost every consumer pays.
fn attributed_screen_from_avt(vt: &Vt) -> AttributedScreen {
    let rows = vt
        .view()
        .iter()
        .map(|line| line.cells().iter().map(cell_from_avt).collect())
        .collect();
    let cursor = vt.cursor();
    AttributedScreen {
        rows,
        cursor_row: cursor.row,
        cursor_column: cursor.col,
        cursor_hidden: !cursor.visible,
    }
}

/// Convert one `avt` cell, keeping `avt`'s own width.
///
/// # The one width table we do not control
///
/// Everywhere else, in-tree width decisions are pinned to the `unicode-width`
/// major `vt100` uses, so [`crate::terminal::attributed`]'s two paths agree
/// about which column a glyph occupies. `avt` brings its own `unicode-width`
/// 0.1, and as of `avt` 0.18 — the latest release — there is no version built
/// against 0.2, so this path cannot be brought onto that table.
///
/// We take `avt`'s width rather than recomputing it. `avt` already *placed*
/// the glyph and its filler using its own table; substituting a width from a
/// different table would leave the cell disagreeing with the grid it sits in,
/// and [`crate::terminal::attributed::screen_svg`] paints the background rect
/// from that width — a cell claiming two columns where `avt` allocated one
/// spills over its neighbour. A self-consistent frame measured by an older
/// table is better evidence than an incoherent one.
///
/// The practical effect is that a cast frame and a live `vt100` screen can
/// place the same code point in different columns; `cast_frames_use_avts_width_table`
/// pins a concrete case, and fails when `avt` catches up so this can be
/// revisited rather than quietly outliving the constraint.
fn cell_from_avt(cell: &avt::Cell) -> AttributedCell {
    let pen = cell.pen();
    let width = cell.width().min(2) as u8;
    AttributedCell {
        // A width-0 cell is the filler behind a wide glyph; it carries no text
        // of its own, matching what the SGR parser produces.
        text: if width == 0 {
            String::new()
        } else {
            cell.char().to_string()
        },
        fg: avt_color(pen.foreground()),
        bg: avt_color(pen.background()),
        bold: pen.is_bold(),
        dim: pen.is_faint(),
        italic: pen.is_italic(),
        underline: pen.is_underline(),
        strikethrough: pen.is_strikethrough(),
        reverse: pen.is_inverse(),
        width,
    }
}

fn avt_color(color: Option<avt::Color>) -> String {
    match color {
        None => "default".to_string(),
        Some(avt::Color::Indexed(index)) => palette_color(index as u16),
        Some(avt::Color::RGB(rgb)) => rgb_color(rgb.r, rgb.g, rgb.b),
    }
}

#[cfg(test)]
mod tests {
    use std::sync::Arc;
    use std::sync::Mutex;

    use super::*;
    use crate::evidence::CaptureKind;
    use crate::terminal::attributed::attributed_screen_from_text;

    fn cast_with(events: &str) -> (tempfile::TempDir, String) {
        let dir = tempfile::tempdir().unwrap();
        let cast = dir.path().join("r.cast");
        fs::write(
            &cast,
            format!("{{\"version\":2,\"width\":10,\"height\":3}}\n{}", events),
        )
        .unwrap();
        let path = cast.to_string_lossy().to_string();
        (dir, path)
    }

    fn frames(events: &str) -> Vec<AttributedScreen> {
        let (_dir, path) = cast_with(events);
        CastVideoConverter::new().frames_from_cast(&path).unwrap()
    }

    #[test]
    fn output_path_swaps_extension() {
        let conv = CastVideoConverter::new();
        assert_eq!(conv.output_path_for("/tmp/a/b.cast"), "/tmp/a/b.mp4");
    }

    #[test]
    fn frames_from_simple_cast() {
        let f = frames("[0.0, \"o\", \"hi\"]\n[0.5, \"o\", \"!\"]\n");
        assert!(!f.is_empty());
        assert_eq!(f.last().unwrap().text_lines(true)[0], "hi!");
    }

    #[test]
    fn non_output_events_are_ignored() {
        let f = frames("[0.0, \"i\", \"typed\"]\n[0.1, \"o\", \"ok\"]\n");
        assert_eq!(f.last().unwrap().text_lines(true)[0], "ok");
    }

    #[test]
    fn frame_count_follows_the_frame_rate() {
        // One second of playback at 24 fps, capped by idle_time_limit 1.0.
        let f = frames("[0.0, \"o\", \"a\"]\n[1.0, \"o\", \"b\"]\n");
        assert_eq!(f.len(), 25);
    }

    #[test]
    fn a_long_pause_is_collapsed_to_the_idle_limit() {
        // 60s of waiting must not become 60s of still frames.
        let f = frames("[0.0, \"o\", \"a\"]\n[60.0, \"o\", \"b\"]\n");
        assert_eq!(f.len(), 25);
    }

    #[test]
    fn cast_frames_use_avts_width_table() {
        // U+1FA89 is one column under `unicode-width` 0.1 and two under 0.2.
        // The rest of the crate is pinned to 0.2 to match `vt100`; `avt` is
        // built against 0.1 and cannot be moved, so a cast frame measures this
        // code point differently from a live screen. That is a real fidelity
        // gap, documented on `cell_from_avt` — this test is what stops it
        // being a silent one.
        //
        // When this fails because `avt` has moved to 0.2, the gap is closed:
        // delete the test and the caveat rather than adjusting the expectation.
        // Written as a surrogate pair because a `.cast` line is JSON, which
        // has no `\u{...}` form for an astral code point.
        let f = frames("[0.0, \"o\", \"\\ud83e\\ude89x\"]\n");
        let row = &f.last().unwrap().rows[0];
        assert_eq!(
            row[0].width, 1,
            "avt no longer measures U+1FA89 with the unicode-width 0.1 table; \
             re-check whether avt and vt100 can now share one table"
        );
        assert_eq!(row[1].text, "x", "x should sit in the adjacent column");

        // The same bytes through the vt100-backed path put `x` one column
        // further along. Asserted so the divergence is stated, not implied.
        let mut parser = vt100::Parser::new(3, 10, 0);
        parser.process("\u{1FA89}x".as_bytes());
        let live = crate::terminal::attributed::from_vt100(parser.screen());
        assert_eq!(live.rows[0][0].width, 2);
        assert_eq!(live.rows[0][2].text, "x");
    }

    // -- Cases the hand-rolled grid got wrong -------------------------------

    #[test]
    fn alternate_screen_repaints_are_captured() {
        // Ink repaints whole frames on the alternate screen. The old grid had
        // no concept of one, so these captures came back as noise.
        let f = frames(
            "[0.0, \"o\", \"scrollback\"]\n\
             [0.1, \"o\", \"\\u001b[?1049h\\u001b[H\\u001b[2Jalt\"]\n",
        );
        assert_eq!(f.last().unwrap().text_lines(true)[0], "alt");
    }

    #[test]
    fn scroll_region_is_honored() {
        // DECSTBM: a scroll confined to rows 1-2 must leave row 3 alone.
        let f = frames(
            "[0.0, \"o\", \"a\\r\\nb\\r\\nkeep\"]\n\
             [0.1, \"o\", \"\\u001b[1;2r\\u001b[2;1H\\n\\rc\"]\n",
        );
        let text = f.last().unwrap().text_lines(true);
        assert_eq!(text[0], "b");
        assert_eq!(text[1], "c");
        assert_eq!(text[2], "keep");
    }

    #[test]
    fn colors_survive_into_the_frame() {
        // The old grid stored plain chars, so every frame rendered monochrome.
        let f = frames("[0.0, \"o\", \"\\u001b[31mred\\u001b[0m\"]\n");
        let cell = &f.last().unwrap().rows[0][0];
        assert_eq!(cell.fg, "red");
        assert_eq!(f.last().unwrap().rows[0][3].fg, "default");
    }

    #[test]
    fn indexed_and_rgb_colors_map_to_hex() {
        let f = frames("[0.0, \"o\", \"\\u001b[38;5;196ma\\u001b[38;2;1;2;3mb\"]\n");
        let row = &f.last().unwrap().rows[0];
        assert_eq!(row[0].fg, "ff0000");
        assert_eq!(row[1].fg, "010203");
    }

    #[test]
    fn text_attributes_survive_into_the_frame() {
        let f = frames("[0.0, \"o\", \"\\u001b[1;3;4;9;7ma\"]\n");
        let cell = &f.last().unwrap().rows[0][0];
        assert!(cell.bold && cell.italic && cell.underline);
        assert!(cell.strikethrough && cell.reverse);
    }

    #[test]
    fn wide_glyph_keeps_its_filler_column() {
        let f = frames("[0.0, \"o\", \"\\u4f60x\"]\n");
        let row = &f.last().unwrap().rows[0];
        assert_eq!(row[0].width, 2);
        assert_eq!(row[1].width, 0);
        assert_eq!(row[2].text, "x");
    }

    #[test]
    fn frames_are_rendered_and_stitched() {
        let calls = Arc::new(Mutex::new(Vec::new()));
        let sink = calls.clone();
        let conv = CastVideoConverter::with_runner(Box::new(move |exe, args, _| {
            sink.lock()
                .expect("poisoned")
                .push((exe.to_string(), args.to_vec()));
            Ok(())
        }));
        let (dir, path) = cast_with("[0.0, \"o\", \"hi\"]\n");
        let out = dir.path().join("out.mp4").to_string_lossy().to_string();
        assert_eq!(conv.convert(&path, Some(&out)).unwrap(), out);

        let calls = calls.lock().unwrap();
        let (ffmpeg_exe, ffmpeg_args) = calls.last().unwrap();
        assert_eq!(ffmpeg_exe, FFMPEG);
        assert!(ffmpeg_args.contains(&"yuv444p".to_string()));
        assert!(ffmpeg_args.contains(&"stillimage".to_string()));
        assert!(ffmpeg_args.contains(&"24".to_string()));
        // Every earlier call rasterizes one frame.
        assert!(calls[..calls.len() - 1]
            .iter()
            .all(|(e, _)| e == RSVG_CONVERT));
    }

    #[test]
    fn a_frame_is_the_still_the_screenshot_renderer_would_draw() {
        // The module claims the video is the screenshots in sequence. Asserting
        // only that each frame goes to `rsvg-convert` would leave that claim
        // resting on the SVG being the right one, which nothing checked.
        let seen = Arc::new(Mutex::new(Vec::new()));
        let sink = seen.clone();
        let conv = CastVideoConverter::with_runner(Box::new(move |exe, args, _| {
            if exe == RSVG_CONVERT {
                sink.lock()
                    .expect("poisoned")
                    .push(fs::read_to_string(&args[2]).expect("frame written"));
            }
            Ok(())
        }));
        let (dir, path) = cast_with("[0.0, \"o\", \"hi\"]\n");
        let out = dir.path().join("out.mp4").to_string_lossy().to_string();
        conv.convert(&path, Some(&out)).unwrap();

        let expected = screen_svg(&frames("[0.0, \"o\", \"hi\"]\n")[0], &conv.metrics());
        let seen = seen.lock().expect("poisoned");
        assert_eq!(seen.first().map(String::as_str), Some(expected.as_str()));
    }

    // -- Trailing checkpoint frames -----------------------------------------

    fn step(index: usize, label: &str, screen: &str, kind: CaptureKind) -> CapturedStep {
        CapturedStep {
            index,
            label: label.to_string(),
            kind,
            screen: screen.to_string(),
            attributed: attributed_screen_from_text(screen, 10, 3),
            raw_output: None,
        }
    }

    fn checkpoint(index: usize, label: &str, screen: &str) -> CapturedStep {
        step(index, label, screen, CaptureKind::Checkpoint)
    }

    /// Every event in the cast as `(timestamp, data)`, header dropped.
    fn events_in(path: &str) -> Vec<(f64, String)> {
        fs::read_to_string(path)
            .unwrap()
            .lines()
            .skip(1)
            .map(|line| serde_json::from_str::<serde_json::Value>(line).expect("valid event"))
            .map(|e| {
                (
                    e[0].as_f64().expect("timestamp"),
                    e[2].as_str().expect("data").to_string(),
                )
            })
            .collect()
    }

    #[test]
    fn checkpoints_are_appended_in_capture_order() {
        let (_dir, path) = cast_with("[0.5, \"o\", \"live\"]\n");
        let steps = [
            checkpoint(0, "one", "first"),
            checkpoint(1, "two", "second"),
        ];
        assert_eq!(append_checkpoint_frames(&path, &steps, None).unwrap(), 2);

        let events = events_in(&path);
        // The session's own event, the two checkpoints, and the closing hold.
        assert_eq!(events.len(), 4);
        assert_eq!(events[0].1, "live");
        assert!(events[1].1.ends_with("first"), "{:?}", events[1].1);
        assert!(events[2].1.ends_with("second"), "{:?}", events[2].1);
        assert_eq!(events[3].1, HOLD_TERMINATOR);
    }

    #[test]
    fn timestamps_continue_from_the_session_and_only_increase() {
        let (_dir, path) = cast_with("[0.5, \"o\", \"a\"]\n[2.25, \"o\", \"b\"]\n");
        let steps = [
            checkpoint(0, "one", "first"),
            checkpoint(1, "two", "second"),
        ];
        append_checkpoint_frames(&path, &steps, Some(1.5)).unwrap();

        let times: Vec<f64> = events_in(&path).iter().map(|(at, _)| *at).collect();
        assert_eq!(times, vec![0.5, 2.25, 3.75, 5.25, 6.75]);
        assert!(times.windows(2).all(|w| w[1] > w[0]));
    }

    #[test]
    fn the_hold_is_the_gap_between_frames_and_defaults() {
        let (_dir, path) = cast_with("[0.0, \"o\", \"a\"]\n");
        let steps = [
            checkpoint(0, "one", "first"),
            checkpoint(1, "two", "second"),
        ];
        append_checkpoint_frames(&path, &steps, None).unwrap();

        let times: Vec<f64> = events_in(&path).iter().map(|(at, _)| *at).collect();
        let hold = DEFAULT_CHECKPOINT_HOLD;
        // The last checkpoint is held as long as the ones before it, which is
        // what the closing event is for.
        assert_eq!(times, vec![0.0, hold, 2.0 * hold, 3.0 * hold]);
    }

    #[test]
    fn no_checkpoints_is_a_silent_no_op() {
        let (_dir, path) = cast_with("[0.0, \"o\", \"a\"]\n");
        let before = fs::read_to_string(&path).unwrap();
        assert_eq!(append_checkpoint_frames(&path, &[], None).unwrap(), 0);
        assert_eq!(fs::read_to_string(&path).unwrap(), before);

        // No-op, not merely harmless: a run that captured nothing must not
        // fail, and must not need the cast to be there to be told so.
        let missing = format!("{path}.does-not-exist");
        assert_eq!(append_checkpoint_frames(&missing, &[], None).unwrap(), 0);
    }

    #[test]
    fn the_appended_cast_still_replays() {
        let (_dir, path) = cast_with("[0.0, \"o\", \"live\"]\n");
        let steps = [
            checkpoint(0, "one", "first"),
            checkpoint(1, "two", "second"),
        ];
        append_checkpoint_frames(&path, &steps, None).unwrap();

        // Replaying it is the strongest statement that it is still a cast:
        // the player parses the header, every event and every payload.
        let frames = CastVideoConverter::new().frames_from_cast(&path).unwrap();
        let painted: Vec<String> = frames
            .iter()
            .map(|f| f.text_lines(true)[0].clone())
            .collect();
        assert_eq!(painted.last().unwrap(), "second");
        assert!(painted.contains(&"live".to_string()));
        assert!(
            painted.iter().position(|t| t == "first") < painted.iter().position(|t| t == "second"),
            "the evidence replays in capture order"
        );
    }

    #[test]
    fn a_multi_line_screen_is_repainted_row_by_row() {
        // A cast payload goes to a raw terminal, where a bare newline drops a
        // row without returning the carriage and the screen comes back as a
        // staircase.
        let (_dir, path) = cast_with("[0.0, \"o\", \"live\"]\n");
        append_checkpoint_frames(&path, &[checkpoint(0, "menu", "MENU\nitem")], None).unwrap();

        let frames = CastVideoConverter::new().frames_from_cast(&path).unwrap();
        let text = frames.last().unwrap().text_lines(true);
        assert_eq!(text[0], "MENU");
        assert_eq!(text[1], "item");
    }

    #[test]
    fn a_checkpoint_paints_over_the_screen_before_it() {
        // Each screen is a whole picture, so a shorter one must not leave the
        // tail of a longer one behind it.
        let (_dir, path) = cast_with("[0.0, \"o\", \"live\"]\n");
        let steps = [
            checkpoint(0, "long", "abcdefgh"),
            checkpoint(1, "short", "xy"),
        ];
        append_checkpoint_frames(&path, &steps, None).unwrap();

        let frames = CastVideoConverter::new().frames_from_cast(&path).unwrap();
        assert_eq!(frames.last().unwrap().text_lines(true)[0], "xy");
    }

    #[test]
    fn the_failure_screen_is_appended_too() {
        // The frame a reviewer most wants held is the one the run died on.
        let (_dir, path) = cast_with("[0.0, \"o\", \"live\"]\n");
        let steps = [
            checkpoint(0, "ok", "fine"),
            step(1, "boom", "ERROR", CaptureKind::Failure),
        ];
        assert_eq!(append_checkpoint_frames(&path, &steps, None).unwrap(), 2);

        let frames = CastVideoConverter::new().frames_from_cast(&path).unwrap();
        assert_eq!(frames.last().unwrap().text_lines(true)[0], "ERROR");
    }

    #[test]
    fn a_cast_missing_its_final_newline_is_not_spliced() {
        // A recorder killed mid-write leaves one; appending blind would fuse
        // two events into one unparseable line.
        let dir = tempfile::tempdir().unwrap();
        let cast = dir.path().join("r.cast");
        fs::write(
            &cast,
            "{\"version\":2,\"width\":10,\"height\":3}\n[0.0, \"o\", \"a\"]",
        )
        .unwrap();
        let path = cast.to_string_lossy().to_string();

        append_checkpoint_frames(&path, &[checkpoint(0, "one", "first")], None).unwrap();
        assert_eq!(events_in(&path).len(), 3);
    }

    #[test]
    fn a_hold_that_would_stall_the_timestamps_is_rejected() {
        let (_dir, path) = cast_with("[0.0, \"o\", \"a\"]\n");
        let steps = [checkpoint(0, "one", "first")];
        for bad in [0.0, -1.0, f64::NAN, f64::INFINITY] {
            assert!(
                append_checkpoint_frames(&path, &steps, Some(bad)).is_err(),
                "hold {bad} should be rejected"
            );
        }
        // Rejected before anything was written.
        assert_eq!(events_in(&path).len(), 1);
    }

    #[test]
    fn frame_size_is_derived_but_overridable() {
        let conv = CastVideoConverter::new();
        assert_eq!(conv.frame_width(), 120 * 10 + 20);
        assert_eq!(conv.frame_height(), (40.0 * 22.0) as usize + 20);
        let conv = CastVideoConverter {
            width: Some(640),
            height: Some(480),
            ..Default::default()
        };
        assert_eq!(conv.frame_width(), 640);
        assert_eq!(conv.frame_height(), 480);
    }
}
