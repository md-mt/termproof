//! Port half of the config / run-cache differential harness.
//!
//! Cascades the YAML overlays `conformance/probe_config.py` cascades
//! through [`VerifierConfig::load`], serialises each result, and compares
//! the documents — key order normalised — against what the oracle
//! recorded in `conformance/corpus/config.expected.json`; then answers
//! the recorded cache cases through [`cache_key`] and compares
//! availability and input sensitivity per side.
//!
//! # Why this exists
//!
//! The config document is what every run is configured by, whichever
//! implementation loads it, and the run-cache key decides whether a
//! recorded result may stand in for re-running a recipe. Until this test
//! nothing compared either: the two `VerifierConfig`s are different types
//! that happen to share a name, Python's typed `evidence:` block is
//! load-bearing there and silently inert here, and the two cache keys
//! fold different inputs — all without moving a number anywhere (#209).
//!
//! # Allowed differences (#209)
//!
//! The documents are compared whole apart from the named allowances
//! below, each asserted so it fails when the divergence it records stops
//! existing:
//!
//! - The Python document's typed, defaulted `evidence` block. This
//!   config has no such field: a supplied block survives only as an
//!   unvalidated extension echo of exactly the keys written
//!   ([`evidence_echo`]), and nothing reads it.
//! - `artifact_publishers`, likewise: a merged plugin map there, at most
//!   an extension echo of the overlay's fragment here.
//! - [`PYTHON_ONLY_PLUGIN_ENTRIES`] and the `session_backend` spelling:
//!   built-in registry drift between the two default tables.
//! - Unknown keys, dropped by the Python loader (outside `evidence`)
//!   and preserved here by the flatten extensions.
//! - [`PYTHON_REJECTS_RUST_ACCEPTS`]: evidence validation exists only in
//!   Python, so those overlays load here and change nothing but the echo.
//! - [`RUST_REJECTS_PYTHON_ACCEPTS`]: two coercions Python applies (a
//!   numeric string for `idle_cap_seconds`, non-string docker env
//!   values) that the typed deserialisation here refuses.
//! - Error *wording* on the one case both sides reject: the recorded
//!   `ValueError` text is the oracle's, and this side is held to the
//!   verdict (`is_err`), not to a rewording of its own message.
//! - Cache digests themselves. The payloads hashed differ by
//!   construction — the Python payload carries the whole evidence
//!   config, the JSON spacing differs, and the hashed path strings here
//!   are this test's absolute ones — so no digest is compared across
//!   languages. What is pinned is availability (`Some`/`None`) and,
//!   within each side, which inputs move the key, including the two
//!   places those answers diverge: an evidence change moves only the
//!   Python key (this `cache_key` has no evidence parameter to take),
//!   and a missing recipe file yields no Python key but a key here.
//!
//! Anything else differing — a key added, removed or renamed on either
//! side, a default value, a merge or validation outcome, a cache input
//! starting or stopping mattering — fails the comparison. Nothing in
//! either implementation changed to add this harness.
//!
//! ```sh
//! cargo test -p termproof --test differential_config -- --nocapture
//! ```

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

use termproof::cache::cache_key;
use termproof::config::VerifierConfig;

