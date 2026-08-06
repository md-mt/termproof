//! TermProof terminal sessions: PTY/process ownership, terminal screen state,
//! and asciinema cast recording.
//!
//! The public surface for RUST-016 is the [`Session`] and [`SessionBackend`]
//! traits. Production PTY/process implementations are behind `portable-pty`
//! (future work, RUST-005/006) but the trait surface is frozen here so
//! `termproof-core` execution modes depend only on public operations.

pub mod backend;
pub mod custom;
pub mod docker;
pub mod error;
pub mod inmemory;
pub mod session;

pub use backend::SessionBackend;
pub use custom::PluginSessionBackend;
pub use docker::{DockerBackendConfig, DockerSessionBackend};
pub use error::SessionError;
pub use inmemory::InMemorySession;
pub use session::Session;
