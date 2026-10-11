//! Port half of the selection differential harness.
//!
//! Replays `conformance/corpus/selection_cases.json` through
//! [`select_names`] and compares the ordered selected names per case
//! against what the oracle recorded in
//! `conformance/corpus/selection.expected.json`.
//!
//! # Why this exists
//!
//! Selection is where a `ci_paths` glob becomes "run this recipe or
//! not", and the two implementations glob with different engines:
//! Python with `fnmatch`, which has no compile step, this crate with
//! `globset`, skipping any pattern that fails to compile. #209 item 6
//! recorded that as the lowest-confidence divergence of the set — the
//! separating pattern had never actually been constructed. The corpus
//! constructs it and its neighbours: unterminated classes and
//! alternates, brace alternates, `[^...]` negation, a `**` spanning
//! zero directories, invalid ranges, backslash "escapes", case,
//! `./` prefixes, the root marker, and the harness fallback. Most
//! pattern cases are one candidate, one glob, one changed file, so a
//! selected name reads as "this glob matched this path" and each
//! divergence names its pattern.
//!
//! # The two transcriptions
//!
//! The cases are written against the Python signature, whose two
//! knobs have no same-shaped counterpart here, so this test
//! transcribes them — the only transcription in the harness, stated
//! rather than hidden:
//!
//! - `root_marker`: Python takes the bare directory name (`"repo"`)
//!   and *keeps* it (`/x/repo/src/a` normalises to `repo/src/a`); this
//!   crate takes the slashed segment (`"/repo/"`, as its own doctest
//!   spells it) and *strips* it. The test formats the bare name into
//!   the slashed segment. `None` becomes `""`, which this crate's
//!   normaliser finds at offset 0 and strips zero bytes of — a no-op,
//!   pinned by `marker/absent`.
//! - `harness_paths`: Python takes a list of globs; this crate takes
//!   one literal prefix, [`SelectionConfig::harness_root`]. The test
//!   derives the prefix from the *first* glob, dropping a trailing
//!   `/**` or `/*` — the spelling both sides' own unit tests use for
//!   a harness directory. An empty list becomes a NUL-led prefix no
//!   normalised path can start with, because `""` here would mean
//!   *every* path is under the harness. Globs no single prefix can
//!   express *as globs* diverge, and are allowances below: that is a
//!   property of the config's shape, not of the derivation.
//!
//! # Allowed differences (#209)
//!
//! [`KNOWN_DIVERGENCES`] pins each divergent case's name *and* the
//! exact list this crate selects for it. A case not listed must agree
//! with the recording exactly; a listed case must diverge by exactly
//! the pinned list, so the table fails in both directions — a
//! divergence that stops existing, one that starts, or one whose
//! shape changes all fail here. Nothing in either implementation
//! changed to add this harness.
//!
//! ```sh
//! cargo test -p termproof --test differential_selection -- --nocapture
//! ```

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

use termproof::selection::{select_names, SelectionConfig};