/// The fixed config scenarios: (name, overlay YAML or `None` for no
/// overlay). Keep in step with probe_config.py, which carries the same
/// strings.
const OVERLAYS: [(&str, Option<&str>); 15] = [
    ("defaults", None),
    (
        "evidence-populated",
        Some(
            "evidence:\n  dedup_step_screenshots: true\n  svg:\n    char_width: 7.5\n    \
             font_size: 12\n  png:\n    scale: 2\n    font_path: /usr/share/fonts/custom.ttf\n  \
             video:\n    fps: 30\n    crf: 18\n",
        ),
    ),
    (
        "docker-full",
        Some(
            "docker:\n  image: myimg:1.0\n  workdir: /app\n  env:\n    FOO: bar\n  volumes:\n    \
             - host: ./src\n      container: /src\n",
        ),
    ),
    (
        "plugin-overrides",
        Some(
            "steps:\n  custom_step: mypkg.steps:CustomStep\n  sleep: mypkg.steps:MySleep\n\
             artifact_publishers:\n  gcs: mypkg.pub:GcsPublisher\n",
        ),
    ),
    ("idle-null", Some("defaults:\n  idle_cap_seconds: null\n")),
    (
        "idle-string",
        Some("defaults:\n  idle_cap_seconds: '2.5'\n"),
    ),
    ("idle-negative", Some("defaults:\n  idle_cap_seconds: -1\n")),
    ("docker-env-numeric", Some("docker:\n  env:\n    FOO: 1\n")),
    ("unknown-top-level", Some("bogus_section:\n  x: 1\n")),
    ("unknown-docker-key", Some("docker:\n  bogus_knob: 3\n")),
    ("unknown-defaults-key", Some("defaults:\n  bogus_knob: 3\n")),
    ("unknown-evidence-key", Some("evidence:\n  bogus_knob: 3\n")),
    (
        "unknown-evidence-svg-key",
        Some("evidence:\n  svg:\n    bogus_knob: 3\n"),
    ),
    (
        "evidence-bad-type",
        Some("evidence:\n  svg:\n    font_size: 'twelve'\n"),
    ),
    (
        "evidence-below-minimum",
        Some("evidence:\n  svg:\n    font_size: 0\n"),
    ),
];

/// Built-in plugin entries the Python default table carries that this
/// one does not, as `(map, key, python value)` (#209). No scenario's
/// overlay touches these three maps' pinned keys, so the entries below
/// are the whole drift in every case that loads.
const PYTHON_ONLY_PLUGIN_ENTRIES: [(&str, &str, &str); 3] = [
    (
        "assertions",
        "step_screen_contains",
        "termproof.builtin_assertions:StepScreenContains",
    ),
    (
        "screen_renderers",
        "png_rsvg",
        "termproof.rsvg:RsvgPngRenderer",
    ),
    (
        "video_backends",
        "attributed_rsvg",
        "termproof.cast_video:RsvgFfmpegBackend",
    ),
];

/// The default `session_backend` each side spells, `(python, rust)`
/// (#209). No scenario overrides it.
const SESSION_BACKENDS: (&str, &str) = (
    "termproof.builtin_session:PexpectBackend",
    "termproof.builtin_session:PexpectAsciinemaBackend",
);

/// Cases the Rust loader rejects where Python coerces and accepts
/// (#209): `idle-string` (Python `float('2.5')`) and
/// `docker-env-numeric` (Python `str(1)`). The pinned Python outcomes
/// are asserted per case below.
const RUST_REJECTS_PYTHON_ACCEPTS: [&str; 2] = ["idle-string", "docker-env-numeric"];

/// Cases Python rejects for evidence validation that this loader
/// accepts without looking inside the block (#209). Each must leave the
/// loaded document identical to `defaults` apart from the echo.
const PYTHON_REJECTS_RUST_ACCEPTS: [&str; 4] = [
    "unknown-evidence-key",
    "unknown-evidence-svg-key",
    "evidence-bad-type",
    "evidence-below-minimum",
];

/// The cache case names the oracle must record. A case added to one
/// half only fails the name assert rather than passing uncompared.
const CACHE_CASE_NAMES: [&str; 8] = [
    "base",
    "evidence-tweaked",
    "renderer-changed",
    "video-off-fps-changed",
    "video-on",
    "no-source-path",
    "missing-recipe-file",
    "ci-content-changed",
];

const RECIPE_BYTES: &[u8] = b"name: login\ncommand: [cat]\n";
const CI_BYTES_A: &[u8] = b"ci content A\n";
const CI_BYTES_B: &[u8] = b"ci content B\n";

fn expected_path() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("../../../conformance/corpus/config.expected.json")
}

fn recorded_document() -> serde_json::Value {
    let recorded = std::fs::read_to_string(expected_path()).expect("oracle document readable");
    serde_json::from_str(&recorded).expect("recorded oracle document is JSON")
}

