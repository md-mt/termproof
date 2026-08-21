#!/usr/bin/env bash
#
# Confirm that every crate the publish plan names is on crates.io at VERSION.
#
# Reads ORDER (space-separated crate names) and VERSION from the environment,
# the same contract publish.sh has, so the set being checked is the set that
# was meant to be uploaded. Nothing here names a crate; the caller derives both
# values from .github/scripts/rust/publish-plan.py.
#
# ## Why this exists as its own thing
#
# The publish workflow already waits for each crate it uploads to appear on the
# index, so a *publish that ran* reports its own failures. The gap this closes
# is the publish that never ran at all: it triggers on a published GitHub
# release, so a tag that produced no release produces no upload and no red job
# — only the absence of one, which reads as nothing having gone wrong.
#
# Absence is not something the publish workflow can report on. This runs on the
# tag, at the end of the release path, and asks the registry the only question
# that matters: is the thing the plan said would ship actually there.
#
# ## Polling, and what a timeout means
#
# The crates upload is downstream of the release this path publishes, and it
# runs its own gate first, so it finishes minutes after the binaries do. Hence
# a poll rather than a single look. A timeout is reported as a failure and
# names the crates that are missing: at that point either the publish never
# fired, it failed, or it is still waiting — and all three are states a release
# should not be left in silently. If the `crates-io` environment ever grows a
# required reviewer, an approval slower than this window will land here; raise
# ATTEMPTS rather than deleting the check.
#
# ATTEMPTS and INTERVAL are overridable so the same script can be exercised
# without waiting out the release-sized window.
set -euo pipefail

: "${ORDER?ORDER must be set to the space-separated publish order (may be empty)}"
: "${VERSION:?VERSION must be set to the workspace version}"

ATTEMPTS="${ATTEMPTS:-80}"
INTERVAL="${INTERVAL:-30}"
INDEX="${INDEX:-https://index.crates.io}"

# Sparse-index layout: crates.io shards by name length, then by prefix.
index_url() {
    local name=$1
    case ${#name} in
        1) printf '%s/1/%s\n' "$INDEX" "$name" ;;
        2) printf '%s/2/%s\n' "$INDEX" "$name" ;;
        3) printf '%s/3/%s/%s\n' "$INDEX" "${name:0:1}" "$name" ;;
        *) printf '%s/%s/%s/%s\n' "$INDEX" "${name:0:2}" "${name:2:2}" "$name" ;;
    esac
}

# The index is what a consumer's `cargo build` resolves against, so it — not
# the web API — is the thing worth asking. A 404 means the crate has never been
# published at any version.
on_index() {
    local name=$1 body
    body=$(curl -sSf --max-time 30 "$(index_url "$name")" 2>/dev/null) || return 1
    jq -e -s --arg v "$VERSION" 'map(.vers) | index($v) != null' >/dev/null <<<"$body"
}

if [ -z "${ORDER// /}" ]; then
    # Every member carries `publish = false`. That is a policy recorded in the
    # manifests, not a fault, and the publish workflow would upload nothing
    # either — so there is nothing to be missing.
    echo "::notice::the publish plan names no crates, so there is nothing to verify on crates.io"
    exit 0
fi

missing=""
for ((attempt = 1; attempt <= ATTEMPTS; attempt++)); do
    missing=""
    for crate in $ORDER; do
        on_index "$crate" || missing="$missing $crate"
    done
    if [ -z "${missing// /}" ]; then
        echo "every planned crate is on crates.io at $VERSION: $ORDER"
        exit 0
    fi
    echo "waiting for crates.io ($attempt of $ATTEMPTS) — still missing at $VERSION:$missing"
    if [ "$attempt" -lt "$ATTEMPTS" ]; then
        sleep "$INTERVAL"
    fi
done

echo "::error::the release is out but these crates are not on crates.io at $VERSION:$missing — the crates publish did not happen. It triggers on a published GitHub release and nothing else, so check that the release exists and was published by an identity whose events start workflows, then look at the Publish crates (Rust) runs."
exit 1
