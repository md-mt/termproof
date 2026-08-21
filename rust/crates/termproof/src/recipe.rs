//! Typed recipe models with flattened extension maps and legacy loading.
//!
//! The models mirror `termproof/models.py` but preserve unknown fields via
//! flattened `extension` maps rather than discarding them. Additional
//! properties are permitted at the recipe, command, step, and assertion level
//! (see JSON Schema `additionalProperties: true`).
//!
//! # A recipe is linear, on purpose
//!
//! [`Recipe::steps`] runs in order, once, the same way every time. There is no
//! `when` predicate, no retry count, and no second, imperative recipe model
//! beside this one — a scenario that polls until something renders and acts
//! only if it did, dismisses an overlay that may or may not appear, or retries
//! a racy step, is not expressible here and is not meant to be.
//!
//! That is a decision rather than a gap, and the reasoning turns on the very
//! tolerance described above: an unknown step key lands in [`Step::extra`] and
//! is ignored by both runtimes, so a `when` this crate honoured would be one
//! the Python oracle silently skipped, and a single recipe file would mean two
//! different things. Consumers with a branching scenario keep their own runner,
//! drive a session through [`crate::terminal::SessionDriver`], and build a
//! [`crate::result::RunResult`] themselves — which keeps [`crate::parity`],
//! [`crate::before_after`] and the reporters available to them. See
//! `docs/conditional-recipes.md` for the three scenarios this was weighed
//! against and the conditions that would reopen it.

use std::collections::HashMap;
use std::path::Path;

#[cfg(feature = "schema")]
use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

/// The current canonical recipe version.
pub const RECIPE_VERSION: u32 = 1;

fn default_recipe_version() -> u32 {
    RECIPE_VERSION
}

fn default_description() -> String {
    String::new()
}

fn default_intent() -> String {
    String::new()
}

fn default_priority() -> String {
    "P2".to_string()
}

fn default_execution() -> String {
    "scripted".to_string()
}

fn default_determinism() -> String {
    "deterministic".to_string()
}

fn default_timeout_seconds() -> f64 {
    30.0
}

fn default_cols() -> u32 {
    100
}

fn default_rows() -> u32 {
    30
}

fn default_expect_exit_code() -> Option<i32> {
    Some(0)
}

fn default_pty() -> bool {
    true
}

/// Human-friendly default for `renderers`: `{"default": []}`.
fn default_renderers() -> HashMap<String, Vec<String>> {
    let mut m = HashMap::new();
    m.insert("default".to_string(), Vec::new());
    m
}

/// Command specification for a recipe.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[cfg_attr(feature = "schema", derive(JsonSchema))]
pub struct CommandSpec {
    /// Target command and arguments; at least one entry required.
    pub argv: Vec<String>,

    /// Working directory for the command; `None` means inherited.
    #[serde(default)]
    #[cfg_attr(feature = "schema", schemars(with = "Option<String>"))]
    pub cwd: Option<String>,

    /// Environment variables for the command.
    #[serde(default)]
    pub env: HashMap<String, String>,

    /// Whether to allocate a PTY for the command.
    #[serde(default = "default_pty")]
    pub pty: bool,

    /// Extension fields not covered by the typed schema (`additionalProperties: true`).
    #[serde(default, flatten)]
    #[cfg_attr(feature = "schema", schemars(flatten))]
    pub extension: HashMap<String, serde_json::Value>,
}

/// A single step in a recipe.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[cfg_attr(feature = "schema", derive(JsonSchema))]
pub struct Step {
    /// Action name, e.g. `wait_for_text`, `send_line`.
    pub action: String,

    /// Optional human-readable step name.
    #[serde(default)]
    #[cfg_attr(feature = "schema", schemars(with = "Option<String>"))]
    pub name: Option<String>,

    /// Per-step timeout in seconds, if overridden.
    #[serde(default)]
    #[cfg_attr(feature = "schema", schemars(with = "Option<f64>"))]
    pub timeout_seconds: Option<f64>,

    /// Any additional step fields (e.g. `text`, `key`, `pattern`).
    #[serde(default, flatten)]
    #[cfg_attr(feature = "schema", schemars(flatten))]
    pub extra: HashMap<String, serde_json::Value>,
}

/// A single assertion in a recipe.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[cfg_attr(feature = "schema", derive(JsonSchema))]
pub struct Assertion {
    /// Assertion type, e.g. `output_contains`.
    #[serde(rename = "type")]
    pub kind: String,