fn recorded_cases(section: &str) -> BTreeMap<String, serde_json::Value> {
    let document = recorded_document();
    let cases = document[section].as_array().expect("section is an array");
    cases
        .iter()
        .map(|case| {
            (
                case["name"].as_str().expect("case name").to_string(),
                case.clone(),
            )
        })
        .collect()
}

/// The `evidence` value this side echoes for a case whose overlay
/// supplied one: exactly the fragment written, no defaults filled in,
/// nothing validated (#209). `None` means the Rust document must carry
/// no `evidence` key at all while the Python one carries its full
/// typed, defaulted block.
fn evidence_echo(case: &str) -> Option<serde_json::Value> {
    match case {
        "evidence-populated" => Some(serde_json::json!({
            "dedup_step_screenshots": true,
            "svg": {"char_width": 7.5, "font_size": 12},
            "png": {"scale": 2, "font_path": "/usr/share/fonts/custom.ttf"},
            "video": {"fps": 30, "crf": 18},
        })),
        "unknown-evidence-key" => Some(serde_json::json!({"bogus_knob": 3})),
        "unknown-evidence-svg-key" => Some(serde_json::json!({"svg": {"bogus_knob": 3}})),
        "evidence-bad-type" => Some(serde_json::json!({"svg": {"font_size": "twelve"}})),
        "evidence-below-minimum" => Some(serde_json::json!({"svg": {"font_size": 0}})),
        _ => None,
    }
}

/// Load one scenario the way the probe does: empty project directory, a
/// user path that does not exist, the overlay as the explicit config.
fn load_case(tmp: &Path, overlay: Option<&str>) -> Result<VerifierConfig, termproof::CoreError> {
    let project = tmp.join("proj");
    std::fs::create_dir_all(&project).expect("project dir");
    let user = tmp.join("no-user.yaml");
    match overlay {
        Some(text) => {
            let explicit = tmp.join("overlay.yaml");
            std::fs::write(&explicit, text).expect("overlay written");
            VerifierConfig::load(Some(&project), Some(&user), Some(&explicit))
        }
        None => VerifierConfig::load(Some(&project), Some(&user), None),
    }
}

fn object<'a>(
    doc: &'a mut serde_json::Value,
    what: &str,
) -> &'a mut serde_json::Map<String, serde_json::Value> {
    doc.as_object_mut()
        .unwrap_or_else(|| panic!("{what} is an object"))
}

