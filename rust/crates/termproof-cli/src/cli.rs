//! CLI definitions mirroring `termproof/cli.py`.
//!
//! Every command, flag, and exit code is part of the public compatibility
//! contract frozen in RUST-001. This module builds the `clap::Command` tree
//! without proc macros so the build does not require `proc-macro2` build
//! scripts under sandbox.

use clap::{value_parser, Arg, ArgAction, Command};
use std::path::PathBuf;

// ---------------------------------------------------------------------------
// Exit codes (frozen from Python oracle)
// ---------------------------------------------------------------------------

/// Canonical exit codes preserved from the Python oracle.
pub mod exit_code {
    pub const SUCCESS: i32 = 0;
    pub const FAILURE: i32 = 1;
    pub const USAGE: i32 = 2;
}

/// Build the top-level `termproof` command with all subcommands and flags.
///
/// Mirrors `termproof/cli.py` argument structure. Help text may improve, but
/// flags and subcommand names must remain stable for scripts.
pub fn build_cli() -> Command {
    Command::new("termproof")
        .version(env!("CARGO_PKG_VERSION"))
        .about("Evidence-first verification for terminal and TUI applications")
        .propagate_version(true)
        .subcommand(build_run_command())
        .subcommand(build_list_command())
        .subcommand(build_validate_command())
        .subcommand(build_plugins_command())
        .subcommand(build_init_command())
        .subcommand(build_demo_command())
}

fn build_run_command() -> Command {
    Command::new("run")
        .about("run a verification recipe")
        .arg(
            Arg::new("recipes")
                .required(true)
                .num_args(1..)
                .value_parser(value_parser!(PathBuf))
                .help("Recipe files or directories"),
        )
        .arg(
            Arg::new("out")
                .long("out")
                .value_parser(value_parser!(PathBuf))
                .default_value(".termproof/runs")
                .help("Output directory for evidence"),
        )
        .arg(
            Arg::new("video")
                .long("video")
                .action(ArgAction::SetTrue)
                .help("Render video evidence"),
        )
        .arg(
            Arg::new("no-video")
                .long("no-video")
                .action(ArgAction::SetTrue)
                .help("Disable video rendering"),
        )
        .arg(
            Arg::new("video-fps")
                .long("video-fps")
                .value_parser(value_parser!(u32))
                .default_value("60")
                .help("Video frames per second"),
        )
        .arg(
            Arg::new("priority")
                .long("priority")
                .help("Filter by priority"),
        )
        .arg(
            Arg::new("recipe-name")
                .long("recipe-name")
                .action(ArgAction::Append)
                .help("Filter by recipe name (repeatable)"),
        )
        .arg(
            Arg::new("parallel")
                .long("parallel")
                .value_parser(value_parser!(u32))
                .default_value("1")
                .help("Number of recipes to run concurrently"),
        )
        .arg(
            Arg::new("renderer")
                .long("renderer")
                .default_value("default")
                .help("Renderer to use"),
        )
        .arg(
            Arg::new("operator-command")
                .long("operator-command")
                .help("Operator (agent) command"),
        )
        .arg(
            Arg::new("config")
                .long("config")
                .value_parser(value_parser!(PathBuf))
                .help("Path to a termproof config YAML file"),
        )
        .arg(
            Arg::new("reporter")
                .long("reporter")
                .default_value("markdown")
                .help("Reporter to use (default: markdown)"),
        )
        .arg(
            Arg::new("xml-path")
                .long("xml-path")
                .value_parser(value_parser!(PathBuf))
                .help("Write JUnit XML report to this path"),
        )
        .arg(
            Arg::new("screen-renderer")
                .long("screen-renderer")
                .default_value("svg")
                .help("Screen renderer to use (default: svg)"),
        )
        .arg(
            Arg::new("video-backend")
                .long("video-backend")
                .default_value("agg_ffmpeg")
                .help("Video backend to use"),
        )
        .arg(
            Arg::new("diff")
                .long("diff")
                .action(ArgAction::SetTrue)
                .help("Compare final screenshots against baselines"),
        )
        .arg(
            Arg::new("baseline-dir")
                .long("baseline-dir")
                .value_parser(value_parser!(PathBuf))
                .default_value(".termproof/baselines")
                .help("Baseline root for --diff"),
        )
        .arg(
            Arg::new("update-baselines")
                .long("update-baselines")
                .action(ArgAction::SetTrue)
                .help("Write current final screenshots as visual baselines"),
        )
        .arg(
            Arg::new("skip-unchanged")
                .long("skip-unchanged")
                .action(ArgAction::SetTrue)
                .help("Reuse cached passing results for unchanged recipes"),
        )
        .arg(
            Arg::new("cache-dir")
                .long("cache-dir")
                .value_parser(value_parser!(PathBuf))
                .default_value(".termproof/cache")
                .help("Cache root for --skip-unchanged"),
        )
}

