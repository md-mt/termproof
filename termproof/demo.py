"""Demo command implementation — self-contained, exercises all features."""
from __future__ import annotations

import sys
import webbrowser
from pathlib import Path

from .config import VerifierConfig, load_config
from .models import CommandSpec, Recipe
from .runner import VerificationRunner


def build_demo_recipe(out_dir: Path) -> Recipe:
    """Build a demo recipe that exercises every step and assertion type."""
    out_dir = out_dir.resolve()
    export_path = out_dir / "demo_export.txt"
    return Recipe(
        name="termproof-demo",
        description="Self-contained demo exercising all TermProof step types and assertions",
        intent="Demonstrate TermProof verification with a built-in TUI",
        priority="P0",
        execution="scripted",
        determinism="deterministic",
        checks=[
            "demo TUI opens and shows prompt",
            "dashboard step completes",
            "filter step completes via send_text + press",
            "export creates artifact file",
            "all assertions verified",
        ],
        command=CommandSpec(
            argv=[sys.executable, "-m", "termproof.demo_tui", "--out", str(out_dir)],
            pty=True,
        ),
        timeout_seconds=30,
        cols=100,
        rows=30,
        steps=[
            {"name": "wait for demo prompt", "action": "wait_for_text", "text": "demo>", "timeout_seconds": 5},
            {"name": "wait for stable", "action": "wait_for_idle", "stable_seconds": 0.3, "timeout_seconds": 5},
            {"name": "open dashboard", "action": "send_line", "text": "dashboard"},
            {"name": "wait for dashboard ready", "action": "wait_for_text", "text": "DASHBOARD READY", "timeout_seconds": 5},
            {
                "name": "capture version via regex",
                "action": "wait_for_regex",
                "pattern": r"version: (?P<ver>\d+\.\d+\.\d+)",
                "timeout_seconds": 3,
            },
            {"name": "type filter via send_text", "action": "send_text", "text": "filter"},
            {"name": "submit with enter", "action": "press", "key": "enter"},
            {"name": "wait for filter ready", "action": "wait_for_text", "text": "FILTER READY", "timeout_seconds": 5},
            {"name": "brief pause", "action": "sleep", "seconds": 0.5},
            {"name": "export report", "action": "send_line", "text": "export"},
            {"name": "wait for export ready", "action": "wait_for_text", "text": "EXPORT READY", "timeout_seconds": 5},
            {
                "name": "capture export id",
                "action": "wait_for_regex",
                "pattern": r"export id: (?P<id>\d+)",
                "timeout_seconds": 3,
            },
            {"name": "close demo", "action": "send_line", "text": "exit"},
            {"name": "wait for completion", "action": "wait_for_text", "text": "GENERIC DEMO COMPLETE", "timeout_seconds": 5},
        ],
        assertions=[
            {"name": "dashboard was ready", "type": "output_contains", "value": "DASHBOARD READY"},
            {"name": "version present", "type": "output_contains", "value": "2.0.1"},
            {"name": "filter was ready", "type": "output_contains", "value": "FILTER READY"},
            {"name": "export was ready", "type": "output_contains", "value": "EXPORT READY"},
            {"name": "no python traceback", "type": "output_not_contains", "value": "Traceback"},
            {"name": "screen shows completion", "type": "screen_contains", "value": "GENERIC DEMO COMPLETE"},
            {"name": "screen has no failure", "type": "screen_not_contains", "value": "FAILURE"},
            {"name": "exit code ok", "type": "exit_code", "value": 0},
            {"name": "export file exists", "type": "file_exists", "value": str(export_path)},
            {"name": "export file contains id", "type": "file_contains", "path": str(export_path), "value": "id=123"},
        ],
        expect_exit_code=0,
    )


def _safe_generate_report(runner: VerificationRunner, recipe: Recipe, result, reporter_name: str, out_dir: Path) -> Path | None:
    """Generate report using requested reporter, write to appropriate file, return path."""
    try:
        reporter = runner.reporter_registry.get(reporter_name)
    except KeyError:
        print(f"Warning: unknown reporter {reporter_name!r}, falling back to markdown")
        reporter = runner.reporter_registry.get("markdown")
        reporter_name = "markdown"

    from .build_info import BuildInfo

    build_info = BuildInfo.from_command(recipe.command.argv)
    report = reporter.generate([result], build_info=build_info)

    if reporter_name == "junit_xml":
        junit_path = out_dir / "junit.xml"
        junit_path.write_text(report, encoding="utf-8")
        # supplement: always generate a markdown version for browser open
        try:
            md_reporter = runner.reporter_registry.get("markdown")
            md_report = md_reporter.generate([result], build_info=build_info)
            (out_dir / "latest-report.md").write_text(md_report, encoding="utf-8")
        except Exception:
            (out_dir / "latest-report.md").write_text(report, encoding="utf-8")
        return junit_path
    else:
        report_path = out_dir / "latest-report.md"
        report_path.write_text(report, encoding="utf-8")
        return report_path


