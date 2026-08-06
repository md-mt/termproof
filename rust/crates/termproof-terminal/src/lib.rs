//! TermProof terminal sessions: PTY and process backends merged — PTY/process ownership, terminal screen state, and asciinema cast recording.
//! RUST-005 (process) and RUST-006 (PTY/screen/cast) both depend on RUST-004 typed recipes.

/// PTY sessions (RUST-006).
pub mod pty;

/// Terminal screen emulation via `vt100` (RUST-006).
pub mod screen;

/// Asciinema cast recording and activity clock (RUST-006).
pub mod cast;

/// Non-PTY process sessions (RUST-005).
pub mod process;

pub use pty::{PtyConfig, PtyError, PtySession};
pub use cast::{replay_cast, ActivityClock, CastHeader, CastRecorder};
pub use screen::TerminalScreen;
pub use process::{ProcessConfig, ProcessError, ProcessOutput, ProcessSession, ProcessWaitResult};
