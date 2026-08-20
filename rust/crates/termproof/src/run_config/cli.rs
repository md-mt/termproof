//! The command line that fills in a [`RunConfig`].
//!
//! [`super`] models a whole run and says how the three sources of an answer
//! rank — flag, then config file, then built-in default, via [`pick`]. It does
//! not say where the flags come from, so every consumer wrote that layer again:
//! the same twenty-odd `clap` builders, and [`pick`] re-derived by hand once per
//! flag. This module is that layer, once.
//!
//! # The whole outer loop
//!
//! ```no_run
//! use termproof::run_config::{self, Execution, RunConfig};
//!
//! let builtin = RunConfig {
//!     execution: Execution { transport: Some("pty".into()), ..Default::default() },
//!     ..Default::default()
//! };
//! let matches = run_config::clap_command().get_matches();
//! let config = run_config::resolve(&matches, &builtin)?;
//! # Ok::<(), String>(())
//! ```
//!
//! [`resolve`] reads `--run-config`, parses it, and applies the precedence to
//! every field. A consumer with no flags of its own needs nothing else.
//!
//! # Composing
//!
//! A consumer with flags of its own owns the [`Command`] and asks for the
//! standard ones to be added to it:
//!
//! ```
//! use clap::{Arg, ArgAction, Command};
//! use termproof::run_config;
//!
//! let command = run_config::augment_args(Command::new("validate"))
//!     .arg(Arg::new("watch").long("watch").action(ArgAction::SetTrue));
//! let matches = command.get_matches_from(["validate", "--renderer", "alternate", "--watch"]);
//!
//! assert!(matches.get_flag("watch"));
//! let flags = run_config::from_matches(&matches).unwrap();
//! assert_eq!(flags.execution.renderer.as_deref(), Some("alternate"));
//! ```
//!
//! [`clap_command`] is [`augment_args`] over a bare `termproof` command, so the
//! two agree by construction rather than by being kept in step.
//!
//! # No flag here has a `default_value`
//!
//! That is the load-bearing rule, and [`super`]'s precedence section is where
//! it comes from: a flag that merely *has* a default is indistinguishable from
//! one the caller *passed*, and if the two look alike a config file can never
//! override a defaulted flag — which would make most of the schema dead. So the
//! built-in default lives in the `builtin: &RunConfig` argument to [`resolve`]
//! and [`merge`], never in the `clap` argument, and "the caller passed this"
//! means exactly that `ArgMatches` has a value for it.
//!
//! The corollary is that **an empty value is still a value**. `--renderer ''`
//! beats a configured renderer and resolves to `Some("")`, because the caller
//! passed it. Reading it as "unset" would be this layer inventing a fourth rule
//! on top of the three [`pick`] states, and would put the caller back to
//! guessing which flags treat empty specially.
//!
//! # Repeatable flags, and what "unset" means for them
//!
//! `--root`, `--exclude`, `--recipe-name`, `--env`, `--publisher` and
//! `--publisher-setting` are repeatable, and land in fields that are a `Vec` or
//! a map rather than an `Option`. For those, empty is unset and the first
//! non-empty of flag / config / built-in wins as a whole — the same shape
//! [`pick`] has, applied to the whole list.
//!
//! Two consequences worth stating rather than discovering. There is no way to
//! say "explicitly no excludes" on the command line, which matches the config
//! file, where `exclude: []` is also indistinguishable from an absent key. And
//! a passed `--env` replaces a configured `env` wholesale rather than merging
//! key by key: per-key merging is a fourth precedence rule, and this layer
//! exists to stop those being invented one consumer at a time.
//!
//! # Divergence from `termproof.cli`
//!
//! Python's `termproof.cli` is an `argparse` program for the `termproof`
//! binary; this is a library layer for a config type Python has no counterpart
//! for. Where the two name the same thing they use the same flag —
//! `--priority`, `--recipe-name`, `--renderer` — and where they do not, this
//! module picks a different name rather than reusing one of Python's for a
//! different meaning. The full reconciliation is in the CHANGELOG entry for
//! #197.

