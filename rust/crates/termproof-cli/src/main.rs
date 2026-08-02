//! TermProof command-line entry point.
//!
//! RUST-002 baseline: the binary prints the canonical workspace greeting and
//! exits successfully. Real command parsing, subcommands, and composition land
//! in later milestones (RUST-010 through RUST-015); this file is the smallest
//! possible runnable artifact that proves the workspace builds and links.

fn main() {
    println!("{}", termproof_core::banner());
}
