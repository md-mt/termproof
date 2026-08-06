//! Core error types.

use thiserror::Error;

/// Errors produced by core operations.
#[derive(Debug, Error)]
pub enum CoreError {
    /// Recipe validation failed.
    #[error("recipe error: {0}")]
    Recipe(String),

    /// Execution failed.
    #[error("execution error: {0}")]
    Execution(String),

    /// Plugin error.
    #[error("plugin error: {0}")]
    Plugin(String),

    /// Session error.
    #[error("session error: {0}")]
    Session(String),

    /// Configuration error.
    #[error("config error: {0}")]
    Config(String),
}