/// Remove or rewrite exactly the pinned divergences (#209), asserting
/// each one still diverges as recorded, so the whole-document comparison
/// that follows fails on anything else.
fn reconcile(case: &str, rust: &mut serde_json::Value, python: &mut serde_json::Value) {
    let rust = object(rust, "a Rust config document");
    let python = object(python, "a Python config document");

    // `evidence`: a typed, defaulted block there; absent or an
    // unvalidated echo of the written fragment here (#209).
    assert!(
        python.remove("evidence").is_some(),
        "case {case}: the Python document lost its `evidence` block; \
         remove the allowance in this test"
    );
    match evidence_echo(case) {
        Some(fragment) => assert_eq!(
            rust.remove("evidence"),
            Some(fragment),
            "case {case}: the Rust `evidence` echo moved; if it is now a \
             typed, defaulted block like Python's, remove the allowance \
             in this test"
        ),
        None => assert!(
            !rust.contains_key("evidence"),
            "case {case}: the Rust document now carries `evidence` with \
             none supplied; remove the allowance in this test"
        ),
    }

    // `artifact_publishers`: a merged plugin map there; here, nothing by
    // default and only the overlay's fragment when one is written.
    assert!(
        python.remove("artifact_publishers").is_some(),
        "case {case}: the Python document lost `artifact_publishers`"
    );
    if case == "plugin-overrides" {
        assert_eq!(
            rust.remove("artifact_publishers"),
            Some(serde_json::json!({"gcs": "mypkg.pub:GcsPublisher"})),
            "case {case}: the Rust `artifact_publishers` echo moved"
        );
    } else {
        assert!(
            !rust.contains_key("artifact_publishers"),
            "case {case}: the Rust document now carries \
             `artifact_publishers`; remove the allowance in this test"
        );
    }

    // The default `session_backend` spelling (#209), both directions.
    assert_eq!(
        python.get("session_backend"),
        Some(&serde_json::json!(SESSION_BACKENDS.0)),
        "case {case}: the Python default session backend moved"
    );
    assert_eq!(
        rust.get("session_backend"),
        Some(&serde_json::json!(SESSION_BACKENDS.1)),
        "case {case}: the Rust default session backend moved; if it now \
         spells Python's, remove the allowance in this test"
    );
    rust.insert(
        "session_backend".to_string(),
        serde_json::json!(SESSION_BACKENDS.0),
    );

    // Built-in registry drift (#209): present there with the pinned
    // values, absent here.
    for (map, key, value) in PYTHON_ONLY_PLUGIN_ENTRIES {
        assert_eq!(
            python
                .get(map)
                .and_then(|m| m.as_object())
                .unwrap_or_else(|| panic!("case {case}: Python `{map}` is an object"))
                .get(key),
            Some(&serde_json::json!(value)),
            "case {case}: the Python `{map}.{key}` entry moved"
        );
        let rust_map = rust
            .get_mut(map)
            .and_then(|m| m.as_object_mut())
            .unwrap_or_else(|| panic!("case {case}: Rust `{map}` is an object"));
        assert!(
            !rust_map.contains_key(key),
            "case {case}: the Rust defaults now carry `{map}.{key}`; \
             remove it from PYTHON_ONLY_PLUGIN_ENTRIES in this test"
        );
        rust_map.insert(key.to_string(), serde_json::json!(value));
    }

    // Unknown keys Python drops and the flatten extensions preserve
    // (#209), each pinned where it lands.
    match case {
        "unknown-top-level" => {
            assert!(
                !python.contains_key("bogus_section"),
                "case {case}: the Python loader now preserves unknown keys"
            );
            assert_eq!(
                rust.remove("bogus_section"),
                Some(serde_json::json!({"x": 1})),
                "case {case}: the Rust extension echo moved"
            );
        }
        "unknown-docker-key" => {
            let python_docker = python
                .get("docker")
                .and_then(|d| d.as_object())
                .expect("Python `docker` is an object");
            assert!(
                !python_docker.contains_key("bogus_knob"),
                "case {case}: the Python loader now preserves unknown keys"
            );
            let rust_docker = object(
                rust.get_mut("docker").expect("Rust `docker` exists"),
                "Rust `docker`",
            );
            assert_eq!(
                rust_docker.remove("bogus_knob"),
                Some(serde_json::json!(3)),
                "case {case}: the Rust docker extension echo moved"
            );
        }
        "unknown-defaults-key" => {
            let python_defaults = python
                .get("defaults")
                .and_then(|d| d.as_object())
                .expect("Python `defaults` is an object");
            assert!(
                !python_defaults.contains_key("bogus_knob"),
                "case {case}: the Python loader now preserves unknown keys"
            );
            let rust_defaults = object(
                rust.get_mut("defaults").expect("Rust `defaults` exists"),
                "Rust `defaults`",
            );
            assert_eq!(
                rust_defaults.remove("bogus_knob"),
                Some(serde_json::json!(3)),
                "case {case}: the Rust defaults extension echo moved"
            );
        }
        _ => {}
    }
}

fn assert_same_document(case: &str, rust: &serde_json::Value, python: &serde_json::Value) {
    assert_eq!(
        serde_json::to_string_pretty(python).unwrap(),
        serde_json::to_string_pretty(rust).unwrap(),
        "case {case}: the Rust config document diverged from the \
         recorded Python one beyond the allowed differences; regenerate \
         the oracle only if the Python side is the one that changed — \
         see conformance/README.md"
    );
}

