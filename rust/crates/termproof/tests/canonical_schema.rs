//! The canonical schema seam must reach the right file, or no file.
//!
//! Two properties, and the second is the one that matters to a consumer.
//!
//! **It resolves in this repository.** Before the two implementations were
//! consolidated, `load_canonical_schema` could not reach the canonical recipe
//! schema from any checkout layout, and the crate README, the architecture
//! document and the engineering baseline all said so. Both now live in one
//! repository and the schema is at `python/docs/recipe-schema-v1.json`, so the
//! seam resolves — and this stops that regressing into a `None` that reads as
//! "there is no canonical schema" rather than "it moved".
//!
//! **It cannot be tricked by the working directory.** The lookup briefly had
//! `docs/recipe-schema-v1.json` and `python/docs/recipe-schema-v1.json` cwd
//! fallbacks after the manifest-relative one. In a published crate the
//! manifest-relative path lands in the registry checkout and misses, so those
//! fallbacks would have read whatever file of that name sat in the consumer's
//! working directory and returned it as the canonical TermProof schema. A
//! wrong schema presented as canonical is worse than no schema. The decoy test
//! below is that reproduction, kept as a regression.
//!
//! The file lives in `tests/` and is excluded from the package, for the same
//! reason the differential tests are: it reads a path outside the crate. A
//! consumer running `cargo test` against the published tarball would have no
//! repository around it and no way to pass.
//!
//! `schema` is a feature, and CI runs the whole feature powerset, so the file
//! compiles to nothing without it. An integration test cannot be gated from
//! the manifest — the crate-level attribute is how a test binary opts out.

#![cfg(feature = "schema")]

use termproof::schema::{load_canonical_schema, load_canonical_schema_from_dir};

const DECOY: &str = r#"{"title": "DECOY - a consumer's unrelated file"}"#;

/// One test, because it changes the process-wide working directory and the
/// tests in a binary run in parallel threads.
#[test]
fn the_seam_reads_the_repository_schema_and_never_the_working_directory() {
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

    // Results are captured before asserting: the cwd must be restored even if
    // an assertion fails, or every later test in this binary would run from
    // the temporary directory.
    let from_repo = load_canonical_schema();
    // A registry checkout is just a manifest directory with no repository
    // above it — exactly what a published crate has.
    let from_packaged = load_canonical_schema_from_dir(&temp);

    std::env::set_current_dir(&original).expect("restore cwd");
    let _ = std::fs::remove_dir_all(&temp);

    let canonical = from_repo.expect("the repository schema should be reachable");
    assert_eq!(
        canonical["title"], "TermProof recipe v1",
        "the seam read a file from the working directory instead of the repository"
    );
    assert_eq!(canonical["properties"]["recipe_version"]["const"], 1);

    assert!(
        from_packaged.is_none(),
        "a packaged crate must return None rather than a file found near the \
         consumer's working directory; got {from_packaged:?}"
    );
}