use std::collections::BTreeMap;
use std::path::Path;

use clap::{value_parser, Arg, ArgAction, ArgGroup, ArgMatches, Command};

use super::{
    pick, BinarySource, Discovery, Execution, Output, Publisher, Requirements, RunConfig, Selection,
};

/// The standard `RunConfig` flags on a bare `termproof` command.
///
/// Equal to [`augment_args`] over `Command::new("termproof")`; a consumer that
/// already owns a [`Command`] should call that instead.
pub fn clap_command() -> Command {
    augment_args(Command::new("termproof"))
}

/// Add the standard `RunConfig` flags to an existing command.
///
/// The consumer keeps its own `Command` — name, version, about, subcommands and
/// any flags of its own — and gets the ones this crate knows how to parse back
/// into a [`RunConfig`].
pub fn augment_args(command: Command) -> Command {
    command
        .arg(
            Arg::new("run-config")
                .long("run-config")
                .value_name("PATH")
                .help("Read a run config from this YAML or JSON file"),
        )
        // -- discovery ---------------------------------------------------
        .arg(
            Arg::new("root")
                .long("root")
                .value_name("DIR")
                .action(ArgAction::Append)
                .help("Directory a changed file must fall under to count as touching the framework (repeatable)"),
        )
        .arg(
            Arg::new("repo-marker")
                .long("repo-marker")
                .value_name("FRAGMENT")
                .help("Path fragment that marks the start of a repo-relative path"),
        )
        .arg(
            Arg::new("all")
                .long("all")
                .action(ArgAction::SetTrue)
                .help("Run every discovered recipe"),
        )
        .arg(
            Arg::new("priority")
                .long("priority")
                .value_name("PRIORITY")
                .help("Run every recipe at this priority, e.g. P0"),
        )
        .arg(
            Arg::new("recipe-name")
                .long("recipe-name")
                .value_name("NAME")
                .action(ArgAction::Append)
                .help("Run exactly this recipe (repeatable)"),
        )
        .arg(
            Arg::new("changed-files")
                .long("changed-files")
                .value_name("PATH")
                .help("Run recipes whose ci_paths match the changed files listed in this file"),
        )
        // The enum is mutually exclusive by construction, so the command line
        // is too — otherwise "all and a priority" becomes something this layer
        // has to rank, and the config file has no such ranking to mirror.
        .group(
            ArgGroup::new("select")
                .args(["all", "priority", "recipe-name", "changed-files"])
                .multiple(false),
        )
        .arg(
            Arg::new("exclude")
                .long("exclude")
                .value_name("GLOB")
                .action(ArgAction::Append)
                .help("Skip recipes whose name matches this glob (repeatable)"),
        )
        // -- execution ---------------------------------------------------
        .arg(
            Arg::new("transport")
                .long("transport")
                .value_name("NAME")
                .help("Terminal transport, for example pty or tmux"),
        )
        .arg(
            Arg::new("renderer")
                .long("renderer")
                .value_name("NAME")
                .help("Renderer or renderer set to validate"),
        )
        .arg(
            Arg::new("model")
                .long("model")
                .value_name("ID")
                .help("Model identifier to run the product under test with"),
        )
        .arg(
            Arg::new("effort")
                .long("effort")
                .value_name("LEVEL")
                .help("Reasoning-effort setting to pair with --model"),
        )
        .arg(
            Arg::new("binary-installed")
                .long("binary-installed")
                .action(ArgAction::SetTrue)
                .help("Test the already-installed binary"),
        )
        .arg(
            Arg::new("binary-build")
                .long("binary-build")
                .value_name("CHANGE")
                .help("Build from the current checkout, labelling results with this change id"),
        )
        .group(
            ArgGroup::new("binary")
                .args(["binary-installed", "binary-build"])
                .multiple(false),
        )
        .arg(
            Arg::new("env")
                .long("env")
                .value_name("KEY=VALUE")
                .action(ArgAction::Append)
                .help("Environment applied to every recipe (repeatable)"),
        )
        .arg(
            Arg::new("timeout-scale")
                .long("timeout-scale")
                .value_name("FACTOR")
                .value_parser(value_parser!(f64))
                .help("Multiply every recipe's declared timeout by this factor"),
        )
        // -- output ------------------------------------------------------
        .arg(
            Arg::new("artifact-dir")
                .long("artifact-dir")
                .value_name("DIR")
                .help("Directory for screenshots, casts and videos"),
        )
        .arg(
            Arg::new("report-path")
                .long("report-path")
                .value_name("PATH")
                .help("Where the human-readable report is written"),
        )
        .arg(
            Arg::new("result-json-path")
                .long("result-json-path")
                .value_name("PATH")
                .help("Where the machine-readable result JSON is written"),
        )
        .arg(
            Arg::new("publisher")
                .long("publisher")
                .value_name("NAME")
                .action(ArgAction::Append)
                .help("Publisher to run, in the order given (repeatable)"),
        )
        .arg(
            Arg::new("publisher-setting")
                .long("publisher-setting")
                .value_name("PUBLISHER:KEY=VALUE")
                .action(ArgAction::Append)
                .help("Setting for a publisher named by --publisher (repeatable)"),
        )
        .arg(
            Arg::new("require-uploaded-media")
                .long("require-uploaded-media")
                .action(ArgAction::SetTrue)
                .help("Fail if evidence was not uploaded anywhere shareable"),
        )
        .arg(
            Arg::new("require-media-publisher")
                .long("require-media-publisher")
                .value_name("NAME")
                .help("Fail if this specific publisher did not carry the evidence"),
        )
}

