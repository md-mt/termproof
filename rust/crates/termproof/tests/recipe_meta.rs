//! `RecipeMeta` is a Rust-side split only (#199).
//!
//! `Recipe` used to declare the seven descriptive fields itself; it now holds a
//! [`termproof::recipe::RecipeMeta`] and flattens it. The point of the split is
//! that an imperative consumer can construct the metadata without constructing
//! a `Recipe` — and the price of it must be nothing at all on the wire, because
//! recipe files are checked in and the schema is a published contract.
//!
//! These tests pin that: the exact serialised text, key order included, for
//! both a fully-populated recipe and one that takes every default. They were
//! written against the pre-split tree and the strings below are what it
//! emitted, so a regression here is a regression against the old shape rather
//! than against a fresh recording of the new one. The generated JSON Schema is
//! covered separately and just as strictly by `schema_snapshot.rs`.
//!
//! The default table at the bottom is the Python mirror's twin — see
//! `python/tests/test_recipe_meta.py::test_defaults_are_the_shared_table`.

use termproof::recipe::{Recipe, RecipeMeta};
use termproof::selection::Selectable;

/// Every field set to something other than its default, plus extension fields
/// at both the recipe and command level.
fn populated() -> serde_json::Value {
    serde_json::json!({
        "recipe_version": 1,
        "name": "n",
        "description": "d",
        "intent": "i",
        "priority": "P1",
        "execution": "scripted",
        "determinism": "flaky",
        "ci_paths": ["a/**"],
        "checks": ["c"],
        "operator": {"k": 1},
        "renderers": {"default": ["x"]},
        "command": {"argv": ["true"], "cwd": "/tmp", "env": {"A": "B"}, "pty": false, "custom": 2},
        "steps": [{"action": "send_line", "text": "hi"}],
        "assertions": [{"type": "output_contains", "value": "hi"}],
        "expect_exit_code": 3,
        "timeout_seconds": 7.5,
        "cols": 80,
        "rows": 24,
        "my_extra": {"deep": [1, 2]}
    })
}

#[test]
fn a_populated_recipe_serialises_to_the_pre_split_text() {
    let recipe: Recipe = serde_json::from_value(populated()).expect("parse");
    assert_eq!(
        serde_json::to_string(&recipe).expect("serialize"),
        r#"{"recipe_version":1,"name":"n","description":"d","intent":"i","priority":"P1","execution":"scripted","determinism":"flaky","ci_paths":["a/**"],"checks":["c"],"operator":{"k":1},"renderers":{"default":["x"]},"command":{"argv":["true"],"cwd":"/tmp","env":{"A":"B"},"pty":false,"custom":2},"steps":[{"action":"send_line","name":null,"timeout_seconds":null,"text":"hi"}],"assertions":[{"type":"output_contains","name":null,"value":"hi"}],"expect_exit_code":3,"timeout_seconds":7.5,"cols":80,"rows":24,"my_extra":{"deep":[1,2]}}"#
    );
}

