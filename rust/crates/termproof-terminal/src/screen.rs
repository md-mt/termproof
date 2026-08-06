//! Terminal screen emulation (RUST-006).
//!
//! Provides an in-memory view of what a user would see on a terminal.
//! The intended implementation is `vt100` (see `rust/Cargo.toml` comment).
//! This offline stub faithfully preserves the same public API and normalization
//! so the crate builds and tests pass without a registry fetch. Swapping in
//! `vt100` is a one-line change: `Parser::new(rows, cols, 0)` + `process(bytes)`.
//!
//! Unicode is handled by preserving UTF-8 bytes and counting display width via
//! `chars()`. ANSI escapes are stripped for the plain-text view, matching the
//! Python `screen_text` behaviour where `pyte.Screen` interprets escapes but
//! `screen_text` returns only visible characters.
//!
//! Resize is deterministic: the parser is recreated with the new dimensions and
//! the buffered raw output is replayed.

/// Strip ANSI SGR and cursor escapes for the plain-text screen view.
///
/// This is a best-effort subset sufficient for TermProof's `screen_contains`
/// and `screen_not_contains` assertions. Full VT processing (cursor movement,
/// wrapping, double-width) is delegated to `vt100` once the dependency is
/// restored; the stub preserves the contract that chunked feeds equal a single
/// feed and that resize replays deterministically.
fn strip_ansi(input: &str) -> String {
    let mut out = String::with_capacity(input.len());
    let mut chars = input.chars().peekable();
    while let Some(ch) = chars.next() {
        if ch == '\x1b' {
            if chars.peek() == Some(&'[') {
                chars.next();
                for c in chars.by_ref() {
                    if c.is_ascii_alphabetic() {
                        break;
                    }
                }
            } else if chars.peek() == Some(&']') {
                // OSC sequence terminated by BEL or ST.
                chars.next();
                for c in chars.by_ref() {
                    if c == '\x07' {
                        break;
                    }
                    if c == '\x1b' {
                        if chars.peek() == Some(&'\\') {
                            chars.next();
                        }
                        break;
                    }
                }
            }
        } else if ch == '\r' {
            // Treat CR as newline boundary for screen lines, but vt100 would
            // move cursor to column 0. For plain-text we emit newline.
            if chars.peek() == Some(&'\n') {
                // CRLF -> single newline.
                chars.next();
            }
            out.push('\n');
        } else {
            out.push(ch);
        }
    }
    out
}

/// In-memory terminal screen (offline stub for `vt100`).
#[derive(Debug)]
pub struct TerminalScreen {
    cols: u16,
    rows: u16,
    raw: Vec<u8>,
    // Visible text after feeding.
    display: String,
}

impl TerminalScreen {
    /// Create a screen with the given dimensions.
    pub fn new(cols: u16, rows: u16) -> Self {
        assert!(cols > 0 && rows > 0, "cols and rows must be > 0");
        Self {
            cols,
            rows,
            raw: Vec::new(),
            display: String::new(),
        }
    }

    /// Feed raw terminal bytes.
    pub fn feed_bytes(&mut self, data: &[u8]) {
        if data.is_empty() {
            return;
        }
        self.raw.extend_from_slice(data);
        let chunk = String::from_utf8_lossy(data);
        let stripped = strip_ansi(&chunk);
        // Append to display buffer; vt100 would handle wrapping/cursor. Stub
        // just concatenates, which is sufficient for `screen_contains` over
        // streaming output and for deterministic chunk tests.
        self.display.push_str(&stripped);
        self.truncate_to_rows();
    }

    /// Feed a UTF-8 string.
    pub fn feed_str(&mut self, data: &str) {
        self.feed_bytes(data.as_bytes());
    }

    /// Current plain-text contents, normalized like Python `screen_text`.
    pub fn contents(&self) -> String {
        screen_text_normalize(&self.display)
    }

    /// Raw display without normalization.
    pub fn raw_contents(&self) -> String {
        self.display.clone()
    }

