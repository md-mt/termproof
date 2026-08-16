//! Plugin protocol v1: NDJSON schemas, handshake, capabilities, lifecycle,
//! timeout, size, version negotiation, diagnostics.
//!
//! Every message is a single JSON object on one line (NDJSON). Host and plugin
//! communicate over stdin/stdout; stderr is diagnostic output. The protocol is
//! versioned and bounded.

use std::collections::HashMap;

use serde::{Deserialize, Serialize};

/// Current protocol version.
pub const PROTOCOL_VERSION: u32 = 1;

/// Maximum NDJSON line size (1 MiB). Host and plugin must enforce it.
pub const MAX_MESSAGE_BYTES: usize = 1024 * 1024;

/// Default per-request timeout in milliseconds.
pub const DEFAULT_TIMEOUT_MS: u64 = 30_000;

/// All eight plugin roles.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Hash)]
pub enum Capability {
    /// Step action plugin.
    #[serde(rename = "StepAction")]
    StepAction,
    /// Assertion type plugin.
    #[serde(rename = "AssertionType")]
    AssertionType,
    /// Execution mode plugin.
    #[serde(rename = "ExecutionMode")]
    ExecutionMode,
    /// Reporter plugin.
    #[serde(rename = "Reporter")]
    Reporter,
    /// Screen renderer plugin.
    #[serde(rename = "ScreenRenderer")]
    ScreenRenderer,
    /// Video backend plugin.
    #[serde(rename = "VideoBackend")]
    VideoBackend,
    /// Agent runner plugin.
    #[serde(rename = "AgentRunner")]
    AgentRunner,
    /// Session backend plugin.
    #[serde(rename = "SessionBackend")]
    SessionBackend,
}

impl Capability {
    /// All capabilities as strings.
    pub fn all() -> Vec<Capability> {
        vec![
            Capability::StepAction,
            Capability::AssertionType,
            Capability::ExecutionMode,
            Capability::Reporter,
            Capability::ScreenRenderer,
            Capability::VideoBackend,
            Capability::AgentRunner,
            Capability::SessionBackend,
        ]
    }

    /// As string name.
    pub fn as_str(&self) -> &'static str {
        match self {
            Capability::StepAction => "StepAction",
            Capability::AssertionType => "AssertionType",
            Capability::ExecutionMode => "ExecutionMode",
            Capability::Reporter => "Reporter",
            Capability::ScreenRenderer => "ScreenRenderer",
            Capability::VideoBackend => "VideoBackend",
            Capability::AgentRunner => "AgentRunner",
            Capability::SessionBackend => "SessionBackend",
        }
    }
}

/// Hello message sent by plugin on startup to declare version + capabilities.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Hello {
    /// Message type discriminant.
    #[serde(rename = "type")]
    pub msg_type: String,
    /// Protocol version.
    pub protocol_version: u32,
    /// Advertised capabilities.
    pub capabilities: Vec<Capability>,
    /// Plugin name.
    pub name: String,
    /// Plugin version.
    #[serde(default)]
    pub version: String,
}

impl Hello {
    /// Create a new hello.
    pub fn new(name: impl Into<String>, capabilities: Vec<Capability>) -> Self {
        Self {
            msg_type: "hello".to_string(),
            protocol_version: PROTOCOL_VERSION,
            capabilities,
            name: name.into(),
            version: "0.1.0".to_string(),
        }
    }
}

/// Ready message sent by host after successful handshake.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Ready {
    /// Message type.
    #[serde(rename = "type")]
    pub msg_type: String,
    /// Protocol version echoed.
    pub protocol_version: u32,
}

impl Ready {
    /// Create ready.
    pub fn new() -> Self {
        Self {
            msg_type: "ready".to_string(),
            protocol_version: PROTOCOL_VERSION,
        }
    }
}

impl Default for Ready {
    fn default() -> Self {
        Self::new()
    }
}

/// Shutdown message.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Shutdown {
    /// Message type.
    #[serde(rename = "type")]
    pub msg_type: String,
}

impl Shutdown {
    /// Create shutdown.
    pub fn new() -> Self {
        Self {
            msg_type: "shutdown".to_string(),
        }
    }
}

impl Default for Shutdown {
    fn default() -> Self {
        Self::new()
    }
}

/// Generic request envelope (host -> plugin).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Request {
    /// Request id for correlating responses.
    pub id: u64,
    /// Method / type (e.g. "execute_step", "evaluate_assertion").
    #[serde(rename = "type")]
    pub msg_type: String,
    /// Capability being invoked.
    pub capability: Capability,
    /// Parameters (bounded extension data).
    #[serde(default)]
    pub params: HashMap<String, serde_json::Value>,
    /// Timeout ms for this request.
    #[serde(default)]
    pub timeout_ms: Option<u64>,
}

/// Generic response envelope (plugin -> host).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Response {
    /// Correlated request id.
    pub id: u64,
    /// Message type ("result" or "error").
    #[serde(rename = "type")]
    pub msg_type: String,
    /// Result payload on success.
    #[serde(default)]
    pub result: Option<HashMap<String, serde_json::Value>>,
    /// Error payload on failure.
    #[serde(default)]
    pub error: Option<String>,
    /// Diagnostics / warnings.
    #[serde(default)]
    pub diagnostics: Vec<String>,
}

impl Response {
    /// Create a success response.
    pub fn success(id: u64, result: HashMap<String, serde_json::Value>) -> Self {
        Self {
            id,
            msg_type: "result".to_string(),
            result: Some(result),
            error: None,
            diagnostics: vec![],
        }
    }

    /// Create an error response.
    pub fn error(id: u64, message: impl Into<String>) -> Self {
        Self {
            id,
            msg_type: "error".to_string(),
            result: None,
            error: Some(message.into()),
            diagnostics: vec![],
        }
    }
}

/// Validate that a serialized message does not exceed size bound.
pub fn validate_message_size(bytes: &[u8]) -> Result<(), crate::error::ProtocolError> {
    if bytes.len() > MAX_MESSAGE_BYTES {
        return Err(crate::error::ProtocolError::MessageTooLarge {
            size: bytes.len(),
            limit: MAX_MESSAGE_BYTES,
        });
    }
    Ok(())
}

/// Negotiate protocol version. Returns Ok if plugin version matches host.
pub fn negotiate_version(plugin_version: u32) -> Result<(), crate::error::ProtocolError> {
    if plugin_version != PROTOCOL_VERSION {
        return Err(crate::error::ProtocolError::VersionMismatch {
            expected: PROTOCOL_VERSION,
            got: plugin_version,
        });
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn hello_roundtrip() {
        let h = Hello::new("my-plugin", vec![Capability::StepAction]);
        let json = serde_json::to_string(&h).unwrap();
        let de: Hello = serde_json::from_str(&json).unwrap();
        assert_eq!(h, de);
        assert_eq!(de.protocol_version, PROTOCOL_VERSION);
    }

    #[test]
    fn size_validation_rejects_oversized() {
        let big = vec![b'a'; MAX_MESSAGE_BYTES + 1];
        assert!(validate_message_size(&big).is_err());
        let ok = vec![b'a'; MAX_MESSAGE_BYTES];
        assert!(validate_message_size(&ok).is_ok());
    }

    #[test]
    fn version_negotiation() {
        assert!(negotiate_version(PROTOCOL_VERSION).is_ok());
        assert!(negotiate_version(99).is_err());
    }

    #[test]
    fn all_capabilities_are_eight() {
        assert_eq!(Capability::all().len(), 8);
    }
}
