//! TermProof: evidence-first verification for TUI and terminal applications.
//!
//! # Layout
//!
//! This crate was merged from three (`termproof-core`, `termproof-terminal`,
//! `termproof-evidence`) before any of them was published, so the shape below
//! is the only one that has ever existed on crates.io.
//!
//! - **The crate root** is what was `termproof-core`: the recipe model,
//!   config, schema, validation, the built-in [`steps`] and [`assertions`],
//!   [`planner`]/[`runner`]/[`execution`], [`store`]/[`cache`], and the
//!   `py*` compatibility shims that keep this port close to the Python
//!   oracle. It is flat rather than under a `core` module, both because it is
//!   the crate's primary surface and because a module named `core` shadows the
//!   `core` crate for every path in its scope.
//! - **[`terminal`]** is what was `termproof-terminal`: PTY, tmux and process
//!   sessions, plain and attributed screen state, asciicast recording, idle
//!   detection and the [`terminal::SessionBackend`] implementations.
//! - **[`evidence`]** is what was `termproof-evidence`: screenshot and video
//!   rendering, Markdown reports, visual baselines, diff and upload.
//! - **[`junit`]** is the JUnit XML writer. It was in `termproof-evidence` too,
//!   and [`evidence::report`] still re-exports it, but it reads a [`RunResult`]
//!   and renders nothing, so #34 moved it out to where it can be compiled
//!   without the renderers.
//!
//! The two nested modules keep their own re-exports rather than flattening
//! into the root. `error` is defined by both the root and [`terminal`], so
//! nesting is what keeps [`crate::error`] and [`terminal::error`] apart; the
//! same nesting keeps [`crate::result`] clear of [`evidence::report`], and
//! keeps the reader's sense of which layer a name comes from.
//!
//! Original module notes: models, config, schema, registries, planning,
//! orchestration and execution (RUST-004 + RUST-010 + RUST-016); PTY/process
//! ownership, terminal screen, cast recording, idle and session backends
//! (RUST-005/006 + RUST-012 + RUST-016); and the evidence pipeline.
//!
//! # Features
//!
//! All four are on by default, so a consumer that does not name features gets
//! the whole crate — the shape that has always been published.
//!
//! - **`evidence`** — the [`evidence`] module. Off, the crate does not compile
//!   `image` or `avt`.
//! - **`junit`** — the [`junit`] module and the `generate_junit` re-exports in
//!   [`evidence`]. Off, the crate does not compile `quick-junit`. It does not
//!   imply `evidence` and is not implied by it: JUnit is written from a
//!   [`RunResult`], so the two are independent in both directions (#34).
//! - **`json-schema`** — [`validation`], [`pyschema`] and the `json_schema`
//!   built-in assertion. Off, the crate does not compile `jsonschema`, and
//!   `json_schema` is absent from [`assertions::BUILTIN_TYPES`] rather than
//!   present and failing. Implies `schema`, which is where the schema it
//!   validates against comes from.
//! - **`schema`** — the [`schema`] module and the `JsonSchema` impls derived on
//!   [`Recipe`], [`config::VerifierConfig`] and the types they contain. Off,
//!   the crate does not compile `schemars`. It is the only dependency left in
//!   the public API (below), and the only one that could not be wrapped out of
//!   it, because the derives put `JsonSchema` on the published types themselves
//!   rather than in a signature; turning it off is how a consumer on a
//!   different `schemars` major stops carrying two.
//!
//! [`terminal`] has no feature of its own: the crate root is built on it, and
//! every build drives a terminal, so there is nothing to save.
//!
//! # Dependencies in the public API
//!
//! A third-party type in a public signature makes that dependency's version
//! requirement a *source-compatibility* surface, and not just a question of
//! how many copies the graph carries: two copies of a crate are two unrelated
//! types, so a consumer that names one compiles only when its copy is the copy
//! cargo handed us. Cargo resolves a requirement to the **top** of its range,
//! so the window of versions a consumer can unify with is one version wide
//! however the range is written — widening it moves the window rather than
//! enlarging it (#177).
//!
//! A *signature* is not the only door. A re-exported crate is public API too —
//! `termproof::dep::Type` names the same type as `dep::Type` and carries the
//! same requirement — and so is anything a public trait impl renders, since a
//! derived `Debug` over a private field publishes that field's formatting.
//! 0.4.0 closed all three:
//!
//! | Door | Was | Now |
//! |---|---|---|
//! | return type | [`pyregex::compile`] gave a `fancy_regex::Regex` | [`pyregex::PyRegex`], with [`pyregex::PyCaptures`] and [`pyregex::PyMatch`] so reading a match does not re-leak |
//! | return type | [`pyschema::compile`] gave a `jsonschema::Validator` | [`pyschema::PySchema`] |
//! | argument | `terminal::attributed::from_vt100` took a `vt100::Screen` | crate-internal. Nothing public accepts a caller-built `vt100` value; [`terminal::screen::TerminalScreen`] takes bytes and owns its own parser |
//! | re-export | `pub use fancy_regex`, `jsonschema`, `vt100` | removed |
//! | trait impl | `PyRegex`'s derived `Debug` rendered the engine | written out, and does not format it |
//!
//! `schemars` is the one that could not be closed: the `JsonSchema` derives sit
//! on [`Recipe`] and the types it holds, so the trait is on the published types
//! themselves rather than in a signature there is a return value to change.
//! Turning the `schema` feature off is the only way out of carrying two copies,
//! which is why that feature exists.
//!
//! **What this does and does not claim.** It claims that the *declared
//! requirement* on these crates is no longer a source-compatibility surface: a
//! consumer can depend on any version of `fancy-regex` it likes, and ours is an
//! implementation detail of the graph. It does not claim the engine is
//! interchangeable — a backtracking engine's accepted language moves between
//! releases, and `(?<=a+)b` is rejected at 0.16 and accepted at 0.19 — which is
//! why the requirement is pinned to one minor and the differential harnesses
//! are run against it rather than assumed.
//!
//! `serde`, `serde_json` and `serde_yaml` do appear in public signatures and
//! are deliberately left alone: they are 1.x, so cargo unifies every consumer
//! onto one copy and the hazard cannot arise.

