from __future__ import annotations

import importlib
from collections.abc import Callable
from pathlib import Path
from typing import Generic, TypeVar

from .config import CURRENT_PLUGIN_MODULE_PREFIX, LEGACY_PLUGIN_MODULE_PREFIX
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


def import_class(qualname: str) -> type:
    """Import a plugin class from a ``module.path:ClassName`` reference.

    Configuration written for the pre-TermProof package can keep using its
    plugin module prefix. This narrow alias avoids a compatibility shim package
    while ensuring external plugin configuration remains loadable.
    """
    if ":" not in qualname:
        raise ValueError(
            f"expected 'module.path:ClassName', got {qualname!r}"
        )
    module_name, class_name = qualname.split(":", 1)
    if module_name.startswith(LEGACY_PLUGIN_MODULE_PREFIX):
        module_name = (
            CURRENT_PLUGIN_MODULE_PREFIX
            + module_name.removeprefix(LEGACY_PLUGIN_MODULE_PREFIX)
        )
    module = importlib.import_module(module_name)
    return getattr(module, class_name)


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