    /// Optional human-readable assertion name.
    #[serde(default)]
    #[cfg_attr(feature = "schema", schemars(with = "Option<String>"))]
    pub name: Option<String>,

    /// Any additional assertion fields (e.g. `value`, `path`, `schema`).
    #[serde(default, flatten)]
    #[cfg_attr(feature = "schema", schemars(flatten))]
    pub extra: HashMap<String, serde_json::Value>,
}

/// What a recipe says about itself, independent of how it is driven.
///
/// These seven fields answer "which scenario is this, how much does it matter,
/// and which sources does it cover" — questions that have the same answer
/// whether the scenario is a declarative [`Recipe`] or a consumer's own
/// imperative runner. Only the *driving* half of a recipe is declarative, and
/// only that half is out of reach for a suite that branches on what the screen
/// shows; the description is not, and used to be reachable only by constructing
/// a [`Recipe`], which such a suite cannot do.
///
/// [`Recipe`] holds one of these and flattens it, so a recipe file is unchanged
/// on disk: `name` and `ci_paths` are still top-level keys. An imperative
/// caller constructs one directly and gets [`crate::selection::Selectable`] for
/// free, because that trait is implemented here rather than only on [`Recipe`].
///
/// Product-specific knobs do not belong here. [`Recipe::extension`] is the
/// sanctioned home for those, and a consumer's own struct is the other.
///
/// ```
/// use termproof::recipe::RecipeMeta;
/// use termproof::selection::{select_names, SelectionConfig};
///
/// let recipes = vec![
///     RecipeMeta::new("smoke"),
///     RecipeMeta {
///         ci_paths: vec!["src/payments/**".to_string()],
///         ..RecipeMeta::new("payments")
///     },
/// ];
/// let config = SelectionConfig {
///     harness_root: "verify/",
///     repo_marker: "/repo/",
///     smoke: &["smoke"],
/// };
/// let changed = vec!["src/payments/api.rs".to_string()];
/// assert_eq!(select_names(&recipes, &changed, &config), ["smoke", "payments"]);
/// ```
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[cfg_attr(feature = "schema", derive(JsonSchema))]
pub struct RecipeMeta {
    /// Human-readable recipe identifier.
    pub name: String,

    /// Human-readable description.
    #[serde(default = "default_description")]
    pub description: String,

    /// Intent description.
    #[serde(default = "default_intent")]
    pub intent: String,

    /// Priority label, e.g. `P2`.
    #[serde(default = "default_priority")]
    pub priority: String,

    /// Execution mode name, e.g. `scripted` or `agent-driven`.
    #[serde(default = "default_execution")]
    pub execution: String,

    /// Determinism label.
    #[serde(default = "default_determinism")]
    pub determinism: String,

    /// CI path filters.
    #[serde(default)]
    pub ci_paths: Vec<String>,
}

impl RecipeMeta {
    /// Metadata for `name`, with every other field at the value a recipe file
    /// that omits it would get.
    ///
    /// The defaults come from the same functions the `serde` attributes use, so
    /// this and a parsed recipe cannot drift.
    pub fn new(name: impl Into<String>) -> Self {
        Self {
            name: name.into(),
            ..Self::default()
        }
    }
}

impl Default for RecipeMeta {
    /// The defaults a recipe file gets for the fields it omits — except `name`,
    /// which has no default in the schema and is empty here.
    fn default() -> Self {
        Self {
            name: String::new(),
            description: default_description(),
            intent: default_intent(),
            priority: default_priority(),
            execution: default_execution(),
            determinism: default_determinism(),
            ci_paths: Vec::new(),
        }
    }
}

/// Typed recipe model.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[cfg_attr(feature = "schema", derive(JsonSchema))]
pub struct Recipe {
    /// Recipe format version; defaults to `1` for legacy recipes.
    #[serde(default = "default_recipe_version")]
    #[cfg_attr(feature = "schema", schemars(range(min = 1, max = 1)))]
    pub recipe_version: u32,

    /// What the recipe says about itself: name, description, intent, priority,
    /// execution, determinism and `ci_paths`.
    ///
    /// Flattened, so these stay top-level keys in a recipe file and in the
    /// schema. The nesting is a Rust-side split only.
    ///
    /// This is an owned field, so `recipe.meta.ci_paths.push(..)` mutates the
    /// recipe. Python's `Recipe.meta` is a property returning a copy, and the
    /// same expression there is a no-op — the one place the two
    /// implementations differ in semantics rather than only in spelling.
    #[serde(flatten)]
    #[cfg_attr(feature = "schema", schemars(flatten))]
    pub meta: RecipeMeta,