fn build_list_command() -> Command {
    Command::new("list")
        .about("list recipes")
        .arg(
            Arg::new("recipes")
                .required(true)
                .num_args(1..)
                .value_parser(value_parser!(PathBuf)),
        )
        .arg(Arg::new("priority").long("priority"))
}

fn build_validate_command() -> Command {
    Command::new("validate")
        .about("validate recipe files")
        .arg(
            Arg::new("recipes")
                .required(true)
                .num_args(1..)
                .value_parser(value_parser!(PathBuf)),
        )
        .arg(
            Arg::new("config")
                .long("config")
                .value_parser(value_parser!(PathBuf)),
        )
}

fn build_plugins_command() -> Command {
    Command::new("plugins")
        .about("manage TermProof plugins")
        .subcommand_required(true)
        .subcommand(
            Command::new("list").about("list configured plugins").arg(
                Arg::new("config")
                    .long("config")
                    .value_parser(value_parser!(PathBuf)),
            ),
        )
        .subcommand(
            Command::new("search")
                .about("search community plugins")
                .arg(Arg::new("query").required(true))
                .arg(
                    Arg::new("registry")
                        .long("registry")
                        .value_parser(value_parser!(PathBuf))
                        .default_value("docs/plugins.md"),
                ),
        )
        .subcommand(
            Command::new("install")
                .about("install a community plugin")
                .arg(Arg::new("name").required(true))
                .arg(
                    Arg::new("registry")
                        .long("registry")
                        .value_parser(value_parser!(PathBuf))
                        .default_value("docs/plugins.md"),
                )
                .arg(
                    Arg::new("dry-run")
                        .long("dry-run")
                        .action(ArgAction::SetTrue),
                ),
        )
}

fn build_init_command() -> Command {
    Command::new("init")
        .about("create a reusable recipe pack")
        .arg(
            Arg::new("path")
                .required(true)
                .value_parser(value_parser!(PathBuf)),
        )
        .arg(Arg::new("name").long("name").required(true))
        .arg(
            Arg::new("command")
                .long("command")
                .required(true)
                .help("Command the recipe launches"),
        )
        .arg(
            Arg::new("non-pty")
                .long("non-pty")
                .action(ArgAction::SetTrue),
        )
        .arg(Arg::new("priority").long("priority").default_value("P2"))
        .arg(
            Arg::new("cols")
                .long("cols")
                .value_parser(value_parser!(u32))
                .default_value("100"),
        )
        .arg(
            Arg::new("rows")
                .long("rows")
                .value_parser(value_parser!(u32))
                .default_value("30"),
        )
        .arg(Arg::new("force").long("force").action(ArgAction::SetTrue))
}

fn build_demo_command() -> Command {
    Command::new("demo")
        .about("run a self-contained demo exercising all features")
        .arg(
            Arg::new("out")
                .long("out")
                .value_parser(value_parser!(PathBuf))
                .default_value(".termproof/demo")
                .help("Output directory for demo evidence"),
        )
        .arg(
            Arg::new("no-open")
                .long("no-open")
                .action(ArgAction::SetTrue),
        )
        .arg(Arg::new("video").long("video").action(ArgAction::SetTrue))
        .arg(
            Arg::new("video-fps")
                .long("video-fps")
                .value_parser(value_parser!(u32))
                .default_value("60"),
        )
        .arg(
            Arg::new("config")
                .long("config")
                .value_parser(value_parser!(PathBuf)),
        )
        .arg(
            Arg::new("reporter")
                .long("reporter")
                .default_value("markdown"),
        )
        .arg(
            Arg::new("xml-path")
                .long("xml-path")
                .value_parser(value_parser!(PathBuf)),
        )
        .arg(
            Arg::new("screen-renderer")
                .long("screen-renderer")
                .default_value("svg"),
        )
        .arg(
            Arg::new("video-backend")
                .long("video-backend")
                .default_value("agg_ffmpeg"),
        )
}

/// Validate combinational constraints.
///
/// Mirrors guards in `termproof/cli.py::main`.
pub fn validate_run_constraints(
    parallel: u32,
    skip_unchanged: bool,
    diff: bool,
    update_baselines: bool,
) -> Result<(), String> {
    if parallel < 1 {
        return Err("--parallel must be >= 1".to_string());
    }
    if skip_unchanged && (diff || update_baselines) {
        return Err(
            "--skip-unchanged cannot be combined with --diff or --update-baselines".to_string(),
        );
    }
    Ok(())
}
