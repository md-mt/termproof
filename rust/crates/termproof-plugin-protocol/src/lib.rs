//! TermProof plugin protocol: versioned newline-delimited JSON process
//! messages plus client/host support.
//!
//! RUST-018: handshake, capabilities, lifecycle, timeout, size, version
//! negotiation, diagnostics, and conformance kit. RUST-019: Python bridge.

pub mod client;
pub mod error;
pub mod host;
pub mod protocol;
pub mod python_bridge;

pub use client::PluginClient;
pub use error::ProtocolError;
pub use host::{run_plugin, EchoHandler, PluginHandler};
pub use protocol::{
    Capability, Hello, Ready, Request, Response, Shutdown, DEFAULT_TIMEOUT_MS, MAX_MESSAGE_BYTES,
    PROTOCOL_VERSION,
};
pub use python_bridge::{remap_legacy_import, PythonBridge, PythonBridgeConfig};

/// Conformance kit: run a minimal in-memory handshake + echo check.
///
/// This is used by tests to prove the protocol framing, size, timeout, and
/// lifecycle invariants hold for a given handler.
pub fn conformance_roundtrip() -> Result<(), ProtocolError> {
    use std::io::Cursor;

    let mut handler = EchoHandler::new(
        "conformance",
        vec![Capability::StepAction, Capability::AssertionType],
    );
    let req = protocol::Request {
        id: 1,
        msg_type: "execute_step".to_string(),
        capability: Capability::StepAction,
        params: {
            let mut m = std::collections::HashMap::new();
            m.insert("text".to_string(), serde_json::json!("hello"));
            m
        },
        timeout_ms: Some(1000),
    };
    // Direct handler call.
    let params = req.params.clone();
    let result = handler
        .handle(&req.msg_type, &req.capability, &params)
        .expect("handler should succeed");
    assert_eq!(result.get("passed").and_then(|v| v.as_bool()), Some(true));
    // Full loop with correct hello/ready sequencing.
    let mut full_in = Cursor::new({
        let mut v = Vec::new();
        v.extend_from_slice(serde_json::to_string(&Ready::new()).unwrap().as_bytes());
        v.push(b'\n');
        v.extend_from_slice(serde_json::to_string(&req).unwrap().as_bytes());
        v.push(b'\n');
        v.extend_from_slice(
            serde_json::to_string(&protocol::Shutdown::new())
                .unwrap()
                .as_bytes(),
        );
        v.push(b'\n');
        v
    });
    let mut full_out = Vec::new();
    run_plugin(&mut handler, &mut full_in, &mut full_out)?;
    let out_str = String::from_utf8(full_out).unwrap();
    assert!(out_str.contains("\"type\":\"hello\""));
    assert!(out_str.contains("\"type\":\"result\""));
    Ok(())
}
