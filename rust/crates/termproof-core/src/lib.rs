//! TermProof core: models, config, schema, registries, planning, and
//! orchestration.

pub mod config;
pub mod error;
pub mod recipe;
pub mod schema;
pub mod validation;

// Re-exports for ergonomics.
pub use config::VerifierConfig;
pub use recipe::{Assertion, CommandSpec, Recipe, Step, RECIPE_VERSION};
pub use validation::{has_errors, Severity, ValidationIssue};

/// Canonical product name used by the CLI and diagnostics.
pub const NAME: &str = "termproof";

/// Canonical crate/product version, inherited from the workspace manifest.
pub const VERSION: &str = env!("CARGO_PKG_VERSION");

/// Render the canonical `name version` banner used by the CLI greeting.
pub fn banner() -> String {
    format!("{NAME} {VERSION} (rust workspace baseline)")
}

pub mod cache;
pub mod planner;
pub mod result;
pub mod store;

// Re-exports for convenience.
pub use result::{AssertionResult, RunResult, StepResult};
pub use store::{
    atomic_write, atomic_write_text, ensure_within_base, new_run_dir, sanitize_component,
};