// There is deliberately no `pub use fancy_regex;` / `jsonschema` / `vt100`
// here. An earlier step in this release added all three, as an escape hatch
// while those crates' types were still in our signatures: a consumer could
// name our copy and stop betting on the resolver. Wrapping the signatures
// removed the thing they were an escape from, and left them as the last way a
// dependency's version could still reach a consumer through us — a re-exported
// crate is public API, so its own breaking changes become ours. See
// "Dependencies in the public API" above (#177).

#[cfg(feature = "evidence")]
pub mod evidence;
#[cfg(feature = "junit")]
pub mod junit;
pub mod terminal;

pub mod agent;
pub mod assertions;
pub mod before_after;
pub mod build_info;
pub mod cache;
pub mod config;
pub mod error;
pub mod execution;
pub mod models;
pub mod parity;
pub mod planner;
pub mod pypath;
pub mod pyregex;
pub mod pyrepr;
#[cfg(feature = "json-schema")]
pub mod pyschema;
pub mod recipe;
pub mod result;
pub mod run_config;
pub mod runner;
#[cfg(feature = "schema")]
pub mod schema;
pub mod selection;
pub mod steps;
pub mod store;
#[cfg(feature = "json-schema")]
pub mod validation;
pub mod vocabulary;

// Re-exports: config + recipe/schema/validation (RUST-004)
pub use config::VerifierConfig;
pub use recipe::{
    Assertion, CommandSpec as RecipeCommandSpec, Recipe, RecipeMeta, Step, RECIPE_VERSION,
};
#[cfg(feature = "json-schema")]
pub use validation::{has_errors, Severity, ValidationIssue};

// Re-exports: models/result/store (RUST-010) — models is legacy, result is canonical
// Canonical Recipe is from recipe.rs (serde, plus schemars under `schema`);
// models::Recipe retained as ModelRecipe for back-compat
pub use models::Recipe as ModelRecipe;
pub use models::{
    AssertionResult as ModelAssertionResult, CommandSpec as ModelCommandSpec,
    RunResult as ModelRunResult, StepResult as ModelStepResult,
};
// Canonical RunResult/AssertionResult/StepResult from result.rs (score_from_assertions, BTreeMap artifacts)
pub use result::{AssertionResult, RunResult, StepResult};
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
pub use runner::{LoadedRecipe, Runner};

/// Canonical product name used by the CLI and diagnostics.
pub const NAME: &str = "termproof";

/// Canonical crate/product version, inherited from the workspace manifest.
pub const VERSION: &str = env!("CARGO_PKG_VERSION");

/// Render the canonical `name version` banner used by the CLI greeting.
pub fn banner() -> String {
    format!("{NAME} {VERSION} (rust workspace baseline)")
}