/// Exactly what the flags said, and nothing else.
///
/// Every field the caller did not pass is left unset, so the result is the
/// `flag` column of [`pick`] rather than a usable config. [`resolve`] is what
/// turns it into one.
pub fn from_matches(matches: &ArgMatches) -> Result<RunConfig, String> {
    Ok(RunConfig {
        discovery: Discovery {
            roots: strings(matches, "root"),
            repo_marker: string(matches, "repo-marker"),
            select: selection(matches),
            exclude: strings(matches, "exclude"),
        },
        execution: Execution {
            transport: string(matches, "transport"),
            renderer: string(matches, "renderer"),
            model: string(matches, "model"),
            effort: string(matches, "effort"),
            binary: binary(matches),
            env: env(matches)?,
            timeout_scale: matches.get_one::<f64>("timeout-scale").copied(),
        },
        output: Output {
            artifact_dir: string(matches, "artifact-dir"),
            report_path: string(matches, "report-path"),
            result_json_path: string(matches, "result-json-path"),
            publishers: publishers(matches)?,
            require: Requirements {
                uploaded_media: matches.get_flag("require-uploaded-media"),
                media_publisher: string(matches, "require-media-publisher"),
            },
        },
    })
}

/// The config file named by `--run-config`, or an empty config if there is none.
pub fn configured(matches: &ArgMatches) -> Result<RunConfig, String> {
    match matches.get_one::<String>("run-config") {
        Some(path) => RunConfig::from_path(Path::new(path)),
        None => Ok(RunConfig::default()),
    }
}

/// The command line and its `--run-config` file, resolved against `builtin`.
///
/// This is the whole outer loop: [`configured`] for the file, [`from_matches`]
/// for the flags, [`merge`] for the precedence.
pub fn resolve(matches: &ArgMatches, builtin: &RunConfig) -> Result<RunConfig, String> {
    Ok(merge(
        &from_matches(matches)?,
        &configured(matches)?,
        builtin,
    ))
}

