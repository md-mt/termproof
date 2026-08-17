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
//! owned by the Python implementation and, since the two implementations were
//! consolidated, sits in the same repository at
//! `python/docs/recipe-schema-v1.json` — `load_canonical_schema` reads it from
//! there. Comparing the two is still parity-gate work; having the file
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
    // matching the checked-in `docs/recipe-schema-v1.json`.
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

/// The canonical recipe schema's path, relative to this crate's directory.
///
/// The schema is owned by the Python implementation and both implementations
/// now live in one repository, so it is three levels up from
/// `rust/crates/termproof`. Resolved from `CARGO_MANIFEST_DIR` rather than the
/// working directory, so it does not depend on where a test or a binary was
/// invoked from. In a published tarball the join lands on a path that does not
/// exist, which is the correct answer for a consumer: the schema is not
/// vendored into the crate.
const CANONICAL_SCHEMA_FROM_MANIFEST: &str = "../../../python/docs/recipe-schema-v1.json";

/// Load the canonical recipe schema, or `None` when it is not reachable.
///
/// This is the seam the parity gate will compare `generate_recipe_schema()`
/// against. Reaching the file is the precondition; agreeing with it is the
/// gate, and that is still open work.
#[allow(dead_code)]
pub fn load_canonical_schema() -> Option<serde_json::Value> {
    let from_manifest =
        std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join(CANONICAL_SCHEMA_FROM_MANIFEST);
    let candidates = [
        from_manifest.as_path(),
        // cwd = repository root
        std::path::Path::new("python/docs/recipe-schema-v1.json"),
        // cwd = the Python tree
        std::path::Path::new("docs/recipe-schema-v1.json"),
    ];
    for candidate in candidates {
        if candidate.exists() {
            if let Ok(content) = std::fs::read_to_string(candidate) {
                if let Ok(val) = serde_json::from_str(&content) {
                    return Some(val);
                }
            }
        }
    }
    None
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
}
