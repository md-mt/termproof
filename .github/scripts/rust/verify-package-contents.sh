#!/usr/bin/env bash
# Verify the termproof package tarball contains exactly what the publishing
# contract (docs/publishing.md) promises — and nothing it does not.
#
# Run from a checkout after `cargo package -p termproof`. The --list output
# is the authoritative manifest of the tarball, so this script checks that
# list rather than the files on disk.
#
# Required: the canonical recipe schema and the test that proves the seam
# reads it (issue #174 — the crate used to reach outside itself for the schema,
# so neither shipped), the snapshot test and its fixture (issue #33 added the
# snapshot on the promise that consumers could run it), and *not* the
# differential tests, which replay the root conformance corpus and cannot run
# without it.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)/rust"

LIST="$(cargo package -p termproof --list --allow-dirty)"

# Present: the pieces a consumer needs and the tests that can run without the
# repository around them.
for required in \
  Cargo.toml \
  Cargo.toml.orig \
  LICENSE \
  README.md \
  src/lib.rs \
  resources/recipe-schema-v1.json \
  tests/canonical_schema.rs \
  tests/schema_snapshot.rs \
  tests/snapshots/recipe_schema_v1.json
do
  if ! grep -qx "$required" <<<"$LIST"; then
    echo "::error::termproof tarball is missing $required" >&2
    exit 1
  fi
done

# Absent: repository-only artifacts that must not reach consumers. The
# differential tests replay the root conformance corpus, which is not shipped,
# so a tarball that carries those tests cannot run them.
for forbidden in \
  tests/differential_steps.rs \
  tests/differential_assertions.rs \
  tests/differential_before_after.rs \
  conformance/
do
  if grep -q "^${forbidden}" <<<"$LIST"; then
    echo "::error::termproof tarball must not contain $forbidden" >&2
    exit 1
  fi
done

echo "termproof tarball contents verified ($(wc -l <<<"$LIST") files)"