/// [`pick`] over every field of a [`RunConfig`], in one place.
///
/// Separate from [`resolve`] because it is pure: a consumer that reads its
/// config from somewhere other than `--run-config` still wants the precedence
/// applied once rather than per flag.
pub fn merge(flags: &RunConfig, configured: &RunConfig, builtin: &RunConfig) -> RunConfig {
    let (f, c, b) = (flags, configured, builtin);
    RunConfig {
        discovery: Discovery {
            roots: pick_list(&f.discovery.roots, &c.discovery.roots, &b.discovery.roots),
            repo_marker: pick_opt(
                &f.discovery.repo_marker,
                &c.discovery.repo_marker,
                &b.discovery.repo_marker,
            ),
            select: pick_opt(
                &f.discovery.select,
                &c.discovery.select,
                &b.discovery.select,
            ),
            exclude: pick_list(
                &f.discovery.exclude,
                &c.discovery.exclude,
                &b.discovery.exclude,
            ),
        },
        execution: Execution {
            transport: pick_opt(
                &f.execution.transport,
                &c.execution.transport,
                &b.execution.transport,
            ),
            renderer: pick_opt(
                &f.execution.renderer,
                &c.execution.renderer,
                &b.execution.renderer,
            ),
            model: pick_opt(&f.execution.model, &c.execution.model, &b.execution.model),
            effort: pick_opt(
                &f.execution.effort,
                &c.execution.effort,
                &b.execution.effort,
            ),
            binary: pick_opt(
                &f.execution.binary,
                &c.execution.binary,
                &b.execution.binary,
            ),
            env: pick_map(&f.execution.env, &c.execution.env, &b.execution.env),
            timeout_scale: pick_opt(
                &f.execution.timeout_scale,
                &c.execution.timeout_scale,
                &b.execution.timeout_scale,
            ),
        },
        output: Output {
            artifact_dir: pick_opt(
                &f.output.artifact_dir,
                &c.output.artifact_dir,
                &b.output.artifact_dir,
            ),
            report_path: pick_opt(
                &f.output.report_path,
                &c.output.report_path,
                &b.output.report_path,
            ),
            result_json_path: pick_opt(
                &f.output.result_json_path,
                &c.output.result_json_path,
                &b.output.result_json_path,
            ),
            publishers: pick_list(
                &f.output.publishers,
                &c.output.publishers,
                &b.output.publishers,
            ),
            require: Requirements {
                // A `bool` has no unset state to rank, so this is `pick` where
                // `pick` can tell the difference and a disjunction where it
                // cannot: any of the three asking for it is asking for it.
                uploaded_media: f.output.require.uploaded_media
                    || c.output.require.uploaded_media
                    || b.output.require.uploaded_media,
                media_publisher: pick_opt(
                    &f.output.require.media_publisher,
                    &c.output.require.media_publisher,
                    &b.output.require.media_publisher,
                ),
            },
        },
    }
}

/// [`pick`] for a field whose built-in is itself optional.
///
/// [`pick`] takes the built-in as a value, because that is what a built-in
/// usually is. Here it arrives as a field of a [`RunConfig`], so it can be
/// absent too — and when it is, there is no third answer and the first two are
/// the whole ranking.
fn pick_opt<T: Clone>(flags: &Option<T>, configured: &Option<T>, builtin: &Option<T>) -> Option<T> {
    match builtin {
        Some(builtin) => Some(pick(flags.clone(), configured.clone(), builtin.clone())),
        None => flags.clone().or_else(|| configured.clone()),
    }
}

/// [`pick`] for a field whose "unset" is emptiness rather than `None`.
fn pick_list<T: Clone>(flags: &[T], configured: &[T], builtin: &[T]) -> Vec<T> {
    for candidate in [flags, configured, builtin] {
        if !candidate.is_empty() {
            return candidate.to_vec();
        }
    }
    Vec::new()
}

/// [`pick_list`], for the one field that is a map rather than a list.
fn pick_map(
    flags: &BTreeMap<String, String>,
    configured: &BTreeMap<String, String>,
    builtin: &BTreeMap<String, String>,
) -> BTreeMap<String, String> {
    for candidate in [flags, configured, builtin] {
        if !candidate.is_empty() {
            return candidate.clone();
        }
    }
    BTreeMap::new()
}

fn string(matches: &ArgMatches, id: &str) -> Option<String> {
    matches.get_one::<String>(id).cloned()
}

fn strings(matches: &ArgMatches, id: &str) -> Vec<String> {
    matches
        .get_many::<String>(id)
        .map(|values| values.cloned().collect())
        .unwrap_or_default()
}

