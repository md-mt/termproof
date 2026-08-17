//! The canonical schema seam must reach the file it names.
//!
//! Before the two implementations were consolidated, `load_canonical_schema`
//! could not reach the canonical recipe schema from any checkout layout, and
//! the crate README, the architecture document and the engineering baseline
//! all said so. Both implementations now live in one repository and the schema
//! is at `python/docs/recipe-schema-v1.json`, so the seam resolves — and this
//! is what stops that from regressing into a `None` that reads as "there is no
//! canonical schema" rather than "it moved".
//!
//! It lives in `tests/` rather than beside the function, and is excluded from
//! the package, for the same reason the differential tests are: it reads a
//! path outside the crate. A consumer running `cargo test` against the
//! published tarball would have no repository around it and no way to pass.

use termproof::schema::load_canonical_schema;

#[test]
fn the_canonical_schema_is_reachable_from_this_repository() {
    let canonical = load_canonical_schema()
        .expect("python/docs/recipe-schema-v1.json should be reachable from the workspace");
    assert_eq!(canonical["title"], "TermProof recipe v1");
    assert_eq!(canonical["properties"]["recipe_version"]["const"], 1);
}
