//! TermProof terminal sessions: PTY/process ownership, terminal screen state,
//! and asciinema cast recording.
//!
//! RUST-005 delivers non-PTY process sessions (`process` module). RUST-006
//! (PTY, screen, cast) lives in the parallel worktree `rust/m1-term-pty-006`
//! and merges after RUST-004. This crate's `process` module is the RUST-005
//! lane; PTY modules are stubbed here until the merge.

/// Non-PTY process sessions (RUST-005).
pub mod process;

/// Re-export process session types at the crate root for ergonomic `SessionBackend` wiring.
pub use process::{ProcessConfig, ProcessError, ProcessOutput, ProcessSession, ProcessWaitResult};
