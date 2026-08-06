//! TermProof terminal sessions: PTY/process ownership, terminal screen state,
//! and asciinema cast recording.
//!
//! RUST-006 delivers PTY sessions (`pty`), terminal emulation (`screen`), cast
//! recording and the activity clock (`cast`). RUST-005 (non-PTY process
//! sessions) lives in the parallel worktree `rust/m1-term-proc-005` and merges
//! after RUST-004. Both lanes depend on RUST-004's typed recipes — this crate
//! scaffolds `PtyConfig`/`ProcessConfig` against the expected `CommandSpec`
//! interface and notes the merge dependency in each module header.

/// PTY sessions (RUST-006).
pub mod pty;

/// Terminal screen emulation via `vt100` (RUST-006).
pub mod screen;

/// Asciinema cast recording and activity clock (RUST-006).
pub mod cast;

/// Re-export the primary PTY types for `SessionBackend` wiring.
pub use pty::{PtyConfig, PtyError, PtySession};

pub use cast::{replay_cast, ActivityClock, CastHeader, CastRecorder};
/// Re-export screen and cast types.
pub use screen::TerminalScreen;
