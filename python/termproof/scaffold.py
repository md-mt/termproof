from __future__ import annotations

import json
import shlex
from pathlib import Path


def write_recipe_pack(
    path: Path,
    name: str,
    command: str,
    pty: bool,
    priority: str,
    cols: int,
    rows: int,
    force: bool = False,
) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    recipe_path = path / f"{_safe_name(name)}.recipe.json"
    if recipe_path.exists() and not force:
        raise FileExistsError(recipe_path)
    recipe_path.write_text(
        json.dumps(
            {
                "name": name,
                "description": f"Verify the {name} terminal workflow.",
                "priority": priority,
                "execution": "scripted",
                "determinism": "deterministic",
                "checks": [
                    "terminal workflow starts",
                    "terminal evidence is recorded",
                ],
                "renderers": {"default": []},
                "command": {
                    "argv": shlex.split(command),
                    "pty": pty,
                },
                "timeout_seconds": 30,
                "cols": cols,
                "rows": rows,
                "steps": [
                    {
                        "name": "wait for stable screen",
                        "action": "wait_for_idle",
                        "stable_seconds": 0.75,
                        "timeout_seconds": 10,
                    }
                ],
                "assertions": [
                    {
                        "name": "python traceback is absent",
                        "type": "output_not_contains",
                        "value": "Traceback",
                    },
                ],
                "expect_exit_code": None,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    _write_readme(path, recipe_path.name)
    return recipe_path


def _write_readme(path: Path, recipe_name: str) -> None:
    readme = path / "README.md"
    if readme.exists():
        return
    readme.write_text(
        "\n".join(
            [
                "# TermProof Recipe Pack",
                "",
                "Run this pack from the repository root:",
                "",
                "```bash",
                f"uv run termproof run {path}/{recipe_name} --video",
                "```",
                "",
                "Edit the recipe assertions and steps to match the product workflow.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in value).strip("-")
