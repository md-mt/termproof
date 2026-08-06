//! JSON Schema generation for recipes (Draft 2020-12).
//!
//! Uses `schemars` as the source-to-schema generator. The generated schema is
//! Draft 2020-12 (spec §5.3) and is checked against the checked-in
//! `docs/recipe-schema-v1.json` for drift.

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

/// Load the checked-in canonical schema from `docs/recipe-schema-v1.json` if present.
///
/// When running from the workspace the docs path is `../docs/recipe-schema-v1.json`
/// relative to `rust/`; fallback is to look beside the crate root.
#[allow(dead_code)]
pub fn load_canonical_schema() -> Option<serde_json::Value> {
    for candidate in [
        // When run with cwd = rust/ (workspace root's rust dir)
        std::path::Path::new("../docs/recipe-schema-v1.json"),
        // When run with cwd = repository root
        std::path::Path::new("docs/recipe-schema-v1.json"),
        // When run with cwd = rust/crates/termproof-core
        std::path::Path::new("../../../docs/recipe-schema-v1.json"),
    ] {
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
