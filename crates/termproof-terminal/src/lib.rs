//! TermProof terminal: PTY/process ownership, terminal screen, cast recording, idle, and session backends (RUST-005/006 + RUST-012 + RUST-016).

// RUST-005/006 PTY and process implementations
pub mod cast;
pub mod idle;
pub mod process;
pub mod pty;
pub mod screen;

// RUST-016 public session interfaces (ExecutionContext boundary)
pub mod backend;
pub mod custom;
pub mod docker;
pub mod error;
pub mod inmemory;
pub mod session;

pub use cast::{replay_cast, ActivityClock, CastHeader, CastRecorder};
pub use idle::{wait_for_idle, IdleTracker};
pub use process::{ProcessConfig, ProcessError, ProcessOutput, ProcessSession, ProcessWaitResult};
pub use pty::{PtyConfig, PtyError, PtySession};
pub use screen::TerminalScreen;

pub use backend::SessionBackend;
pub use custom::PluginSessionBackend;
pub use docker::{DockerBackendConfig, DockerSessionBackend};
pub use error::SessionError;
pub use inmemory::InMemorySession;
pub use session::Session;
