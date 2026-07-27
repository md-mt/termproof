from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .before_after import build_before_after
from .models import AssertionResult, RunResult, StepResult

DEFAULT_RECEIPT = Path("docs/ci/evidence-receipt.json")


def load_receipt(path: Path = DEFAULT_RECEIPT) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_target(target_name: str, repo: Path, out: Path | None = None,
               receipt_path: Path = DEFAULT_RECEIPT) -> int:
    receipt = load_receipt(receipt_path)
    target = receipt["targets"][target_name]
    out_dir = out or Path(target["out"])
    receipt_out = out_dir if out_dir.is_absolute() else repo / out_dir
    cmd = ["uv", "run", "termproof", "run", *target["recipes"]]
    if target.get("video"):
        cmd.append("--video")
    if "video_fps" in target:
        cmd.extend(["--video-fps", str(target["video_fps"])])
    cmd.extend(["--out", str(out_dir)])
    completed = subprocess.run(cmd, cwd=repo)
    _normalize_artifact_paths(receipt_out)
    _copy_receipt(receipt_path, receipt_out)
    return completed.returncode


def compose_pr_comment(base_dir: Path, head_dir: Path, run_url: str,
                       base_label: str = "base", head_label: str = "head",
                       receipt_path: Path = DEFAULT_RECEIPT) -> str:
    receipt = load_receipt(receipt_path)
    ci_target = receipt["targets"]["ci"]
    release_target = receipt["targets"]["release"]
    marker = receipt["pr_comment"]["marker"]
    before_after = build_before_after(
        load_results(base_dir),
        load_results(head_dir),
    )
    base_report = _truncate(_read_report(base_dir), 18000)
    head_report = _truncate(_read_report(head_dir), 26000)
    return "\n".join(
        [
            marker,
            "## TermProof CI Report",
            "",
            f"Run: [{run_url}]({run_url})",
            "",
            f"PR evidence artifact: `{ci_target['artifact_name']}` in this workflow run.",
            f"Release destination: GitHub Release asset `{release_target['archive_name']}`.",
            "Download the artifact/archive to inspect linked evidence files.",
            "",
            "<details open><summary>Behavioral delta</summary>",
            "",
            before_after.to_markdown().rstrip(),
            "",
            "</details>",
            "",
            f"<details><summary>Before: base commit {base_label}</summary>",
            "",
            base_report,
            "",
            "</details>",
            "",
            f"<details open><summary>After: head commit {head_label}</summary>",
            "",
            head_report,
            "",
            "</details>",
            "",
        ]
    )


def load_results(root: Path) -> list[RunResult]:
    if not root.exists():
        return []
    return [
        _result_from_mapping(json.loads(path.read_text(encoding="utf-8")))
        for path in sorted(root.rglob("result.json"))
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m termproof.ci_evidence")
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("target", choices=("ci", "release"))
    run_parser.add_argument("--repo", type=Path, default=Path("."))
    run_parser.add_argument("--out", type=Path)
    run_parser.add_argument("--continue-on-fail", action="store_true")

    comment_parser = subparsers.add_parser("comment")
    comment_parser.add_argument("--base-dir", type=Path, required=True)
    comment_parser.add_argument("--head-dir", type=Path, required=True)
    comment_parser.add_argument("--out", type=Path, required=True)
    comment_parser.add_argument("--run-url", required=True)
    comment_parser.add_argument("--base-label", default="base")
    comment_parser.add_argument("--head-label", default="head")

    args = parser.parse_args(argv)
    if args.command == "run":
        code = run_target(args.target, args.repo, out=args.out, receipt_path=args.receipt)
        return 0 if args.continue_on_fail else code
    if args.command == "comment":
        body = compose_pr_comment(
            args.base_dir,
            args.head_dir,
            args.run_url,
            base_label=args.base_label or "base",
            head_label=args.head_label or "head",
            receipt_path=args.receipt,
        )
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(body, encoding="utf-8")
        return 0
    raise AssertionError(args.command)


def _copy_receipt(receipt_path: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(receipt_path, out_dir / "evidence-receipt.json")


def _normalize_artifact_paths(out_dir: Path) -> None:
    if not out_dir.is_absolute() or not out_dir.exists():
        return
    try:
        display_dir = out_dir.relative_to(Path.cwd())
    except ValueError:
        return
    old = str(out_dir)
    new = str(display_dir)
    for path in [out_dir / "latest-report.md", *out_dir.rglob("report.md")]:
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            path.write_text(text.replace(old, new), encoding="utf-8")
    for path in out_dir.rglob("result.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        data["artifacts"] = {
            key: str(value).replace(old, new) for key, value in data.get("artifacts", {}).items()
        }
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _read_report(root: Path) -> str:
    path = root / "latest-report.md"
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return "No TermProof report was generated."


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return (
        f"{text[:limit]}\n\n_Report truncated. Download the "
        "`termproof-ci-evidence` artifact from the run for the full report._"
    )


def _result_from_mapping(data: dict[str, Any]) -> RunResult:
    return RunResult(
        recipe_name=data["recipe_name"],
        passed=bool(data["passed"]),
        exit_code=data["exit_code"],
        duration_seconds=float(data["duration_seconds"]),
        priority=data["priority"],
        execution=data["execution"],
        renderer=data["renderer"],
        score=float(data["score"]),
        steps=[
            StepResult(step["name"], bool(step["passed"]), step["detail"], step["screen"])
            for step in data.get("steps", [])
        ],
        assertions=[
            AssertionResult(assertion["name"], bool(assertion["passed"]), assertion["detail"])
            for assertion in data.get("assertions", [])
        ],
        artifacts=dict(data.get("artifacts", {})),
    )


if __name__ == "__main__":
    raise SystemExit(main())