#[test]
fn a_minimal_recipe_serialises_to_the_pre_split_text() {
    let recipe: Recipe =
        serde_json::from_str(r#"{"name":"x","command":{"argv":["true"]}}"#).expect("parse");
    assert_eq!(
        serde_json::to_string(&recipe).expect("serialize"),
        r#"{"recipe_version":1,"name":"x","description":"","intent":"","priority":"P2","execution":"scripted","determinism":"deterministic","ci_paths":[],"checks":[],"operator":{},"renderers":{"default":[]},"command":{"argv":["true"],"cwd":null,"env":{},"pty":true},"steps":[],"assertions":[],"expect_exit_code":0,"timeout_seconds":30.0,"cols":100,"rows":30}"#
    );
}

#[test]
fn the_descriptive_fields_stay_top_level_and_out_of_the_extension_map() {
    let recipe: Recipe = serde_json::from_value(populated()).expect("parse");

    // The flattened field must not surface as a `meta` object...
    let as_value = serde_json::to_value(&recipe).expect("serialize");
    let object = as_value.as_object().expect("object");
    assert!(!object.contains_key("meta"), "{object:?}");
    assert_eq!(object.get("name"), Some(&serde_json::json!("n")));
    assert_eq!(object.get("ci_paths"), Some(&serde_json::json!(["a/**"])));

    // ...and the catch-all must still catch only what is genuinely unknown.
    // Two flattened fields on one struct is exactly the arrangement where a
    // known key could fall through to the map instead.
    assert_eq!(recipe.extension.keys().collect::<Vec<_>>(), ["my_extra"]);
}

#[test]
fn a_recipe_round_trips_through_the_split_unchanged() {
    let recipe: Recipe = serde_json::from_value(populated()).expect("parse");
    let reparsed: Recipe =
        serde_json::from_value(serde_json::to_value(&recipe).expect("serialize")).expect("reparse");
    assert_eq!(recipe, reparsed);
}

#[test]
fn a_recipe_file_that_omits_everything_optional_gets_the_constructor_defaults() {
    // The whole reason `RecipeMeta::new` reuses the `serde` default functions:
    // hand-built metadata and parsed metadata must be the same value.
    let recipe: Recipe =
        serde_json::from_str(r#"{"name":"x","command":{"argv":["true"]}}"#).expect("parse");
    assert_eq!(recipe.meta, RecipeMeta::new("x"));
}

#[test]
fn metadata_deserialises_on_its_own_from_a_recipe_file_body() {
    // The same keys a recipe carries, read into the metadata alone — which is
    // what lets a consumer keep one file format for both recipe kinds.
    let meta: RecipeMeta =
        serde_json::from_str(r#"{"name":"x","priority":"P0","ci_paths":["src/**"]}"#)
            .expect("parse");
    assert_eq!(meta.priority, "P0");
    assert_eq!(meta.ci_paths, ["src/**"]);
    assert_eq!(meta.determinism, "deterministic");
}

#[test]
fn metadata_built_by_hand_is_selectable_without_a_recipe() {
    // The gap #199 is about: this caller has no `command` to invent.
    let meta = RecipeMeta {
        ci_paths: vec!["src/payments/**".to_string()],
        ..RecipeMeta::new("payments")
    };
    assert_eq!(meta.name(), "payments");
    assert_eq!(meta.ci_paths(), ["src/payments/**"]);
}

#[test]
fn a_recipes_own_selectable_answers_from_its_metadata() {
    let recipe: Recipe = serde_json::from_value(populated()).expect("parse");
    assert_eq!(recipe.name(), recipe.meta.name);
    assert_eq!(recipe.ci_paths(), recipe.meta.ci_paths);
}

#[test]
fn the_type_is_reachable_from_the_crate_root() {
    // Every other public type in `recipe` is re-exported at the root, and the
    // consumer this type is for is the one whose `Recipe { .. }` literal just
    // stopped compiling — they are already editing an import line. `Recipe`
    // named from the root here too, so this fails if either export goes.
    let _: termproof::RecipeMeta = termproof::RecipeMeta::new("x");
    fn takes_both(_: &termproof::Recipe, _: &termproof::RecipeMeta) {}
    let recipe: Recipe = serde_json::from_value(populated()).expect("parse");
    takes_both(&recipe, &recipe.meta);
}

#[test]
fn test_defaults_are_the_shared_table() {
    // Mirrored verbatim in `python/tests/test_recipe_meta.py` under the same
    // test name. `name` is the one field with no default in the schema, so it
    // is empty here rather than absent.
    assert_eq!(
        serde_json::to_value(RecipeMeta::default()).expect("serialize"),
        serde_json::json!({
            "name": "",
            "description": "",
            "intent": "",
            "priority": "P2",
            "execution": "scripted",
            "determinism": "deterministic",
            "ci_paths": [],
        })
    );
}
