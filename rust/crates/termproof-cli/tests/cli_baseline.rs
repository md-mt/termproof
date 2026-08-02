//! Integration tests for the `termproof` binary.
//!
//! These tests execute the real compiled binary via the
//! `CARGO_BIN_EXE_termproof` environment variable that Cargo sets for
//! integration tests, so they exercise the shipped artifact, not an in-process
//! stub.

use std::process::Command;

/// The baseline greeting is the RUST-002 hello-world contract. The binary must
/// print it on stdout and exit successfully.
#[test]
fn termproof_binary_prints_baseline_greeting() {
    let output = Command::new(env!("CARGO_BIN_EXE_termproof"))
        .output()
        .expect("failed to execute termproof binary");

    assert!(
        output.status.success(),
        "termproof should exit 0, got {:?}",
        output.status
    );

    let stdout = String::from_utf8_lossy(&output.stdout);
    assert_eq!(
        stdout.trim(),
        "termproof 0.1.0 (rust workspace baseline)",
        "stdout must be exactly the baseline greeting"
    );
}

/// The binary must not write anything to stderr for a plain invocation.
#[test]
fn termproof_binary_is_quiet_on_stderr() {
    let output = Command::new(env!("CARGO_BIN_EXE_termproof"))
        .output()
        .expect("failed to execute termproof binary");

    let stderr = String::from_utf8_lossy(&output.stderr);
    assert!(stderr.is_empty(), "stderr should be empty, got: {stderr:?}");
}
