//! TermProof terminal: PTY + process sessions, terminal screen, cast recording, idle tracking (RUST-005/006 + RUST-012 idle semantics).

/// PTY sessions (RUST-006).
pub mod pty;

/// Terminal screen emulation via vt100 (RUST-006).
pub mod screen;

/// Asciinema cast recording and activity clock (RUST-006).
pub mod cast;

/// Idle tracking for wait_for_idle (RUST-012).
pub mod idle;

/// Non-PTY process sessions (RUST-005).
pub mod process;

pub use pty::{PtyConfig, PtyError, PtySession};
pub use cast::{CastRecorder, ActivityClock, CastHeader, replay_cast};
pub use screen::TerminalScreen;
pub use idle::{wait_for_idle, IdleTracker};
pub use process::{ProcessConfig, ProcessError, ProcessOutput, ProcessSession, ProcessWaitResult};
