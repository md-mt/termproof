//! Host helper and plugin-side utilities.

use std::collections::HashMap;
use std::io::{BufRead, Write};
use std::time::Duration;

use crate::error::ProtocolError;
use crate::protocol::{
    validate_message_size, Capability, Hello, Ready, Request, Response, PROTOCOL_VERSION,
};

/// Plugin-side host trait: implement this to handle requests.
///
/// The `Host` reads NDJSON from stdin and dispatches to this trait.
pub trait PluginHandler: Send {
    /// Handle a request, producing a result map.
    fn handle(
        &mut self,
        msg_type: &str,
        capability: &Capability,
        params: &HashMap<String, serde_json::Value>,
    ) -> Result<HashMap<String, serde_json::Value>, String>;

    /// Advertised capabilities.
    fn capabilities(&self) -> Vec<Capability>;

    /// Plugin name.
    fn name(&self) -> String;
}

/// Run a plugin handler loop over stdin/stdout (blocking).
///
/// Reads hello handshake externally: this function first writes a `Hello`,
/// then waits for `Ready`, then loops handling `Request`s until `shutdown`.
pub fn run_plugin<H, R, W>(
    handler: &mut H,
    reader: &mut R,
    writer: &mut W,
) -> Result<(), ProtocolError>
where
    H: PluginHandler,
    R: BufRead,
    W: Write,
{
    // Send hello.
    let hello = Hello::new(handler.name(), handler.capabilities());
    send_json(writer, &hello)?;
    // Wait for ready.
    let mut line = String::new();
    let n = reader
        .read_line(&mut line)
        .map_err(|e| ProtocolError::Io(format!("read ready failed: {e}")))?;
    if n == 0 {
        return Err(ProtocolError::Terminated(
            "host closed before ready".to_string(),
        ));
    }
    let ready: Ready = serde_json::from_str(line.trim())
        .map_err(|e| ProtocolError::Parse(format!("invalid ready: {e}")))?;
    if ready.protocol_version != PROTOCOL_VERSION {
        return Err(ProtocolError::VersionMismatch {
            expected: PROTOCOL_VERSION,
            got: ready.protocol_version,
        });
    }
    // Loop.
    loop {
        let mut line = String::new();
        let n = reader
            .read_line(&mut line)
            .map_err(|e| ProtocolError::Io(format!("read request failed: {e}")))?;
        if n == 0 {
            break;
        }
        let trimmed = line.trim();
        if trimmed.is_empty() {
            continue;
        }
        validate_message_size(trimmed.as_bytes())?;
        // Check for shutdown.
        if let Ok(val) = serde_json::from_str::<serde_json::Value>(trimmed) {
            if val.get("type").and_then(|v| v.as_str()) == Some("shutdown") {
                break;
            }
        }
        let req: Request = match serde_json::from_str(trimmed) {
            Ok(r) => r,
            Err(e) => {
                // Respond with error but keep looping.
                let resp = Response::error(0, format!("invalid request: {e}"));
                send_json(writer, &resp)?;
                continue;
            }
        };
        // Size already checked.
        // Timeout is advisory; handler should respect it but host enforces.
        let _timeout = req.timeout_ms.map(Duration::from_millis);
        let resp = match handler.handle(&req.msg_type, &req.capability, &req.params) {
            Ok(result) => Response::success(req.id, result),
            Err(msg) => Response::error(req.id, msg),
        };
        send_json(writer, &resp)?;
    }
    Ok(())
}

fn send_json<W: Write, T: serde::Serialize>(
    writer: &mut W,
    value: &T,
) -> Result<(), ProtocolError> {
    let line = serde_json::to_string(value)
        .map_err(|e| ProtocolError::Parse(format!("serialize failed: {e}")))?;
    validate_message_size(line.as_bytes())?;
    writer
        .write_all(line.as_bytes())
        .map_err(|e| ProtocolError::Io(format!("write failed: {e}")))?;
    writer
        .write_all(b"\n")
        .map_err(|e| ProtocolError::Io(format!("write newline failed: {e}")))?;
    writer
        .flush()
        .map_err(|e| ProtocolError::Io(format!("flush failed: {e}")))?;
    Ok(())
}

/// Simple echo handler for conformance tests.
#[derive(Debug, Default)]
pub struct EchoHandler {
    name: String,
    caps: Vec<Capability>,
}

impl EchoHandler {
    /// Create a new echo handler.
    pub fn new(name: impl Into<String>, caps: Vec<Capability>) -> Self {
        Self {
            name: name.into(),
            caps,
        }
    }
}

impl PluginHandler for EchoHandler {
    fn handle(
        &mut self,
        msg_type: &str,
        capability: &Capability,
        params: &HashMap<String, serde_json::Value>,
    ) -> Result<HashMap<String, serde_json::Value>, String> {
        if !self.caps.contains(capability) {
            return Err(format!("capability {} not supported", capability.as_str()));
        }
        let mut result = HashMap::new();
        result.insert(
            "echo_type".to_string(),
            serde_json::Value::String(msg_type.to_string()),
        );
        result.insert(
            "capability".to_string(),
            serde_json::Value::String(capability.as_str().to_string()),
        );
        // Echo params back under "params".
        result.insert("params".to_string(), serde_json::json!(params));
        result.insert("passed".to_string(), serde_json::Value::Bool(true));
        Ok(result)
    }

    fn capabilities(&self) -> Vec<Capability> {
        self.caps.clone()
    }

    fn name(&self) -> String {
        self.name.clone()
    }
}
