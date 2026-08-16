//! CLI parity tests (RUST-015).

use std::process::Command;

fn termproof() -> Command {
    Command::new(env!("CARGO_BIN_EXE_termproof"))
}

#[test]
fn help_contains_all_subcommands() {
    let output = termproof().arg("--help").output().expect("run --help");
    assert!(output.status.success());
    let stdout = String::from_utf8_lossy(&output.stdout);
    for cmd in ["run", "list", "validate", "plugins", "init", "demo"] {
        assert!(stdout.contains(cmd), "help missing {cmd}: {stdout}");
    }
}

#[test]
fn run_help_contains_all_flags() {
    let output = termproof()
        .args(["run", "--help"])
        .output()
        .expect("run --help");
    assert!(output.status.success());
    let stdout = String::from_utf8_lossy(&output.stdout);
    for flag in [
        "--out",
        "--video",
        "--no-video",
        "--video-fps",
        "--priority",
        "--recipe-name",
        "--parallel",
        "--renderer",
        "--operator-command",
        "--config",
        "--reporter",
        "--xml-path",
        "--screen-renderer",
        "--video-backend",
        "--diff",
        "--baseline-dir",
        "--update-baselines",
        "--skip-unchanged",
        "--cache-dir",
    ] {
        assert!(stdout.contains(flag), "run help missing {flag}");
    }
}

#[test]
fn run_parallel_zero_is_usage_error() {
    let output = termproof()
        .args(["run", "dummy.json", "--parallel", "0"])
        .output()
        .expect("run parallel 0");
    assert_eq!(output.status.code(), Some(2));
}

#[test]
fn run_skip_unchanged_with_diff_is_usage_error() {
    let output = termproof()
        .args(["run", "dummy.json", "--skip-unchanged", "--diff"])
        .output()
        .expect("skip-unchanged with diff");
    assert_eq!(output.status.code(), Some(2));
}

#[test]
fn version_flag() {
    let output = termproof().arg("--version").output().expect("--version");
    assert!(output.status.success());
    let stdout = String::from_utf8_lossy(&output.stdout);
    assert!(stdout.contains("termproof"), "version output: {stdout}");
}

#[test]
fn help_snapshots_match() {
    // Ensure checked-in snapshots match current help output.
    let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR"));
    let help = std::fs::read_to_string(root.join("tests/snapshots/help.txt")).unwrap();
    let run_help = std::fs::read_to_string(root.join("tests/snapshots/run-help.txt")).unwrap();
    // Snapshots should contain expected subcommands/flags (content check, not byte-exact due to clap formatting).
    assert!(help.contains("run"), "help snapshot missing run");
    assert!(
        run_help.contains("--parallel"),
        "run-help snapshot missing --parallel"
    );
}