fn selection(matches: &ArgMatches) -> Option<Selection> {
    if matches.get_flag("all") {
        return Some(Selection::All);
    }
    if let Some(priority) = string(matches, "priority") {
        return Some(Selection::Priority(priority));
    }
    let names = strings(matches, "recipe-name");
    if !names.is_empty() {
        return Some(Selection::Names(names));
    }
    string(matches, "changed-files").map(Selection::ChangedFiles)
}

fn binary(matches: &ArgMatches) -> Option<BinarySource> {
    if matches.get_flag("binary-installed") {
        return Some(BinarySource::Installed);
    }
    string(matches, "binary-build").map(BinarySource::Build)
}

fn env(matches: &ArgMatches) -> Result<BTreeMap<String, String>, String> {
    let mut env = BTreeMap::new();
    for entry in strings(matches, "env") {
        let (key, value) = entry
            .split_once('=')
            .ok_or_else(|| format!("--env {entry}: expected KEY=VALUE"))?;
        if key.is_empty() {
            return Err(format!("--env {entry}: the key is empty"));
        }
        env.insert(key.to_string(), value.to_string());
    }
    Ok(env)
}

fn publishers(matches: &ArgMatches) -> Result<Vec<Publisher>, String> {
    let mut publishers: Vec<Publisher> = strings(matches, "publisher")
        .into_iter()
        .map(|name| Publisher {
            name,
            settings: BTreeMap::new(),
        })
        .collect();
    for entry in strings(matches, "publisher-setting") {
        let (name, setting) = entry
            .split_once(':')
            .ok_or_else(|| format!("--publisher-setting {entry}: expected PUBLISHER:KEY=VALUE"))?;
        let (key, value) = setting
            .split_once('=')
            .ok_or_else(|| format!("--publisher-setting {entry}: expected PUBLISHER:KEY=VALUE"))?;
        // Not auto-created: a setting for a publisher nobody asked to run is
        // either a typo in the name or a forgotten `--publisher`, and both are
        // better as a startup failure than as a publisher that silently
        // appears, or settings that silently go nowhere.
        let publisher = publishers
            .iter_mut()
            .find(|p| p.name == name)
            .ok_or_else(|| format!("--publisher-setting {entry}: no --publisher named {name:?}"))?;
        publisher
            .settings
            .insert(key.to_string(), value.to_string());
    }
    Ok(publishers)
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Parse a command line the way a consumer with no extra flags would.
    fn parse(argv: &[&str]) -> RunConfig {
        try_parse(argv).unwrap()
    }

    fn try_parse(argv: &[&str]) -> Result<RunConfig, String> {
        from_matches(&matches_of(argv))
    }

    fn matches_of(argv: &[&str]) -> ArgMatches {
        let mut full = vec!["termproof"];
        full.extend_from_slice(argv);
        clap_command().get_matches_from(full)
    }

    #[test]
    fn the_command_line_says_the_same_things_the_config_file_does() {
        // The counterpart of `the_ci_workflows_flags_are_all_expressible` in
        // the parent module: every field of the schema, said as flags.
        let c = parse(&[
            "--root",
            "some/framework/root/",
            "--repo-marker",
            "/repo/",
            "--recipe-name",
            "smoke",
            "--recipe-name",
            "plugins",
            "--exclude",
            "flaky-*",
            "--transport",
            "pty",
            "--renderer",
            "some-renderer",
            "--model",
            "some-model",
            "--effort",
            "high",
            "--binary-installed",
            "--env",
            "KEY=value",
            "--timeout-scale",
            "1.5",
            "--artifact-dir",
            "/tmp/evidence",
            "--report-path",
            "/tmp/report.md",
            "--result-json-path",
            "/tmp/results.json",
            "--publisher",
            "object-store",
            "--publisher-setting",
            "object-store:bucket=some-bucket",
            "--require-uploaded-media",
            "--require-media-publisher",
            "image-host",
        ]);
        assert_eq!(c.discovery.roots, ["some/framework/root/"]);
        assert_eq!(c.discovery.repo_marker.as_deref(), Some("/repo/"));
        assert_eq!(
            c.discovery.select,
            Some(Selection::Names(vec![
                "smoke".to_string(),
                "plugins".to_string()
            ]))
        );
        assert_eq!(c.discovery.exclude, ["flaky-*"]);
        assert_eq!(c.execution.transport.as_deref(), Some("pty"));
        assert_eq!(c.execution.renderer.as_deref(), Some("some-renderer"));
        assert_eq!(c.execution.model.as_deref(), Some("some-model"));
        assert_eq!(c.execution.effort.as_deref(), Some("high"));
        assert_eq!(c.execution.binary, Some(BinarySource::Installed));
        assert_eq!(c.execution.env["KEY"], "value");
        assert_eq!(c.execution.timeout_scale, Some(1.5));
        assert_eq!(c.output.artifact_dir.as_deref(), Some("/tmp/evidence"));
        assert_eq!(c.output.report_path.as_deref(), Some("/tmp/report.md"));
        assert_eq!(
            c.output.result_json_path.as_deref(),
            Some("/tmp/results.json")
        );
        assert_eq!(
            c.publisher("object-store").unwrap().settings["bucket"],
            "some-bucket"
        );
        assert!(c.output.require.uploaded_media);
        assert_eq!(
            c.output.require.media_publisher.as_deref(),
            Some("image-host")
        );
    }

    #[test]
    fn an_empty_command_line_asks_for_nothing() {
        // The precondition for the whole precedence: what the caller did not
        // pass has to arrive as unset, or the config file is dead.
        assert_eq!(parse(&[]), RunConfig::default());
    }

    #[test]
    fn every_way_of_selecting_recipes_has_a_flag() {
        assert_eq!(parse(&["--all"]).discovery.select, Some(Selection::All));
        assert_eq!(
            parse(&["--priority", "P0"]).discovery.select,
            Some(Selection::Priority("P0".into()))
        );
        assert_eq!(
            parse(&["--recipe-name", "a"]).discovery.select,
            Some(Selection::Names(vec!["a".to_string()]))
        );
        assert_eq!(
            parse(&["--changed-files", "/tmp/c.txt"]).discovery.select,
            Some(Selection::ChangedFiles("/tmp/c.txt".into()))
        );
    }

    #[test]
    fn a_second_way_of_selecting_is_a_usage_error() {
        // The enum cannot hold two, so neither can the command line, and clap
        // says so before this module has to rank them.
        let e = clap_command()
            .try_get_matches_from(["termproof", "--all", "--priority", "P0"])
            .unwrap_err();
        assert_eq!(e.kind(), clap::error::ErrorKind::ArgumentConflict);
    }

    #[test]
    fn a_binary_cannot_be_both_installed_and_built() {
        let e = clap_command()
            .try_get_matches_from(["termproof", "--binary-installed", "--binary-build", "D123"])
            .unwrap_err();
        assert_eq!(e.kind(), clap::error::ErrorKind::ArgumentConflict);
    }

    #[test]
    fn building_from_a_checkout_carries_the_change_id() {
        assert_eq!(
            parse(&["--binary-build", "D123"]).execution.binary,
            Some(BinarySource::Build("D123".into()))
        );
    }

    #[test]
    fn a_flag_beats_the_config_which_beats_the_builtin() {
        let builtin = RunConfig {
            execution: Execution {
                transport: Some("builtin".into()),
                renderer: Some("builtin".into()),
                ..Default::default()
            },
            ..Default::default()
        };
        let configured = RunConfig {
            execution: Execution {
                renderer: Some("configured".into()),
                ..Default::default()
            },
            ..Default::default()
        };

        let c = merge(&parse(&["--renderer", "flag"]), &configured, &builtin);
        assert_eq!(c.execution.renderer.as_deref(), Some("flag"));

        let c = merge(&parse(&[]), &configured, &builtin);
        assert_eq!(c.execution.renderer.as_deref(), Some("configured"));

        // And the field no flag and no config named still gets the built-in,
        // which is the half a caller re-deriving `pick()` per flag drops.
        assert_eq!(c.execution.transport.as_deref(), Some("builtin"));
    }

    #[test]
    fn a_flag_passed_empty_is_still_a_flag_passed() {
        // The bug this layer exists to stop being rewritten: `--renderer ''`
        // is a value the caller chose, so it beats the config. Treating it as
        // unset would be a fourth state on top of `pick`'s three, and every
        // consumer would have to remember which flags have it.
        let configured = RunConfig {
            execution: Execution {
                renderer: Some("configured".into()),
                ..Default::default()
            },
            ..Default::default()
        };
        let c = merge(
            &parse(&["--renderer", ""]),
            &configured,
            &RunConfig::default(),
        );
        assert_eq!(c.execution.renderer.as_deref(), Some(""));
    }

    #[test]
    fn a_repeatable_flag_replaces_the_configured_list_rather_than_adding_to_it() {
        let configured = RunConfig {
            discovery: Discovery {
                exclude: vec!["configured-*".to_string()],
                ..Default::default()
            },
            ..Default::default()
        };
        let c = merge(
            &parse(&["--exclude", "flag-*"]),
            &configured,
            &RunConfig::default(),
        );
        assert_eq!(c.discovery.exclude, ["flag-*"]);

        // Unset for a list is empty, so the configured list survives.
        let c = merge(&parse(&[]), &configured, &RunConfig::default());
        assert_eq!(c.discovery.exclude, ["configured-*"]);
    }

    #[test]
    fn a_passed_env_replaces_the_configured_env_wholesale() {
        let configured = RunConfig {
            execution: Execution {
                env: BTreeMap::from([("FROM_CONFIG".to_string(), "1".to_string())]),
                ..Default::default()
            },
            ..Default::default()
        };
        let c = merge(
            &parse(&["--env", "FROM_FLAG=1"]),
            &configured,
            &RunConfig::default(),
        );
        assert_eq!(c.execution.env.keys().collect::<Vec<_>>(), ["FROM_FLAG"]);
    }

    #[test]
    fn any_of_the_three_can_require_uploaded_media() {
        let required = RunConfig {
            output: Output {
                require: Requirements {
                    uploaded_media: true,
                    ..Default::default()
                },
                ..Default::default()
            },
            ..Default::default()
        };
        let off = RunConfig::default();
        assert!(
            merge(&parse(&["--require-uploaded-media"]), &off, &off)
                .output
                .require
                .uploaded_media
        );
        assert!(
            merge(&parse(&[]), &required, &off)
                .output
                .require
                .uploaded_media
        );
        assert!(
            merge(&parse(&[]), &off, &required)
                .output
                .require
                .uploaded_media
        );
        assert!(!merge(&parse(&[]), &off, &off).output.require.uploaded_media);
    }

    #[test]
    fn an_env_entry_without_a_value_says_what_it_wanted() {
        let e = try_parse(&["--env", "NOEQUALS"]).unwrap_err();
        assert!(e.contains("KEY=VALUE"), "{e}");
        let e = try_parse(&["--env", "=value"]).unwrap_err();
        assert!(e.contains("empty"), "{e}");
        // An empty *value* is legitimate: setting a variable to nothing.
        assert_eq!(parse(&["--env", "KEY="]).execution.env["KEY"], "");
    }

    #[test]
    fn publishers_keep_the_order_they_were_given() {
        let c = parse(&["--publisher", "first", "--publisher", "second"]);
        let names: Vec<&str> = c
            .output
            .publishers
            .iter()
            .map(|p| p.name.as_str())
            .collect();
        assert_eq!(names, ["first", "second"]);
    }

    #[test]
    fn a_setting_for_a_publisher_nobody_asked_for_is_an_error() {
        let e = try_parse(&[
            "--publisher",
            "object-store",
            "--publisher-setting",
            "objectstore:bucket=b",
        ])
        .unwrap_err();
        assert!(e.contains("objectstore"), "{e}");
        let e = try_parse(&["--publisher-setting", "no-colon-or-equals"]).unwrap_err();
        assert!(e.contains("PUBLISHER:KEY=VALUE"), "{e}");
    }

    #[test]
    fn a_setting_value_may_contain_the_separators() {
        // Split at the *first* colon and the *first* equals, so a URL or a
        // key=value payload survives being a setting value.
        let c = parse(&[
            "--publisher",
            "object-store",
            "--publisher-setting",
            "object-store:endpoint=https://host:9000/?a=b",
        ]);
        assert_eq!(
            c.publisher("object-store").unwrap().settings["endpoint"],
            "https://host:9000/?a=b"
        );
    }

    #[test]
    fn a_timeout_scale_that_is_not_a_number_is_a_usage_error() {
        let e = clap_command()
            .try_get_matches_from(["termproof", "--timeout-scale", "slow"])
            .unwrap_err();
        assert_eq!(e.kind(), clap::error::ErrorKind::ValueValidation);
    }

    #[test]
    fn no_flag_carries_a_default_value() {
        // The rule the whole precedence rests on, asserted structurally rather
        // than trusted: a `default_value` here would make that flag
        // indistinguishable from one the caller passed, and the config file
        // could never override it.
        for arg in clap_command().get_arguments() {
            assert!(
                arg.get_default_values().is_empty(),
                "--{} has a default value; the built-in belongs in `builtin`, not in clap",
                arg.get_id()
            );
        }
    }

    #[test]
    fn a_consumer_can_add_its_own_flags() {
        let command = augment_args(Command::new("validator"))
            .arg(Arg::new("watch").long("watch").action(ArgAction::SetTrue));
        // It is the consumer's command that comes back, not one of ours with
        // the consumer's flags bolted on — the name, and with it the about,
        // version and subcommands, is still theirs.
        assert_eq!(command.get_name(), "validator");
        let matches = command.get_matches_from(["validator", "--watch", "--priority", "P0"]);
        assert!(matches.get_flag("watch"));
        assert_eq!(
            from_matches(&matches).unwrap().discovery.select,
            Some(Selection::Priority("P0".into()))
        );
    }

    #[test]
    fn the_run_config_flag_reads_the_file_it_names() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("run.yaml");
        std::fs::write(&path, "execution:\n  renderer: from-file\n").unwrap();
        let path = path.to_str().unwrap();

        let c = resolve(&matches_of(&["--run-config", path]), &RunConfig::default()).unwrap();
        assert_eq!(c.execution.renderer.as_deref(), Some("from-file"));

        // And the flag still wins over the file it was read from.
        let c = resolve(
            &matches_of(&["--run-config", path, "--renderer", "from-flag"]),
            &RunConfig::default(),
        )
        .unwrap();
        assert_eq!(c.execution.renderer.as_deref(), Some("from-flag"));
    }

    #[test]
    fn a_missing_run_config_says_which_file() {
        let e = resolve(
            &matches_of(&["--run-config", "/nonexistent/run.yaml"]),
            &RunConfig::default(),
        )
        .unwrap_err();
        assert!(e.contains("/nonexistent/run.yaml"), "{e}");
    }

    #[test]
    fn with_no_run_config_the_configured_layer_is_simply_empty() {
        assert_eq!(configured(&matches_of(&[])).unwrap(), RunConfig::default());
    }

    #[test]
    fn the_bare_command_and_an_augmented_one_carry_the_same_flags() {
        // `clap_command` is `augment_args` over a bare command, so this cannot
        // drift — which is the point of it not being a second builder.
        let bare: Vec<_> = clap_command()
            .get_arguments()
            .map(|a| a.get_id().to_string())
            .collect();
        let augmented: Vec<_> = augment_args(Command::new("other"))
            .get_arguments()
            .map(|a| a.get_id().to_string())
            .collect();
        assert_eq!(bare, augmented);
    }

    #[test]
    fn the_command_is_internally_consistent() {
        // clap's own audit of ids, groups and conflicts. It panics rather than
        // returning, and only in debug builds, which is where tests run.
        clap_command().debug_assert();
    }
}
