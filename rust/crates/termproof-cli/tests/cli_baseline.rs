//! Integration tests for the `termproof` binary.
//!
//! These tests execute the real compiled binary via the
//! `CARGO_BIN_EXE_termproof` environment variable that Cargo sets for
//! integration tests, so they exercise the shipped artifact, not an in-process
//! stub.

use std::process::Command;

/// The baseline greeting is the RUST-002 hello-world contract. Lock the full
/// CLI contract atomically from a single invocation of the real compiled
/// binary: exit status 0, byte-exact stdout, and empty stderr. Asserting the
/// exact bytes (not a trimmed comparison) prevents leading/trailing whitespace
/// or extra blank lines from silently passing.
#[test]
fn termproof_binary_baseline_contract() {
    let output = Command::new(env!("CARGO_BIN_EXE_termproof"))
        .output()
        .expect("failed to execute termproof binary");

    assert!(
        output.status.success(),
        "termproof should exit 0, got {:?}",
        output.status
    );
    assert_eq!(
        output.stdout, b"termproof 0.1.0 (rust workspace baseline)\n",
        "stdout must be byte-exactly the baseline greeting"
    );
    assert!(
        output.stderr.is_empty(),
        "stderr should be empty, got {:?}",
        String::from_utf8_lossy(&output.stderr)
    );
}