def run_demo(
    out_dir: Path,
    no_open: bool,
    render_video: bool = False,
    video_fps: int | None = None,
    reporter_name: str = "markdown",
    screen_renderer_name: str = "svg",
    video_backend_name: str = "agg_ffmpeg",
    config_path: Path | None = None,
    xml_path: Path | None = None,
) -> int:
    """Execute the demo recipe and report evidence location."""
    out_dir.mkdir(parents=True, exist_ok=True)

    if config_path:
        config = load_config(config_path=config_path.resolve())
    else:
        # Default demo uses builtin config only — avoids ambient project/user
        # config contamination for a self-contained demo.
        config = VerifierConfig.builtin()
    if video_fps is None:
        video_fps = config.evidence.video.fps

    recipe = build_demo_recipe(out_dir=out_dir)
    runner = VerificationRunner(config=config)

    print("Running TermProof demo TUI...")
    print(f"  Recipe: {recipe.name}")
    print(f"  Out dir: {out_dir.resolve()}")
    print(f"  Reporter: {reporter_name}")
    print("")

    result = runner.run(
        recipe,
        out_dir=out_dir,
        render_video=render_video,
        video_fps=video_fps,
        screen_renderer_name=screen_renderer_name,
        video_backend_name=video_backend_name,
    )

    primary_report_path = _safe_generate_report(runner, recipe, result, reporter_name, out_dir)

    # If --xml-path is explicit, also write a JUnit XML there regardless of
    # the primary reporter choice.
    if xml_path:
        xml_path.parent.mkdir(parents=True, exist_ok=True)
        from .build_info import BuildInfo as _BI
        bi = _BI.from_command(recipe.command.argv)
        junit_reporter = runner.reporter_registry.get("junit_xml")
        xml_report = junit_reporter.generate([result], build_info=bi)
        xml_path.write_text(xml_report, encoding="utf-8")
        print(f"xml report: {xml_path}")

    verdict = "PASS" if result.passed else "FAIL"
    print("")
    print(f"Demo result: {verdict}")
    print(f"Score: {result.score:.2f}")
    print(f"Duration: {result.duration_seconds:.2f}s")
    print("")
    print("Evidence generated:")
    for key, path in result.artifacts.items():
        print(f"  {key}: {path}")
    if primary_report_path:
        print(f"  report: {primary_report_path}")
    if reporter_name == "junit_xml":
        md_path = out_dir / "latest-report.md"
        if md_path.exists():
            print(f"  markdown supplement: {md_path}")

    print("")
    print("Steps executed:")
    for step in result.steps:
        status = "PASS" if step.passed else "FAIL"
        print(f"  {status} {step.name}: {step.detail}")

    print("")
    print("Assertions:")
    for assertion in result.assertions:
        status = "PASS" if assertion.passed else "FAIL"
        print(f"  {status} {assertion.name}: {assertion.detail}")

    if not no_open:
        # For JUnit XML reporter, open the markdown supplement in the
        # browser — raw XML is not human-readable in a web browser.
        if reporter_name == "junit_xml":
            md_path = out_dir / "latest-report.md"
            if md_path.exists():
                try:
                    file_url = md_path.resolve().as_uri()
                    print("")
                    if webbrowser.open(file_url):
                        print(f"Opened markdown supplement: {file_url}")
                    else:
                        print(f"Report available at: {md_path}")
                except Exception:
                    print(f"Markdown supplement available at: {md_path}")
            else:
                print("")
                print(f"Report available at: {primary_report_path}")
        elif primary_report_path and primary_report_path.exists():
            try:
                file_url = primary_report_path.resolve().as_uri()
                print("")
                if webbrowser.open(file_url):
                    print(f"Opened report: {file_url}")
                else:
                    print(f"Report available at: {primary_report_path}")
            except Exception:
                print(f"Report available at: {primary_report_path}")
        if "screenshot" in result.artifacts:
            print(f"Screenshot: {result.artifacts['screenshot']}")
    else:
        print("")
        print(f"Evidence directory: {out_dir.resolve()}")

    return 0 if result.passed else 1
