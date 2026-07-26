from __future__ import annotations

import argparse
import shlex
from pathlib import Path

from .agent_driven import CodexCliAgentRunner
from .build_info import BuildInfo
from .config import VerifierConfig, load_config
from .registry import load_recipes, select_recipes
from .renderer import selected_renderers
from .runner import VerificationRunner
from .scaffold import write_recipe_pack


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="termproof")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run", help="run a verification recipe")
    run_parser.add_argument("recipes", nargs="+", type=Path)
    run_parser.add_argument("--out", type=Path, default=Path(".termproof/runs"))
    run_parser.add_argument("--video", action="store_true")
    run_parser.add_argument("--no-video", action="store_true")
    run_parser.add_argument("--video-fps", type=int, default=60)
    run_parser.add_argument("--priority")
    run_parser.add_argument("--recipe-name", action="append", dest="recipe_names")
    run_parser.add_argument("--renderer", default="default")
    run_parser.add_argument("--operator-command")
    run_parser.add_argument("--config", type=Path, default=None,
                            help="path to a termproof config YAML file")
    run_parser.add_argument("--reporter", default="markdown",
                            help="reporter to use (default: markdown)")
    run_parser.add_argument("--xml-path", type=Path, default=None,
                            help="write JUnit XML report to this path (implies --reporter junit_xml)")
    run_parser.add_argument("--screen-renderer", default="svg",
                            help="screen renderer to use (default: svg)")
    run_parser.add_argument("--video-backend", default="agg_ffmpeg",
                            help="video backend to use (default: agg_ffmpeg)")
    list_parser = subparsers.add_parser("list", help="list recipes")
    list_parser.add_argument("recipes", nargs="+", type=Path)
    list_parser.add_argument("--priority")
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
    demo_parser.add_argument("--video-fps", type=int, default=60)
    demo_parser.add_argument("--config", type=Path, default=None,
                             help="path to a termproof config YAML file")
    demo_parser.add_argument("--reporter", default="markdown",
                             help="reporter to use (default: markdown, also: junit_xml)")
    demo_parser.add_argument("--xml-path", type=Path, default=None,
                             help="additional path to write JUnit XML report")
    demo_parser.add_argument("--screen-renderer", default="svg",
                             help="screen renderer (default: svg)")
    demo_parser.add_argument("--video-backend", default="agg_ffmpeg",
                             help="video backend (default: agg_ffmpeg)")
    args = parser.parse_args(argv)

    if args.command == "run":
        config = _resolve_config(args)
        recipes = select_recipes(
            load_recipes(args.recipes),
            priority=args.priority,
            names=args.recipe_names,
        )
        # --xml-path implies --reporter junit_xml
        reporter_name = args.reporter
        if args.xml_path and reporter_name == "markdown":
            reporter_name = "junit_xml"
        results = []
        agent_runner = None
        if args.operator_command:
            agent_runner = CodexCliAgentRunner(command=shlex.split(args.operator_command))
        runner = VerificationRunner(agent_runner, config=config)
        for recipe in recipes:
            for renderer_name, renderer_argv in selected_renderers(recipe, args.renderer):
                results.append(
                    runner.run(
                        recipe,
                        out_dir=args.out,
                        render_video=args.video and not args.no_video,
                        video_fps=args.video_fps,
                        renderer=renderer_name,
                        renderer_argv=renderer_argv,
                        screen_renderer_name=args.screen_renderer,
                        video_backend_name=args.video_backend,
                    )
                )
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
