//! Integration tests for the `termproof` binary.
//!
//! These tests execute the real compiled binary via the
//! `CARGO_BIN_EXE_termproof` environment variable that Cargo sets for
//! integration tests, so they exercise the shipped artifact, not an in-process
//! stub.

use std::process::Command;

/// The baseline greeting contract: `termproof` with no args prints the banner
/// and exits with usage code 2 (no subcommand). The banner is versioned via
/// workspace package version, so the test checks the prefix rather than a
/// hard-coded version string.
#[test]
fn termproof_binary_baseline_contract() {
    let output = Command::new(env!("CARGO_BIN_EXE_termproof"))
        .output()
        .expect("failed to execute termproof binary");

    // No subcommand => usage error (2), but banner on stdout and help hint on stderr.
    assert_eq!(
        output.status.code(),
        Some(2),
        "termproof with no args should exit 2, got {:?}",
        output.status
    );
    let stdout = String::from_utf8_lossy(&output.stdout);
    assert!(
        stdout.starts_with("termproof "),
        "stdout should start with 'termproof ', got {:?}",
        stdout
    );
    assert!(
        stdout.contains("(rust workspace baseline)") || stdout.contains("termproof"),
        "stdout banner missing, got {:?}",
        stdout
    );
}