    /// Checks list (human-readable expectations).
    #[serde(default)]
    pub checks: Vec<String>,

    /// Operator configuration (free-form).
    #[serde(default)]
    pub operator: HashMap<String, serde_json::Value>,

    /// Renderer table, e.g. `{"default": []}`.
    #[serde(default = "default_renderers")]
    pub renderers: HashMap<String, Vec<String>>,

    /// Command to execute.
    pub command: CommandSpec,

    /// Ordered steps to drive the session.
    #[serde(default)]
    pub steps: Vec<Step>,

    /// Assertions to evaluate after execution.
    #[serde(default)]
    pub assertions: Vec<Assertion>,

    /// Expected exit code; `None` means no expectation.
    #[serde(default = "default_expect_exit_code")]
    #[cfg_attr(feature = "schema", schemars(with = "Option<i32>"))]
    pub expect_exit_code: Option<i32>,

    /// Overall recipe timeout in seconds.
    #[serde(default = "default_timeout_seconds")]
    pub timeout_seconds: f64,

    /// Terminal columns.
    #[serde(default = "default_cols")]
    pub cols: u32,

    /// Terminal rows.
    #[serde(default = "default_rows")]
    pub rows: u32,

    /// Source path for diagnostics; not serialized.
    #[serde(skip, default)]
    #[cfg_attr(feature = "schema", schemars(skip))]
    pub source_path: Option<String>,

    /// Extension fields not covered by the typed schema.
    #[serde(default, flatten)]
    #[cfg_attr(feature = "schema", schemars(flatten))]
    pub extension: HashMap<String, serde_json::Value>,
}

impl Recipe {
    /// Load a recipe from a file path, supporting both JSON and YAML inputs.
    ///
    /// JSON is tried first (preserving number fidelity for the legacy
    /// integral-float check); on failure the content is parsed as YAML. This
    /// matches the spec requirement that both formats are accepted and keeps
    /// backward compatibility with the Python loader which only read JSON.
    pub fn from_file(path: &Path) -> Result<Self, crate::error::CoreError> {
        let content = std::fs::read_to_string(path).map_err(|e| crate::error::CoreError::Io {
            path: path.display().to_string(),
            source: e,
        })?;
        Self::from_str(&content, Some(path))
    }

    /// Parse a recipe from a string, optionally attaching a source path.
    ///
    /// JSON and YAML are both accepted (JSON first, YAML fallback).
    pub fn from_str(content: &str, source: Option<&Path>) -> Result<Self, crate::error::CoreError> {
        // Attempt JSON first for fidelity; fall back to YAML.
        let mut recipe: Self = serde_json::from_str(content)
            .or_else(|_| serde_yaml::from_str(content))
            .map_err(|e| crate::error::CoreError::Parse {
                path: source
                    .map(|p| p.display().to_string())
                    .unwrap_or_else(|| "<string>".to_string()),
                message: e.to_string(),
            })?;
        if let Some(p) = source {
            recipe.source_path = Some(p.display().to_string());
        }
        // Normalize: if the raw input omitted recipe_version, the deserialized
        // value will be the default 1. The caller can detect legacy via
        // `was_recipe_version_missing` below if needed for warnings.
        Ok(recipe)
    }

