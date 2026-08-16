//! NDJSON client: host side that spawns a plugin subprocess and speaks the protocol.

use std::collections::HashMap;
use std::io::{BufRead, BufReader, Write};
use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::{Duration, Instant};

use crate::error::ProtocolError;
use crate::protocol::{
    validate_message_size, Hello, Ready, Request, Response, DEFAULT_TIMEOUT_MS, PROTOCOL_VERSION,
};

/// Host-side client for a plugin subprocess.
///
/// Lifecycle: `spawn` -> `handshake` -> `request`/`response` loop -> `shutdown`.
/// Timeouts, size bounds, and version negotiation are enforced. Plugin stderr
/// is available via `take_stderr`.
pub struct PluginClient {
    child: Child,
    stdin: ChildStdin,
    stdout: BufReader<ChildStdout>,
    stderr: Option<String>,
    hello: Hello,
    next_id: AtomicU64,
    default_timeout: Duration,
}

impl PluginClient {
    /// Spawn a plugin command (argv).
    pub fn spawn(
        argv: &[String],
        default_timeout: Option<Duration>,
    ) -> Result<Self, ProtocolError> {
        if argv.is_empty() {
            return Err(ProtocolError::Io("empty plugin argv".to_string()));
        }
        let mut cmd = Command::new(&argv[0]);
        if argv.len() > 1 {
            cmd.args(&argv[1..]);
        }
        cmd.stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        let mut child = cmd
            .spawn()
            .map_err(|e| ProtocolError::Io(format!("failed to spawn plugin: {e}")))?;
        let stdin = child
            .stdin
            .take()
            .ok_or_else(|| ProtocolError::Io("failed to open plugin stdin".to_string()))?;
        let stdout = child
            .stdout
            .take()
            .ok_or_else(|| ProtocolError::Io("failed to open plugin stdout".to_string()))?;
        let stdout = BufReader::new(stdout);
        Ok(Self {
            child,
            stdin,
            stdout,
            stderr: None,
            hello: Hello::new("unknown", vec![]),
            next_id: AtomicU64::new(1),
            default_timeout: default_timeout.unwrap_or(Duration::from_millis(DEFAULT_TIMEOUT_MS)),
        })
    }

    /// Perform the handshake: read `hello`, validate version, send `ready`.
    pub fn handshake(&mut self) -> Result<Hello, ProtocolError> {
        let line = self.read_line_with_timeout(self.default_timeout)?;
        validate_message_size(line.as_bytes())?;
        let hello: Hello = serde_json::from_str(&line)
            .map_err(|e| ProtocolError::Parse(format!("invalid hello: {e}")))?;
        if hello.msg_type != "hello" {
            return Err(ProtocolError::Lifecycle(format!(
                "expected hello, got {}",
                hello.msg_type
            )));
        }
        if hello.protocol_version != PROTOCOL_VERSION {
            return Err(ProtocolError::VersionMismatch {
                expected: PROTOCOL_VERSION,
                got: hello.protocol_version,
            });
        }
        self.hello = hello.clone();
        let ready = Ready::new();
        self.send_json(&ready)?;
        Ok(hello)
    }

    /// Return the hello received during handshake.
    pub fn hello(&self) -> &Hello {
        &self.hello
    }

    /// Send a request and wait for a response.
    pub fn call(
        &mut self,
        msg_type: &str,
        capability: crate::protocol::Capability,
        params: HashMap<String, serde_json::Value>,
        timeout: Option<Duration>,
    ) -> Result<Response, ProtocolError> {
        let id = self.next_id.fetch_add(1, Ordering::SeqCst);
        let req = Request {
            id,
            msg_type: msg_type.to_string(),
            capability,
            params,
            timeout_ms: timeout.map(|d| d.as_millis() as u64),
        };
        self.send_json(&req)?;
        let resp_line = self.read_line_with_timeout(timeout.unwrap_or(self.default_timeout))?;
        validate_message_size(resp_line.as_bytes())?;
        let resp: Response = serde_json::from_str(&resp_line)
            .map_err(|e| ProtocolError::Parse(format!("invalid response: {e}")))?;
        if resp.id != id {
            return Err(ProtocolError::Lifecycle(format!(
                "response id mismatch: expected {id}, got {}",
                resp.id
            )));
        }
        if resp.msg_type == "error" {
            let msg = resp
                .error
                .clone()
                .unwrap_or_else(|| "unknown plugin error".to_string());
            return Err(ProtocolError::Plugin(msg));
        }
        Ok(resp)
    }

    /// Send a shutdown message and wait for child exit.
    pub fn shutdown(&mut self) -> Result<(), ProtocolError> {
        let shutdown = crate::protocol::Shutdown::new();
        let _ = self.send_json(&shutdown);
        let _ = self.stdin.flush();
        let start = Instant::now();
        let timeout = Duration::from_secs(5);
        loop {
            match self.child.try_wait() {
                Ok(Some(_status)) => {
                    return Ok(());
                }
                Ok(None) => {
                    if start.elapsed() > timeout {
                        let _ = self.child.kill();
                        return Err(ProtocolError::Timeout(timeout.as_millis() as u64));
                    }
                    std::thread::sleep(Duration::from_millis(50));
                }
                Err(e) => return Err(ProtocolError::Io(format!("wait failed: {e}"))),
            }
        }
    }

    /// Take accumulated stderr (if any collected elsewhere).
    pub fn take_stderr(&mut self) -> Option<String> {
        self.stderr.take()
    }

    /// Check that the given capability is advertised.
    pub fn require_capability(
        &self,
        capability: &crate::protocol::Capability,
    ) -> Result<(), ProtocolError> {
        if self.hello.capabilities.contains(capability) {
            Ok(())
        } else {
            Err(ProtocolError::Capability(format!(
                "{} not in {:?}",
                capability.as_str(),
                self.hello.capabilities
            )))
        }
    }

    fn send_json<T: serde::Serialize>(&mut self, value: &T) -> Result<(), ProtocolError> {
        let line = serde_json::to_string(value)
            .map_err(|e| ProtocolError::Parse(format!("serialize failed: {e}")))?;
        validate_message_size(line.as_bytes())?;
        self.stdin
            .write_all(line.as_bytes())
            .map_err(|e| ProtocolError::Io(format!("write failed: {e}")))?;
        self.stdin
            .write_all(b"\n")
            .map_err(|e| ProtocolError::Io(format!("write newline failed: {e}")))?;
        self.stdin
            .flush()
            .map_err(|e| ProtocolError::Io(format!("flush failed: {e}")))?;
        Ok(())
    }

    fn read_line_with_timeout(&mut self, timeout: Duration) -> Result<String, ProtocolError> {
        let start = Instant::now();
        let mut line = String::new();
        let n = self
            .stdout
            .read_line(&mut line)
            .map_err(|e| ProtocolError::Io(format!("read failed: {e}")))?;
        if n == 0 {
            return Err(ProtocolError::Terminated(
                "plugin closed stdout".to_string(),
            ));
        }
        if start.elapsed() > timeout {
            return Err(ProtocolError::Timeout(timeout.as_millis() as u64));
        }
        Ok(line.trim_end_matches(&['\r', '\n'][..]).to_string())
    }
}

impl Drop for PluginClient {
    fn drop(&mut self) {
        let _ = self.child.kill();
    }
}
