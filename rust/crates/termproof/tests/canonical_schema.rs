//! The canonical schema seam reads the crate's own copy, and only that.
//!
//! Two properties, and the second is the one that matters to a consumer.
//!
//! **It resolves anywhere.** The schema is embedded from
//! `resources/recipe-schema-v1.json` with `include_str!`, so
//! `load_canonical_schema` answers the same from this repository, from a
//! registry checkout, and from a vendored copy. It used to be read through
//! `../../../python/docs/recipe-schema-v1.json`, which resolved for this
//! repository and returned `None` for every published-crate consumer (#174).
//!
//! **It cannot be tricked by the working directory.** The lookup briefly had
//! `docs/recipe-schema-v1.json` and `python/docs/recipe-schema-v1.json` cwd
//! fallbacks after the manifest-relative one. In a published crate the
//! manifest-relative path landed in the registry checkout and missed, so those
//! fallbacks would have read whatever file of that name sat in the consumer's
//! working directory and returned it as the canonical TermProof schema. A
//! wrong schema presented as canonical is worse than no schema. The decoy test
//! below is that reproduction, kept as a regression — the fix for the `None`
//! must not be a fix that reintroduces path searching.
//!
//! This file ships in the package. It used to be excluded, because it read a
//! path outside the crate and a consumer running `cargo test` against the
//! published tarball had no repository around it and no way to pass. It reads
//! nothing outside the crate now, so the part of the crate that a consumer
//! most needs to trust is finally testable from the artifact they were given.
//!
//! `schema` is a feature, and CI runs the whole feature powerset, so the file
//! compiles to nothing without it. An integration test cannot be gated from
//! the manifest — the crate-level attribute is how a test binary opts out.

#![cfg(feature = "schema")]

use termproof::schema::{load_canonical_schema, CANONICAL_SCHEMA_JSON};

const DECOY: &str = r#"{"title": "DECOY - a consumer's unrelated file"}"#;

/// One test, because it changes the process-wide working directory and the
/// tests in a binary run in parallel threads.
#[test]
fn the_seam_reads_the_embedded_schema_and_never_the_working_directory() {
    let temp =
        std::env::temp_dir().join(format!("termproof-canonical-schema-{}", std::process::id()));
    // Both cwd shapes the removed fallbacks accepted.
    for relative in ["docs", "python/docs"] {
        std::fs::create_dir_all(temp.join(relative)).expect("create decoy dir");
        std::fs::write(temp.join(relative).join("recipe-schema-v1.json"), DECOY)
            .expect("write decoy");
    }

    let original = std::env::current_dir().expect("cwd");
    std::env::set_current_dir(&temp).expect("enter the decoy directory");

    // The result is captured before asserting: the cwd must be restored even
    // if an assertion fails, or every later test in this binary would run from
    // the temporary directory.
    let from_decoy_dir = load_canonical_schema();

    std::env::set_current_dir(&original).expect("restore cwd");
    let _ = std::fs::remove_dir_all(&temp);

    let canonical = from_decoy_dir.expect("the embedded schema is always reachable");
    assert_eq!(
        canonical["title"], "TermProof recipe v1",
        "the seam read a file from the working directory instead of the crate"
    );
    assert_eq!(canonical["properties"]["recipe_version"]["const"], 1);
}

/// The embedded text is the shipped file verbatim, which is what the
/// cross-package byte-equality gate (`python/scripts/check_schema_copies.py`)
/// compares. Parsing and re-serializing would make that gate meaningless.
#[test]
fn the_embedded_text_is_the_packaged_file_verbatim() {
    let packaged = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("resources")
        .join("recipe-schema-v1.json");
    let on_disk = std::fs::read_to_string(&packaged)
        .unwrap_or_else(|e| panic!("{} is unreadable ({e})", packaged.display()));
    assert_eq!(
        on_disk,
        CANONICAL_SCHEMA_JSON,
        "the embedded schema text differs from {}",
        packaged.display()
    );
}
