//! TermProof terminal: PTY/process sessions, terminal screen, cast recording.

pub mod cast;
pub mod idle;
pub mod screen;

pub use cast::CastRecorder;
pub use idle::{wait_for_idle, IdleTracker};
pub use screen::{parser_screen_text, replay_cast};