/// Cases whose selection diverges, as `(case, this crate's selected
/// names)` (#209). The recorded Python list is read from the corpus;
/// only the Rust answer is pinned here, beside the reason.
const KNOWN_DIVERGENCES: &[(&str, &[&str])] = &[
    // A pattern `globset` refuses to compile is skipped, so it can
    // never select. `fnmatch` has no compile step and reads the same
    // text literally, so each of these selects in Python against the
    // path spelled like the pattern. This group is #209 item 6,
    // constructed: "a ci_paths entry valid for one selects in Python,
    // dropped in Rust".
    ("dialect/unterminated-class", &[]),
    ("dialect/unterminated-class-with-range", &[]),
    ("dialect/unclosed-alternate", &[]),
    ("dialect/unopened-alternate", &[]),
    // Brace alternates: `globset` expands `{a,b}` (and an empty `{}`
    // to nothing, so `src/{}` matches only `src/` — a path
    // normalisation never leaves behind). `fnmatch` has no brace
    // syntax and matches the braces literally. The same pattern
    // therefore separates the engines on both spellings of the path.
    ("dialect/brace-alternates-expand", &["r"]),
    ("dialect/brace-alternates-literal-path", &[]),
    ("dialect/empty-alternate-group", &[]),
    // `[^a]`: `globset` reads a leading `^` as class negation, like
    // `!`; `fnmatch` reads it as a literal member, so its class is
    // {^, a}. One pattern, opposite verdicts on the two paths.
    ("dialect/caret-negation-member", &[]),
    ("dialect/caret-negation-other", &["r"]),
    // `**` as a whole path component matches zero directories in
    // `globset`. `fnmatch` has only `*`, so `/**/` still needs both
    // of its slashes (see the agreeing `glob/double-star-empty-middle`,
    // where the slashes are present and the stars match nothing).
    ("dialect/double-star-zero-directories", &["r"]),
    ("dialect/leading-double-star-zero-directories", &["r"]),
    // The root marker: Python keeps it in the normalised path
    // (`repo/src/a.py`), this crate strips it (`src/a.py`). A
    // repo-relative `ci_paths` entry therefore matches an absolute
    // changed path here and not there, and a marker-prefixed entry
    // does the reverse. When pattern and path both carry the marker
    // the two agree again (`marker/absolute-pattern-and-path`).
    ("marker/relative-pattern-absolute-path", &["r"]),
    ("marker/marker-prefixed-pattern", &[]),
    // The harness rule: Python takes globs, any of which may fire;
    // this crate takes one literal prefix. A second glob in the list
    // has no spelling in `SelectionConfig`. `**/verify/**` has no
    // single-prefix spelling *as a glob* — it means a `verify`
    // directory at any depth, and the derivation below yields the
    // useless literal prefix `**/verify/`, which no normalised path
    // starts with — so changes they would suppress in Python select
    // normally here. That is narrower than "no prefix for this
    // path": a caller could spell this case's sampled `x/verify/`
    // by hand and suppress `x/verify/runner.py`, but that answers
    // the one path, not the glob (it misses `y/verify/...`).
    ("harness/nested-glob", &["smoke", "r"]),
    ("harness/multiple-globs-second-fires", &["smoke", "r"]),
];

fn corpus_dir() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("../../../conformance/corpus")
}

fn read_json(path: &Path) -> serde_json::Value {
    serde_json::from_str(&std::fs::read_to_string(path).expect("corpus file readable"))
        .expect("corpus file is JSON")
}

fn strings(value: &serde_json::Value) -> Vec<String> {
    value
        .as_array()
        .expect("a string list is an array")
        .iter()
        .map(|item| {
            item.as_str()
                .expect("a string list holds strings")
                .to_string()
        })
        .collect()
}

/// A case's optional string list, absent meaning empty — the defaults
/// `probe_selection.py` applies on the Python side.
fn opt_strings(case: &serde_json::Value, key: &str) -> Vec<String> {
    case.get(key).map(strings).unwrap_or_default()
}

/// The Python `repo_marker` spelled as this crate takes it: the
/// slashed segment, stripped rather than kept. See the module docs.
fn repo_marker(case: &serde_json::Value) -> String {
    match case.get("root_marker") {
        None | Some(serde_json::Value::Null) => String::new(),
        Some(marker) => format!(
            "/{}/",
            marker
                .as_str()
                .expect("root_marker is a string")
                .trim_matches('/')
        ),
    }
}

/// The Python `harness_paths` spelled as this crate takes it: one
/// literal prefix derived from the first glob. See the module docs.
fn harness_root(harness_paths: &[String]) -> String {
    match harness_paths.first() {
        // No harness rule. `""` would put every path under the
        // harness (`starts_with("")`), so the absence is spelled as
        // a prefix no normalised path can start with.
        None => "\u{0}never/".to_string(),
        Some(first) => {
            let mut root = first.as_str();
            for suffix in ["/**", "/*"] {
                if let Some(stripped) = root.strip_suffix(suffix) {
                    root = stripped;
                    break;
                }
            }
            let mut root = root.to_string();
            if !root.ends_with('/') {
                root.push('/');
            }
            root
        }
    }
}

