//! JSON Schema generation for recipes (Draft 2020-12).
//!
//! Uses `schemars` as the source-to-schema generator. The generated schema is
//! Draft 2020-12 (spec §5.3).
//!
//! The crate's own generated schema is pinned by a checked-in parsed-JSON
//! snapshot (`crates/termproof/tests/schema_snapshot.rs` + its snapshot
//! file). The snapshot is compared as `serde_json::Value` trees, so object
//! key order is ignored but every structural difference — keywords, numbers,
//! array order, `$ref` targets — fails the test. Re-blessing is deliberate
//! and non-default: `TERM_PROOF_BLESS_SCHEMA=1 cargo test -p termproof
//! --test schema_snapshot` (see `docs/engineering-baseline.md` §10).
//!
//! The snapshot proves only that this crate's own output does not drift; it
//! does not establish agreement with the canonical schema. That schema is
//! owned by the Python implementation; this crate carries its own copy at
//! `resources/recipe-schema-v1.json`, embedded by [`CANONICAL_SCHEMA_JSON`],
//! and CI holds that copy byte-identical to the Python package's
//! (`python/scripts/check_schema_copies.py`). Comparing the two *schemas* —
//! generated against canonical — is still parity-gate work; having the file
//! reachable is the precondition, not the gate.

use schemars::gen::{SchemaGenerator, SchemaSettings};

use crate::recipe::Recipe;

/// Generate the Draft 2020-12 JSON Schema for [`Recipe`].
///
/// The schema includes `additionalProperties: true` at the recipe, command,
/// step, and assertion levels via the flattened extension maps.
pub fn generate_recipe_schema() -> serde_json::Value {
    let settings = SchemaSettings::draft2019_09();
    let generator = SchemaGenerator::new(settings);
    let schema = generator.into_root_schema_for::<Recipe>();

    // Ensure the schema declares Draft 2020-12 and carries identifying metadata
    // matching the canonical schema in `resources/recipe-schema-v1.json`. The
    // `$id` is that schema's own, verbatim: it identifies the recipe schema,
    // not the file's location, and rewriting it here would make the two
    // disagree over which schema they are.
    let mut value = serde_json::to_value(&schema).expect("schema serializes");
    if let Some(obj) = value.as_object_mut() {
        obj.insert(
            "$schema".to_string(),
            serde_json::Value::String("https://json-schema.org/draft/2020-12/schema".to_string()),
        );
        obj.insert(
            "$id".to_string(),
            serde_json::Value::String(
                "https://github.com/md-mt/termproof/docs/recipe-schema-v1.json".to_string(),
            ),
        );
        obj.insert(
            "title".to_string(),
            serde_json::Value::String("TermProof recipe v1".to_string()),
        );
    }
    // Fix const for recipe_version: schemars emits type+range, but the
    // canonical schema uses `const: 1`. Normalize to const for exact drift checks.
    if let Some(props) = value
        .get_mut("properties")
        .and_then(|v| v.as_object_mut())
        .and_then(|m| m.get_mut("recipe_version"))
        .and_then(|v| v.as_object_mut())
    {
        props.clear();
        props.insert("const".to_string(), serde_json::Value::Number(1.into()));
    }
    value
}

/// The canonical recipe schema, embedded from this crate's own copy.
///
/// The schema is owned by the Python implementation, but a crate that has to
/// look outside itself to find it does not have it: a registry checkout has no
/// repository above it, so the previous manifest-relative
/// `../../../python/docs/recipe-schema-v1.json` resolved for this repository
/// and for nobody else (#174). The crate now carries the file, and
/// `python/scripts/check_schema_copies.py` holds it byte-identical to
/// `python/termproof/_resources/recipe-schema-v1.json` in CI.
///
/// This is the text, exactly as shipped. [`load_canonical_schema`] parses it.
pub const CANONICAL_SCHEMA_JSON: &str = include_str!("../resources/recipe-schema-v1.json");

/// Load the canonical recipe schema.
///
/// This is the seam the parity gate will compare `generate_recipe_schema()`
/// against. Reaching the schema is the precondition; agreeing with it is the
/// gate, and that is still open work.
///
/// Reads **only** [`CANONICAL_SCHEMA_JSON`] — no filesystem access, so no
/// working directory and no path outside this crate can influence the answer.
/// That is a correctness property, not a tidiness one. This function once had
/// a `docs/recipe-schema-v1.json` cwd fallback, and in a published crate —
/// where the manifest-relative path landed in the registry checkout and missed
/// — it would have read whatever file of that name happened to sit in the
/// consumer's working directory and returned it as the canonical TermProof
/// schema. A wrong schema presented as canonical is worse than no schema.
///
/// The `Option` is vestigial: the schema is embedded at compile time and
/// `canonical_schema_is_the_recipe_schema` below holds it to being valid JSON,
/// so the result is always `Some`. `serde_json::Value` is the honest return
/// type and the right shape for the next minor bump. It is kept as-is here by
/// choice, not by constraint: narrowing it breaks every caller that matches on
/// the result, which is a minor bump under the pre-1.0 convention
/// (`docs/publishing.md`), and a packaging fix is the wrong change to carry
/// one.
///
/// Do not read the green `cargo semver-checks` gate as agreement. It was
/// measured: narrowing this return type passes it. (Making the function
/// private fails, so the gate is wired — it just has no lint for this.) The
/// compatibility argument above is the whole reason; the tooling is not
/// enforcing it.
pub fn load_canonical_schema() -> Option<serde_json::Value> {
    serde_json::from_str(CANONICAL_SCHEMA_JSON).ok()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn schema_is_draft_2020_12() {
        let schema = generate_recipe_schema();
        assert_eq!(
            schema["$schema"],
            "https://json-schema.org/draft/2020-12/schema"
        );
    }

    #[test]
    fn schema_has_required_fields() {
        let schema = generate_recipe_schema();
        let required = schema["required"].as_array().expect("required is array");
        let req_strs: Vec<&str> = required.iter().map(|v| v.as_str().unwrap()).collect();
        assert!(req_strs.contains(&"name"));
        assert!(req_strs.contains(&"command"));
    }

    #[test]
    fn schema_recipe_version_is_const_one() {
        let schema = generate_recipe_schema();
        assert_eq!(schema["properties"]["recipe_version"]["const"], 1);
    }

    /// The embedded text is what makes [`load_canonical_schema`]'s `Option`
    /// vestigial, so hold it to being the schema and not, say, a stray file.
    #[test]
    fn canonical_schema_is_the_recipe_schema() {
        let canonical = load_canonical_schema().expect("the embedded schema parses");
        assert_eq!(canonical["title"], "TermProof recipe v1");
        assert_eq!(canonical["properties"]["recipe_version"]["const"], 1);
    }
}
