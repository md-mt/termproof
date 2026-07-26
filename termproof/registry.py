from __future__ import annotations

from pathlib import Path
from typing import Callable, Generic, TypeVar

from .models import Recipe, load_recipe

T = TypeVar("T")


class Registry(Generic[T]):
    """Generic named registry for pluggable components.

    Stores factories (callables returning T) keyed by name.
    Lookup is O(1) dict access. Populated once at startup.
    """

    def __init__(self) -> None:
        self._factories: dict[str, Callable[[], T]] = {}

    def register(self, name: str, factory: Callable[[], T]) -> None:
        self._factories[name] = factory

    def get(self, name: str) -> T:
        factory = self._factories.get(name)
        if factory is None:
            available = ", ".join(sorted(self._factories))
            raise KeyError(
                f"unknown plugin {name!r}; available: {available}"
            )
        return factory()

    def names(self) -> list[str]:
        return sorted(self._factories)


# -- recipe discovery --------------------------------------------------------


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
