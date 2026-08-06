//! Asciinema v2 cast recorder.

use std::collections::BTreeMap;
use std::fs::File;
use std::io::{BufWriter, Write};
use std::path::PathBuf;
use std::time::{SystemTime, UNIX_EPOCH};

/// Minimal asciinema v2 recorder that writes header + `[time, "o", data]` events.
pub struct CastRecorder {
    path: PathBuf,
    cols: u16,
    rows: u16,
    command: String,
    start: std::time::Instant,
    writer: Option<BufWriter<File>>,
}

impl CastRecorder {
    /// Create a new recorder; file is created on `open`.
    pub fn new(path: PathBuf, cols: u16, rows: u16, command: String) -> Self {
        Self {
            path,
            cols,
            rows,
            command,
            start: std::time::Instant::now(),
            writer: None,
        }
    }

    /// Open the file and write the header.
    pub fn open(&mut self) -> std::io::Result<()> {
        if let Some(parent) = self.path.parent() {
            std::fs::create_dir_all(parent)?;
        }
        let file = File::create(&self.path)?;
        let mut writer = BufWriter::new(file);
        let ts = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();
        let mut header = BTreeMap::new();
        header.insert("version", serde_json::json!(2));
        header.insert("width", serde_json::json!(self.cols));
        header.insert("height", serde_json::json!(self.rows));
        header.insert("timestamp", serde_json::json!(ts));
        header.insert("command", serde_json::json!(self.command));
        let mut env = BTreeMap::new();
        env.insert(
            "TERM".to_string(),
            std::env::var("TERM").unwrap_or_else(|_| "xterm-256color".into()),
        );
        header.insert("env", serde_json::json!(env));
        writeln!(writer, "{}", serde_json::to_string(&header).unwrap())?;
        writer.flush()?;
        self.writer = Some(writer);
        Ok(())
    }

    /// Record output bytes.
    pub fn output(&mut self, data: &str) {
        self.record("o", data);
    }

    /// Record input bytes.
    pub fn input(&mut self, data: &str) {
        self.record("i", data);
    }

    fn record(&mut self, kind: &str, data: &str) {
        if data.is_empty() {
            return;
        }
        if let Some(writer) = self.writer.as_mut() {
            let elapsed = self.start.elapsed().as_secs_f64();
            let event = serde_json::json!([elapsed, kind, data]);
            let _ = writeln!(writer, "{}", serde_json::to_string(&event).unwrap());
            let _ = writer.flush();
        }
    }

    /// Close the recorder.
    pub fn close(&mut self) {
        if let Some(mut w) = self.writer.take() {
            let _ = w.flush();
        }
    }
}

impl Drop for CastRecorder {
    fn drop(&mut self) {
        self.close();
    }
}
