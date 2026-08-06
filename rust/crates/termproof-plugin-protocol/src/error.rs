//! Protocol error types.

use thiserror::Error;

/// Errors from the plugin protocol.
#[derive(Debug, Error)]
pub enum ProtocolError {
    /// Version mismatch between host and plugin.
    #[error("protocol version mismatch: expected {expected}, got {got}")]
    VersionMismatch {
        /// Expected version.
        expected: u32,
        /// Got version.
        got: u32,
    },

    /// Message exceeds maximum allowed size.
    #[error("message too large: {size} bytes exceeds limit {limit}")]
    MessageTooLarge {
        /// Actual size.
        size: usize,
        /// Size limit.
        limit: usize,
    },

    /// Message could not be parsed.
    #[error("parse error: {0}")]
    Parse(String),

    /// Plugin reported an error.
    #[error("plugin error: {0}")]
    Plugin(String),

    /// Host IO error.
    #[error("io error: {0}")]
    Io(String),

    /// Request timed out.
    #[error("timeout after {0}ms")]
    Timeout(u64),

    /// Plugin process exited unexpectedly.
    #[error("plugin terminated: {0}")]
    Terminated(String),

    /// Capability not advertised by plugin.
    #[error("capability not supported: {0}")]
    Capability(String),

    /// Lifecycle violation (e.g. message before handshake).
    #[error("lifecycle error: {0}")]
    Lifecycle(String),

    /// Cancellation requested.
    #[error("cancelled")]
    Cancelled,
}