/// One case replayed through the real [`select_names`].
fn run_case(case: &serde_json::Value) -> Vec<String> {
    let candidates: Vec<(String, Vec<String>)> = case["candidates"]
        .as_array()
        .expect("candidates is an array")
        .iter()
        .map(|entry| {
            (
                entry["name"]
                    .as_str()
                    .expect("a candidate name is a string")
                    .to_string(),
                strings(&entry["ci_paths"]),
            )
        })
        .collect();
    let always = opt_strings(case, "always");
    let marker = repo_marker(case);
    let root = harness_root(&opt_strings(case, "harness_paths"));
    let config = SelectionConfig {
        harness_root: &root,
        repo_marker: &marker,
        smoke: &always.iter().map(String::as_str).collect::<Vec<_>>(),
    };
    select_names(&candidates, &strings(&case["changed_files"]), &config)
}

#[test]
fn the_selected_recipes_match_the_python_ones() {
    let corpus = corpus_dir();
    let cases = read_json(&corpus.join("selection_cases.json"));
    let cases = cases.as_array().expect("the corpus is an array of cases");

    let recorded = read_json(&corpus.join("selection.expected.json"));
    let recorded_cases = recorded["cases"].as_array().expect("cases is an array");
    assert_eq!(
        recorded_cases.len(),
        cases.len(),
        "the recorded case count drifted from selection_cases.json"
    );
    let expected: BTreeMap<String, Vec<String>> = recorded_cases
        .iter()
        .map(|case| {
            (
                case["name"].as_str().expect("case name").to_string(),
                strings(&case["selected"]),
            )
        })
        .collect();
    let case_names: Vec<String> = cases
        .iter()
        .map(|case| case["name"].as_str().expect("case name").to_string())
        .collect();
    // No `dedup` on the sorted input names: `expected`'s keys are
    // unique by construction, so a duplicate case name in the input
    // corpus — even one duplicated in the recording too, where the
    // length check above still passes — leaves the undeduped list
    // longer than the key list and fails here, instead of collapsing
    // silently in the map.
    assert_eq!(
        expected.keys().cloned().collect::<Vec<_>>(),
        {
            let mut names = case_names.clone();
            names.sort_unstable();
            names
        },
        "the recorded cases drifted from the input corpus (a duplicate \
         case name fails here too: the map's keys are deduped, the \
         sorted input names deliberately are not); regenerate the \
         oracle only if the Python side is the one that changed — \
         see conformance/README.md"
    );

    let mut agreed = 0usize;
    let mut divergent: Vec<String> = Vec::new();
    for case in cases {
        let name = case["name"].as_str().expect("case name");
        let python = &expected[name];
        let rust = run_case(case);
        if rust == *python {
            agreed += 1;
            continue;
        }
        println!("divergence {name}: python {python:?}, rust {rust:?}");
        divergent.push(name.to_string());
        let pinned = KNOWN_DIVERGENCES
            .iter()
            .find(|(case, _)| *case == name)
            .unwrap_or_else(|| {
                panic!(
                    "case {name} diverged (python {python:?}, rust {rust:?}) \
                     with no KNOWN_DIVERGENCES allowance; if this is a new \
                     #209 divergence, pin it there with its reason"
                )
            });
        assert_eq!(
            rust,
            pinned.1.iter().map(|s| s.to_string()).collect::<Vec<_>>(),
            "case {name}'s divergence changed shape; update its pinned \
             Rust answer in KNOWN_DIVERGENCES only if the new divergence \
             is the one #209 means to keep"
        );
    }

    // Every allowance must still be needed: a listed case that starts
    // agreeing — or disappears from the corpus — fails here, so the
    // table cannot outlive the divergences it records.
    let mut divergent_sorted = divergent.clone();
    divergent_sorted.sort_unstable();
    let mut allowance_names: Vec<String> = KNOWN_DIVERGENCES
        .iter()
        .map(|(case, _)| case.to_string())
        .collect();
    allowance_names.sort_unstable();
    assert_eq!(
        divergent_sorted, allowance_names,
        "the divergent cases drifted from KNOWN_DIVERGENCES; a case \
         that now agrees means the divergence was fixed — remove its \
         allowance, and say so — and a case missing from the table \
         should already have failed above"
    );

    println!(
        "selection: {agreed}/{} agree exactly, {} known divergences pinned",
        cases.len(),
        divergent.len()
    );
}