#[test]
fn the_loaded_config_document_matches_the_python_one() {
    let recorded = recorded_cases("cases");
    assert_eq!(
        recorded.len(),
        OVERLAYS.len(),
        "the recorded case count drifted from OVERLAYS; a duplicate name \
         would otherwise collapse silently in the map"
    );
    assert_eq!(
        recorded.keys().map(String::as_str).collect::<Vec<_>>(),
        {
            let mut names: Vec<&str> = OVERLAYS.iter().map(|(name, _)| *name).collect();
            names.sort_unstable();
            names
        },
        "the recorded cases drifted from OVERLAYS in this test"
    );
    let defaults_document = recorded["defaults"]["config"].clone();

    for (name, overlay) in OVERLAYS {
        let tmp = tempfile::tempdir().expect("tempdir");
        let result = load_case(tmp.path(), overlay);
        let recorded_case = &recorded[name];

        if let Some(python_document) = recorded_case.get("config") {
            if RUST_REJECTS_PYTHON_ACCEPTS.contains(&name) {
                assert!(
                    result.is_err(),
                    "case {name}: the Rust loader now accepts what it \
                     used to refuse; remove it from \
                     RUST_REJECTS_PYTHON_ACCEPTS in this test"
                );
                match name {
                    "idle-string" => assert_eq!(
                        python_document["defaults"]["idle_cap_seconds"],
                        serde_json::json!(2.5),
                        "case {name}: the Python coercion outcome moved"
                    ),
                    "docker-env-numeric" => assert_eq!(
                        python_document["docker"]["env"],
                        serde_json::json!({"FOO": "1"}),
                        "case {name}: the Python coercion outcome moved"
                    ),
                    other => panic!("unhandled {other} in RUST_REJECTS_PYTHON_ACCEPTS"),
                }
                continue;
            }
            let config = result.unwrap_or_else(|e| panic!("case {name} loads in Rust: {e}"));
            let mut rust_document =
                serde_json::to_value(&config).expect("the Rust config serialises");
            let mut python_document = python_document.clone();
            reconcile(name, &mut rust_document, &mut python_document);
            assert_same_document(name, &rust_document, &python_document);
            continue;
        }

        let python_error = recorded_case["error"]
            .as_str()
            .expect("a recorded case carries `config` or `error`");
        assert!(
            python_error.starts_with("ValueError: "),
            "case {name}: the recorded Python error is not a ValueError: {python_error}"
        );
        if PYTHON_REJECTS_RUST_ACCEPTS.contains(&name) {
            let config = result.unwrap_or_else(|e| {
                panic!(
                    "case {name}: the Rust loader now rejects it too ({e}); \
                     remove it from PYTHON_REJECTS_RUST_ACCEPTS in this test"
                )
            });
            let mut rust_document =
                serde_json::to_value(&config).expect("the Rust config serialises");
            let mut python_document = defaults_document.clone();
            reconcile(name, &mut rust_document, &mut python_document);
            assert_same_document(name, &rust_document, &python_document);
        } else {
            assert!(
                result.is_err(),
                "case {name}: the Rust loader now accepts an overlay \
                 both sides used to reject"
            );
        }
    }
}

/// The shared cache inputs, varied per case below. `out` stays a fixed
/// relative literal on both sides, as in the probe.
fn rust_key(
    source: Option<&Path>,
    renderer: &str,
    video_backend: &str,
    render_video: bool,
    video_fps: u32,
    ci_base: &Path,
) -> Option<String> {
    cache_key(
        source,
        None,
        renderer,
        &[],
        Path::new("out"),
        "svg",
        video_backend,
        render_video,
        video_fps,
        &["ci.txt".to_string()],
        Some(ci_base),
    )
}