    /// Whether the raw value for `recipe_version` was missing (legacy recipe).
    ///
    /// This helper re-parses the raw JSON/YAML to check presence, because
    /// deserialization defaults to 1. It is used by validation to emit the
    /// legacy warning without failing the recipe.
    pub fn was_recipe_version_missing(raw: &serde_json::Value) -> bool {
        !raw.as_object()
            .map(|o| o.contains_key("recipe_version"))
            .unwrap_or(false)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn every_public_field_of_the_recipe_is_accounted_for() {
        // Half of what the waived `struct_pub_field_missing` lint bought.
        //
        // Moving seven fields into `RecipeMeta` is what the lint fires on, and
        // `Cargo.toml` turns it off on the captain's decision that 0.4.x
        // stands. Off, it is off for every struct in the crate, which is the
        // only granularity cargo-semver-checks offers — so this recovers the
        // cover for the struct the waiver was granted for.
        //
        // The assertions are incidental. **The exhaustive literal is the
        // test**: a field leaving `Recipe`, being renamed, or a new one
        // arriving all stop this compiling. That second case is why this one
        // test serves both waived lints for this struct — `Recipe.meta` is the
        // `constructible_struct_adds_field` finding, and it is named here.
        let recipe = Recipe {
            recipe_version: RECIPE_VERSION,
            meta: RecipeMeta::new("x"),
            checks: Vec::new(),
            operator: HashMap::new(),
            renderers: default_renderers(),
            command: CommandSpec {
                argv: vec!["true".to_string()],
                cwd: None,
                env: HashMap::new(),
                pty: true,
                extension: HashMap::new(),
            },
            steps: Vec::new(),
            assertions: Vec::new(),
            expect_exit_code: Some(0),
            timeout_seconds: 30.0,
            cols: 100,
            rows: 30,
            source_path: None,
            extension: HashMap::new(),
        };
        assert_eq!(recipe.meta.name, "x");
        assert_eq!(recipe.command.argv, ["true"]);
        assert!(recipe.source_path.is_none());
    }

    #[test]
    fn the_recipe_semver_waiver_is_scoped_to_the_release_it_was_granted_for() {
        // The other half, and the same reasoning as its twin in
        // `evidence::collector`: the waiver is a decision about *this* release
        // line, not a permanent exemption. It was granted on termproof staying
        // on 0.4.x; the moment the version leaves 0.4.x that reasoning has
        // expired and the waiver has to be re-decided rather than carried
        // along, so this fails the build instead of letting it ride.
        //
        // Matched on the lint name alone: `cargo package` normalises the
        // manifest, so the spacing around the value is not ours to rely on.
        let manifest = include_str!(concat!(env!("CARGO_MANIFEST_DIR"), "/Cargo.toml"));
        let waived = manifest.contains("struct_pub_field_missing");
        let version = env!("CARGO_PKG_VERSION");
        assert!(
            !waived || version.starts_with("0.4."),
            "the struct_pub_field_missing waiver in Cargo.toml was granted for \
             0.4.x and this crate is {version}. Re-decide it: either the break \
             is now carried by the version bump and the waiver, its comment and \
             `every_public_field_of_the_recipe_is_accounted_for` all go, or it \
             is re-granted for the new line and this test moves with it."
        );
    }

    #[test]
    fn legacy_recipe_defaults_version_to_one() {
        let recipe: Recipe =
            serde_json::from_str(r#"{"name":"x","command":{"argv":["true"]}}"#).expect("parse");
        assert_eq!(recipe.recipe_version, 1);
        assert_eq!(recipe.meta.priority, "P2");
        assert_eq!(recipe.cols, 100);
        assert_eq!(recipe.timeout_seconds, 30.0);
        assert_eq!(recipe.expect_exit_code, Some(0));
    }

    #[test]
    fn extension_fields_are_preserved() {
        let recipe: Recipe = serde_json::from_str(
            r#"{"name":"x","command":{"argv":["true"],"custom":"keep"},"my_extra":"hello","recipe_version":1}"#,
        )
        .expect("parse");
        assert_eq!(recipe.extension.get("my_extra").unwrap(), "hello");
        assert_eq!(recipe.command.extension.get("custom").unwrap(), "keep");
    }

    #[test]
    fn json_and_yaml_both_load() {
        let json_str = r#"{"name":"x","command":{"argv":["echo","hi"]},"recipe_version":1}"#;
        let yaml_str = "name: x\ncommand:\n  argv: [echo, hi]\nrecipe_version: 1\n";
        let from_json = Recipe::from_str(json_str, None).expect("json");
        let from_yaml = Recipe::from_str(yaml_str, None).expect("yaml");
        assert_eq!(from_json.meta.name, "x");
        assert_eq!(from_yaml.meta.name, "x");
        assert_eq!(from_json.command.argv, from_yaml.command.argv);
    }

    #[test]
    fn step_extra_preserved() {
        let recipe: Recipe = serde_json::from_str(
            r#"{"name":"x","command":{"argv":["true"]},"steps":[{"action":"wait_for_text","text":"hello","timeout_seconds":5}],"recipe_version":1}"#,
        )
        .expect("parse");
        assert_eq!(recipe.steps[0].action, "wait_for_text");
        assert_eq!(recipe.steps[0].extra.get("text").unwrap(), "hello");
    }
}
