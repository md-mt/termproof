//! TermProof core: models, config, schema, registries, planning, orchestration, and execution (RUST-004 + RUST-010 + RUST-016).

pub mod agent;
pub mod cache;
pub mod config;
pub mod error;
pub mod execution;
pub mod models;
pub mod planner;
pub mod recipe;
pub mod result;
pub mod schema;
pub mod store;
pub mod validation;

// Re-exports: config + recipe/schema/validation (RUST-004)
pub use config::VerifierConfig;
pub use recipe::{Assertion, CommandSpec as RecipeCommandSpec, Recipe, Step, RECIPE_VERSION};
pub use validation::{has_errors, Severity, ValidationIssue};

// Re-exports: models/result/store (RUST-010)
pub use models::{
    CommandSpec as ModelCommandSpec, RunResult as ModelRunResult, StepResult as ModelStepResult,
};
// Recipe from recipe.rs is canonical (serde+schemars); models::Recipe is legacy alias
pub use models::Recipe as ModelRecipe;
// Canonical RunResult is from result.rs (has score_from_assertions, artifacts as BTreeMap)
pub use result::{AssertionResult, RunResult, StepResult};
// Keep Model aliases for compatibility
pub use models::AssertionResult as ModelAssertionResult;
pub use store::{
    atomic_write, atomic_write_text, ensure_within_base, new_run_dir, sanitize_component,
};

// Re-exports: execution/agent (RUST-016/017)
pub use agent::{
    build_agent_prompt, parse_agent_output, ParsedAgentOutput, MAX_AGENT_OUTPUT_BYTES,
    MAX_PROMPT_CONTEXT_CHARS,
};
pub use error::CoreError;
pub use execution::{
    AgentDrivenMode, ExecutionContext, ExecutionError, ExecutionMode, ExecutionResult,
    ScriptedProcessMode, ScriptedPtyMode,
};

/// Canonical product name used by the CLI and diagnostics.
pub const NAME: &str = "termproof";

/// Canonical crate/product version, inherited from the workspace manifest.
pub const VERSION: &str = env!("CARGO_PKG_VERSION");

/// Render the canonical `name version` banner used by the CLI greeting.
pub fn banner() -> String {
    format!("{NAME} {VERSION} (rust workspace baseline)")
}