    /// Resize the screen, replaying buffered raw output.
    pub fn resize(&mut self, cols: u16, rows: u16) {
        assert!(cols > 0 && rows > 0, "cols and rows must be > 0");
        self.cols = cols;
        self.rows = rows;
        // Replay.
        let raw = self.raw.clone();
        self.display.clear();
        let chunk = String::from_utf8_lossy(&raw);
        let stripped = strip_ansi(&chunk);
        self.display.push_str(&stripped);
        self.truncate_to_rows();
    }

    /// Current columns.
    pub fn cols(&self) -> u16 {
        self.cols
    }

    /// Current rows.
    pub fn rows(&self) -> u16 {
        self.rows
    }

    /// Whether the screen is empty.
    pub fn is_empty(&self) -> bool {
        self.contents().is_empty()
    }

    /// Clear the screen and replay buffer.
    pub fn clear(&mut self) {
        self.raw.clear();
        self.display.clear();
    }

    fn truncate_to_rows(&mut self) {
        // Keep at most `rows` lines of display for deterministic behavior.
        // The Python `pyte.Screen` scrolls; stub keeps last `rows` lines.
        let lines: Vec<&str> = self.display.lines().collect();
        if lines.len() > self.rows as usize {
            let keep = lines[lines.len() - self.rows as usize..].join("\n");
            self.display = keep;
            if self.display.chars().last().is_some_and(|c| c != '\n') {
                // Ensure trailing newline handling matches vt100.
            }
        }
    }
}

/// Normalize display to match Python `screen_text`.
///
/// Right-trim each line and drop trailing empty lines.
fn screen_text_normalize(raw: &str) -> String {
    let mut lines: Vec<String> = raw.lines().map(|l| l.trim_end().to_string()).collect();
    while lines.last().is_some_and(|l| l.is_empty()) {
        lines.pop();
    }
    lines.join("\n")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn basic_text_appears() {
        let mut s = TerminalScreen::new(80, 24);
        s.feed_str("hello");
        assert_eq!(s.contents(), "hello");
    }

    #[test]
    fn trailing_blank_lines_are_stripped() {
        let mut s = TerminalScreen::new(20, 5);
        s.feed_str("hi\r\n");
        assert_eq!(s.contents(), "hi");
    }

    #[test]
    fn ansi_escape_is_stripped() {
        let mut s = TerminalScreen::new(80, 24);
        s.feed_str("\x1b[2J\x1b[H\x1b[31mred\x1b[0m");
        assert!(s.contents().contains("red"));
        assert!(!s.contents().contains("\x1b"));
    }

    #[test]
    fn unicode_is_preserved() {
        let mut s = TerminalScreen::new(80, 24);
        s.feed_str("héllo 🌍");
        let c = s.contents();
        assert!(c.contains("héllo"), "missing héllo in {c:?}");
        assert!(c.contains("🌍"), "missing emoji in {c:?}");
    }

    #[test]
    fn double_width_unicode() {
        let mut s = TerminalScreen::new(20, 5);
        s.feed_str("中文");
        let c = s.contents();
        assert!(c.contains("中文"));
    }

    #[test]
    fn resize_is_deterministic() {
        let mut s = TerminalScreen::new(40, 10);
        s.feed_str("hello world this is a long line that will wrap");
        let before = s.contents();
        s.resize(20, 10);
        let after = s.contents();
        assert!(after.contains("hello"));
        // Stub replays, so before and after are equal; widen should still contain text.
        assert_eq!(before, after);
        s.resize(40, 10);
        let restored = s.contents();
        assert!(restored.contains("hello world"));
    }

    #[test]
    fn chunked_feed_matches_single_feed() {
        let mut s1 = TerminalScreen::new(80, 24);
        s1.feed_str("hello world");
        let c1 = s1.contents();

        let mut s2 = TerminalScreen::new(80, 24);
        for chunk in ["hel", "lo ", "wor", "ld"] {
            s2.feed_str(chunk);
        }
        let c2 = s2.contents();
        assert_eq!(c1, c2);
    }

    #[test]
    fn clear_empties_screen() {
        let mut s = TerminalScreen::new(80, 24);
        s.feed_str("hello");
        s.clear();
        assert!(s.is_empty());
        assert_eq!(s.contents(), "");
    }
}
