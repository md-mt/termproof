//! VT100 screen emulation and asciinema cast replay.

use std::path::Path;

/// Replay an asciinema v2 cast file, returning (screen_text, cols, rows).
///
/// Uses `vt100::Parser` to faithfully emulate terminal bytes.
/// Empty lines at the end are trimmed, trailing whitespace per line is stripped,
/// matching Python's `screen_text`.
pub fn replay_cast(cast_path: &Path) -> Result<(String, u16, u16), String> {
    let content = std::fs::read_to_string(cast_path)
        .map_err(|e| format!("failed to read cast {}: {e}", cast_path.display()))?;
    let mut lines = content.lines();
    let header_line = lines
        .next()
        .ok_or_else(|| "cast file is empty".to_string())?;
    let header: serde_json::Value =
        serde_json::from_str(header_line).map_err(|e| format!("invalid cast header: {e}"))?;
    let cols = header.get("width").and_then(|v| v.as_u64()).unwrap_or(100) as u16;
    let rows = header.get("height").and_then(|v| v.as_u64()).unwrap_or(30) as u16;

    let mut parser = vt100::Parser::new(rows, cols, 0);
    for line in lines {
        if line.trim().is_empty() {
            continue;
        }
        let event: serde_json::Value =
            serde_json::from_str(line).map_err(|e| format!("invalid cast event: {e}"))?;
        let arr = event.as_array().ok_or("cast event is not an array")?;
        if arr.len() >= 3 && arr[1].as_str() == Some("o") {
            if let Some(data) = arr[2].as_str() {
                parser.process(data.as_bytes());
            }
        }
    }
    let text = screen_text_from_parser(&parser);
    Ok((text, cols, rows))
}

fn screen_text_from_parser(parser: &vt100::Parser) -> String {
    let screen = parser.screen();
    let mut lines: Vec<String> = Vec::new();
    for row in 0..screen.size().0 {
        let mut line = String::new();
        for col in 0..screen.size().1 {
            if let Some(cell) = screen.cell(row, col) {
                line.push_str(&cell.contents());
            }
        }
        // Trim trailing whitespace like pyte's screen.display rstrip
        let trimmed = line.trim_end().to_string();
        lines.push(trimmed);
    }
    // Trim trailing empty lines
    while lines.last().is_some_and(|l| l.is_empty()) {
        lines.pop();
    }
    lines.join("\n")
}

/// Collect current screen text from a vt100 parser.
pub fn parser_screen_text(parser: &vt100::Parser) -> String {
    screen_text_from_parser(parser)
}
