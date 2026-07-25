from __future__ import annotations

from pathlib import Path

from .models import Recipe
from .runner import load_recipe


def find_recipe_files(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_dir():
            files.extend(sorted(path.rglob("*.recipe.json")))
        else:
            files.append(path)
    return files


def load_recipes(paths: list[Path]) -> list[Recipe]:
    return [load_recipe(path) for path in find_recipe_files(paths)]


def select_recipes(
    recipes: list[Recipe],
    priority: str | None = None,
    names: list[str] | None = None,
) -> list[Recipe]:
    selected = recipes
    if priority:
        selected = [recipe for recipe in selected if recipe.priority == priority]
    if names:
        wanted = set(names)
        selected = [recipe for recipe in selected if recipe.name in wanted]
    return selected
