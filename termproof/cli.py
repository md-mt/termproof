from __future__ import annotations

import argparse
import shlex
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .agent_driven import CodexCliAgentRunner
from .build_info import BuildInfo
from .config import VerifierConfig, load_config
from .evidence import write_result_files
from .recipe_schema import has_errors, validate_recipe_file
from .registry import find_recipe_files, load_recipes, select_recipes
from .renderer import selected_renderers
from .run_cache import load_cached_result, store_cached_result
from .runner import VerificationRunner
from .scaffold import write_recipe_pack
from .visual_diff import apply_visual_diff


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="termproof")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run", help="run a verification recipe")
    run_parser.add_argument("recipes", nargs="+", type=Path)
    run_parser.add_argument("--out", type=Path, default=Path(".termproof/runs"))
    run_parser.add_argument("--video", action="store_true")
    run_parser.add_argument("--no-video", action="store_true")
    run_parser.add_argument("--video-fps", type=int, default=None,
                            help="video frame rate; overrides evidence.video.fps (default: 60)")
    run_parser.add_argument("--priority")
    run_parser.add_argument("--recipe-name", action="append", dest="recipe_names")
    run_parser.add_argument("--parallel", type=int, default=1,
                            help="number of recipes to run concurrently")
    run_parser.add_argument("--renderer", default="default")
    run_parser.add_argument("--operator-command")
    run_parser.add_argument("--config", type=Path, default=None,
                            help="path to a termproof config YAML file")
    run_parser.add_argument("--reporter", default="markdown",
                            help="reporter to use (default: markdown)")
    run_parser.add_argument("--xml-path", type=Path, default=None,
                            help="write JUnit XML report to this path (implies --reporter junit_xml)")
    run_parser.add_argument("--screen-renderer", default="svg",
                            help="screen renderer to use (default: svg, also: png, png_rsvg)")
    run_parser.add_argument("--video-backend", default="agg_ffmpeg",
                            help="video backend to use (default: agg_ffmpeg)")
    run_parser.add_argument("--diff", action="store_true",
                            help="compare final screenshots against baselines")
    run_parser.add_argument("--baseline-dir", type=Path, default=Path(".termproof/baselines"),
                            help="baseline root for --diff")
    run_parser.add_argument("--update-baselines", action="store_true",
                            help="write current final screenshots as visual baselines")
    run_parser.add_argument("--skip-unchanged", action="store_true",
                            help="reuse cached passing results for unchanged recipes")
    run_parser.add_argument("--cache-dir", type=Path, default=Path(".termproof/cache"),
                            help="cache root for --skip-unchanged")
    list_parser = subparsers.add_parser("list", help="list recipes")
    list_parser.add_argument("recipes", nargs="+", type=Path)
    list_parser.add_argument("--priority")
    validate_parser = subparsers.add_parser("validate", help="validate recipe files")
    validate_parser.add_argument("recipes", nargs="+", type=Path)
    validate_parser.add_argument("--config", type=Path, default=None,
                                 help="path to a termproof config YAML file")
    plugins_parser = subparsers.add_parser("plugins", help="manage TermProof plugins")
    plugins_subparsers = plugins_parser.add_subparsers(dest="plugins_command", required=True)
    plugins_list = plugins_subparsers.add_parser("list", help="list configured plugins")
    plugins_list.add_argument("--config", type=Path, default=None,
                              help="path to a termproof config YAML file")
    plugins_search = plugins_subparsers.add_parser("search", help="search community plugins")
    plugins_search.add_argument("query")
    plugins_search.add_argument("--registry", type=Path, default=Path("docs/plugins.md"))
    plugins_install = plugins_subparsers.add_parser("install", help="install a community plugin")
    plugins_install.add_argument("name")
    plugins_install.add_argument("--registry", type=Path, default=Path("docs/plugins.md"))
    plugins_install.add_argument("--dry-run", action="store_true")
    init_parser = subparsers.add_parser("init", help="create a reusable recipe pack")
    init_parser.add_argument("path", type=Path)
    init_parser.add_argument("--name", required=True)
    init_parser.add_argument("--command", required=True, dest="target_command")
    init_parser.add_argument("--non-pty", action="store_true")
    init_parser.add_argument("--priority", default="P2")
    init_parser.add_argument("--cols", type=int, default=100)
    init_parser.add_argument("--rows", type=int, default=30)
    init_parser.add_argument("--force", action="store_true")
    # demo subcommand
    demo_parser = subparsers.add_parser("demo", help="run a self-contained demo exercising all features")
    demo_parser.add_argument("--out", type=Path, default=Path(".termproof/demo"),
                             help="output directory for demo evidence (default: .termproof/demo)")
    demo_parser.add_argument("--no-open", action="store_true",
                             help="do not attempt to open generated report in browser")
    demo_parser.add_argument("--video", action="store_true",
                             help="render video evidence if video backend available")
    demo_parser.add_argument("--video-fps", type=int, default=None,
                             help="video frame rate; overrides evidence.video.fps (default: 60)")
    demo_parser.add_argument("--config", type=Path, default=None,
                             help="path to a termproof config YAML file")
    demo_parser.add_argument("--reporter", default="markdown",
                             help="reporter to use (default: markdown, also: junit_xml)")
    demo_parser.add_argument("--xml-path", type=Path, default=None,
                             help="additional path to write JUnit XML report")
    demo_parser.add_argument("--screen-renderer", default="svg",
                             help="screen renderer (default: svg, also: png, png_rsvg)")
    demo_parser.add_argument("--video-backend", default="agg_ffmpeg",
                             help="video backend (default: agg_ffmpeg)")
    args = parser.parse_args(argv)

    if args.command == "run":
        if args.parallel < 1:
            print("--parallel must be >= 1")
            return 2
        if args.skip_unchanged and (args.diff or args.update_baselines):
            print("--skip-unchanged cannot be combined with --diff or --update-baselines")
            return 2
        config = _resolve_config(args)
        # The flag is the last step of the same cascade: builtin, then user,
        # project and explicit config files, then the command line.
        if args.video_fps is None:
            args.video_fps = config.evidence.video.fps
        recipes = select_recipes(
            load_recipes(args.recipes),
            priority=args.priority,
            names=args.recipe_names,
        )
        # --xml-path implies --reporter junit_xml
        reporter_name = args.reporter
        if args.xml_path and reporter_name == "markdown":
            reporter_name = "junit_xml"
        run_items = [
            (recipe, renderer_name, renderer_argv)
            for recipe in recipes
            for renderer_name, renderer_argv in selected_renderers(recipe, args.renderer)
        ]
        runner = VerificationRunner(_agent_runner(args), config=config)
        if args.parallel == 1:
            results = [
                _run_item(runner, item, args)
                for item in run_items
            ]
        else:
            with ThreadPoolExecutor(max_workers=args.parallel) as executor:
                results = list(
                    executor.map(
                        lambda item: _run_item(
                            VerificationRunner(_agent_runner(args), config=config),
                            item,
                            args,
                        ),
                        run_items,
                    )
                )
        if args.diff or args.update_baselines:
            results = [
                apply_visual_diff(
                    result,
                    args.baseline_dir,
                    update=args.update_baselines,
                )
                for result in results
            ]
            for result in results:
                screenshot = result.artifacts.get("screenshot")
                if screenshot:
                    write_result_files(Path(screenshot).parent, result)
        build_info = BuildInfo.from_command(recipes[0].command.argv) if recipes else None
        reporter = runner.reporter_registry.get(reporter_name)
        report = reporter.generate(results, build_info=build_info)
        args.out.mkdir(parents=True, exist_ok=True)
        ext = ".xml" if reporter_name == "junit_xml" else ".md"
        report_path = args.out / f"latest-report{ext}"
        report_path.write_text(report, encoding="utf-8")
        # Write to explicit --xml-path if provided
        if args.xml_path:
            args.xml_path.parent.mkdir(parents=True, exist_ok=True)
            args.xml_path.write_text(report, encoding="utf-8")
            print(f"xml report: {args.xml_path}")
        passed = sum(1 for result in results if result.passed)
        print(f"{passed}/{len(results)} passed")
        print(f"report: {report_path}")
        for result in results:
            verdict = "PASS" if result.passed else "FAIL"
            video = result.artifacts.get("video", "-")
            print(f"{verdict} {result.recipe_name} [{result.renderer}] video: {video}")
        return 0 if results and all(result.passed for result in results) else 1
    if args.command == "list":
        recipes = select_recipes(load_recipes(args.recipes), priority=args.priority)
        for recipe in recipes:
            print(f"{recipe.name}\t{recipe.priority}\t{recipe.execution}\t{recipe.description}")
        return 0
    if args.command == "validate":
        config = _resolve_config(args)
        paths = find_recipe_files(args.recipes)
        if not paths:
            print("no recipe files found")
            return 1
        failed = False
        for path in paths:
            issues = validate_recipe_file(path, config)
            if not issues:
                print(f"PASS {path}")
                continue
            for issue in issues:
                label = issue.severity.upper()
                print(f"{label} {path}:{issue.path}: {issue.message}")
            failed = failed or has_errors(issues)
        return 1 if failed else 0
    if args.command == "plugins":
        from .plugins_cli import (
            install_community_plugin,
            installed_plugins,
            search_community_plugins,
        )

        if args.plugins_command == "list":
            for plugin in installed_plugins(_resolve_config(args)):
                print(f"{plugin.category}\t{plugin.name}\t{plugin.target}")
            return 0
        if args.plugins_command == "search":
            matches = search_community_plugins(args.query, args.registry)
            if not matches:
                print("no plugins found")
                return 0
            for match in matches:
                print(
                    f"{match.name}\t{match.description}\t{match.install}\t{match.author}"
                )
            return 0
        if args.plugins_command == "install":
            code, detail = install_community_plugin(
                args.name,
                args.registry,
                dry_run=args.dry_run,
            )
            print(detail)
            return code
    if args.command == "init":
        try:
            recipe_path = write_recipe_pack(
                args.path,
                args.name,
                args.target_command,
                not args.non_pty,
                args.priority,
                args.cols,
                args.rows,
                force=args.force,
            )
        except FileExistsError as error:
            print(f"recipe already exists: {error}")
            return 1
        print(f"created recipe: {recipe_path}")
        return 0
    if args.command == "demo":
        from .demo import run_demo
        return run_demo(
            out_dir=args.out,
            no_open=args.no_open,
            render_video=args.video,
            video_fps=args.video_fps,
            reporter_name=args.reporter,
            screen_renderer_name=args.screen_renderer,
            video_backend_name=args.video_backend,
            config_path=args.config,
            xml_path=args.xml_path,
        )
    return 2