#[test]
fn the_cache_key_answers_match_the_python_ones() {
    let recorded = recorded_cases("cache_cases");
    assert_eq!(
        recorded.len(),
        CACHE_CASE_NAMES.len(),
        "the recorded cache case count drifted from CACHE_CASE_NAMES"
    );
    assert_eq!(
        recorded.keys().map(String::as_str).collect::<Vec<_>>(),
        {
            let mut names = CACHE_CASE_NAMES.to_vec();
            names.sort_unstable();
            names
        },
        "the recorded cache cases drifted from CACHE_CASE_NAMES in this test"
    );
    let python_key =
        |name: &str| -> Option<String> { recorded[name]["key"].as_str().map(str::to_string) };

    // The recorded Python relations themselves, so a re-recording that
    // quietly changed which inputs matter fails here as well as there.
    let python_base = python_key("base").expect("the Python base case has a key");
    assert_ne!(
        python_key("evidence-tweaked").as_deref(),
        Some(python_base.as_str())
    );
    assert_ne!(
        python_key("renderer-changed").as_deref(),
        Some(python_base.as_str())
    );
    assert_eq!(
        python_key("video-off-fps-changed").as_deref(),
        Some(python_base.as_str())
    );
    assert_ne!(
        python_key("video-on").as_deref(),
        Some(python_base.as_str())
    );
    assert_eq!(python_key("no-source-path"), None);
    assert_eq!(python_key("missing-recipe-file"), None);
    assert_ne!(
        python_key("ci-content-changed").as_deref(),
        Some(python_base.as_str())
    );

    let tmp = tempfile::tempdir().expect("tempdir");
    let recipe_path = tmp.path().join("recipe.yaml");
    std::fs::write(&recipe_path, RECIPE_BYTES).expect("recipe written");
    std::fs::write(tmp.path().join("ci.txt"), CI_BYTES_A).expect("ci file written");

    let base = rust_key(
        Some(&recipe_path),
        "default",
        "agg_ffmpeg",
        false,
        60,
        tmp.path(),
    )
    .expect("the Rust base case has a key");

    // Evidence moves the Python key and cannot move this one: there is
    // no evidence parameter to give (#209). The identical call is the
    // assertion — when this cache key grows an evidence input, this
    // case must be taught to pass it and this equality revisited.
    assert_eq!(
        rust_key(
            Some(&recipe_path),
            "default",
            "agg_ffmpeg",
            false,
            60,
            tmp.path()
        )
        .as_deref(),
        Some(base.as_str()),
        "the evidence-tweaked inputs changed the Rust key; see the \
         evidence allowance above"
    );
    assert_ne!(
        rust_key(
            Some(&recipe_path),
            "other",
            "agg_ffmpeg",
            false,
            60,
            tmp.path()
        )
        .as_deref(),
        Some(base.as_str()),
        "renderer stopped moving the Rust key"
    );
    assert_eq!(
        rust_key(
            Some(&recipe_path),
            "default",
            "other",
            false,
            30,
            tmp.path()
        )
        .as_deref(),
        Some(base.as_str()),
        "video settings with video off started moving the Rust key"
    );
    assert_ne!(
        rust_key(
            Some(&recipe_path),
            "default",
            "agg_ffmpeg",
            true,
            30,
            tmp.path()
        )
        .as_deref(),
        Some(base.as_str()),
        "video settings stopped moving the Rust key"
    );
    assert_eq!(
        rust_key(None, "default", "agg_ffmpeg", false, 60, tmp.path()),
        None,
        "a recipe with no source path gained a Rust key"
    );
    // A named-but-missing recipe file: no key in Python, a key here
    // (#209) — the missing file hashes as `<missing>`.
    assert!(
        rust_key(
            Some(&tmp.path().join("missing.yaml")),
            "default",
            "agg_ffmpeg",
            false,
            60,
            tmp.path()
        )
        .is_some(),
        "a missing recipe file stopped yielding a Rust key; the two \
         sides now agree, so remove the allowance above"
    );

    std::fs::write(tmp.path().join("ci.txt"), CI_BYTES_B).expect("ci file rewritten");
    assert_ne!(
        rust_key(
            Some(&recipe_path),
            "default",
            "agg_ffmpeg",
            false,
            60,
            tmp.path()
        )
        .as_deref(),
        Some(base.as_str()),
        "ci content stopped moving the Rust key"
    );
}
