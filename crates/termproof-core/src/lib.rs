//! TermProof core: models, config, schema, registries, planning, and
//! orchestration.
//!
//! This crate is the shared foundation for the Rust reimplementation. During
//! the RUST-002 baseline it only carries the canonical identity constants so
//! downstream crates (starting with `termproof-cli`) have a single source of
//! truth for the product name and version.

pub mod config;
pub mod error;
pub mod execution;
pub mod models;

pub use config::{DockerBackendConfig, GlobalDefaults};
pub use error::CoreError;
pub use execution::{
    AgentDrivenMode, ExecutionContext, ExecutionError, ExecutionMode, ExecutionResult,
    ScriptedProcessMode, ScriptedPtyMode,
};
pub use models::{AssertionResult, CommandSpec, Recipe, RunResult, StepResult};

/// Canonical product name used by the CLI and diagnostics.
pub const NAME: &str = "termproof";

/// Canonical crate/product version, inherited from the workspace manifest.
pub const VERSION: &str = env!("CARGO_PKG_VERSION");

/// Render the canonical `name version` banner used by the CLI greeting.
pub fn banner() -> String {
    format!("{NAME} {VERSION} (rust workspace baseline)")
}