def _resolve_config(args: argparse.Namespace) -> VerifierConfig:
    if args.config:
        return load_config(config_path=args.config.resolve())
    return load_config()


def _agent_runner(args: argparse.Namespace) -> CodexCliAgentRunner | None:
    if not args.operator_command:
        return None
    return CodexCliAgentRunner(command=shlex.split(args.operator_command))


def _run_item(
    runner: VerificationRunner,
    item: tuple,
    args: argparse.Namespace,
):
    recipe, renderer_name, renderer_argv = item
    render_video = args.video and not args.no_video
    if args.skip_unchanged:
        cached = load_cached_result(
            args.cache_dir,
            recipe,
            renderer_name,
            renderer_argv,
            out_dir=args.out,
            screen_renderer=args.screen_renderer,
            video_backend=args.video_backend,
            render_video=render_video,
            video_fps=args.video_fps,
            evidence=runner.config.evidence,
        )
        if cached is not None:
            return cached
    result = runner.run(
        recipe,
        out_dir=args.out,
        render_video=render_video,
        video_fps=args.video_fps,
        renderer=renderer_name,
        renderer_argv=renderer_argv,
        screen_renderer_name=args.screen_renderer,
        video_backend_name=args.video_backend,
    )
    if args.skip_unchanged:
        store_cached_result(
            args.cache_dir,
            recipe,
            renderer_name,
            renderer_argv,
            result,
            out_dir=args.out,
            screen_renderer=args.screen_renderer,
            video_backend=args.video_backend,
            render_video=render_video,
            video_fps=args.video_fps,
            evidence=runner.config.evidence,
        )
    return result
