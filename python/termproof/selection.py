"""Choose which recipes to run from the files a change touched.

Running the whole suite on every change is slow enough that people stop running
it. A recipe declares the paths it covers (``ci_paths``) and this picks the ones
a diff could plausibly have broken.

The core function takes ``(name, ci_paths)`` pairs rather than recipe objects,
so it works for any recipe model — including a host whose recipes are classes
rather than the JSON ``Recipe`` in this package. :func:`select_recipes` is the
thin wrapper for that model.
"""

from __future__ import annotations

import fnmatch
from collections.abc import Iterable, Sequence
from pathlib import Path

from .models import Recipe


def read_changed_files(path: Path | str) -> list[str]:
    """One path per line, blanks dropped — the shape ``git diff --name-only`` emits."""
    text = Path(path).read_text(encoding="utf-8")
    return [line.strip() for line in text.splitlines() if line.strip()]


def normalize_path(path: str, root_marker: str | None = None) -> str:
    """Reduce a path to the form patterns are written against.

    Backslashes become slashes, ``./`` prefixes and trailing slashes go. If
    *root_marker* is given and appears in the path, everything before it is
    dropped — a CI system that reports absolute paths then still matches
    patterns written relative to the repository root.
    """
    normalized = path.strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    if root_marker:
        marker = f"/{root_marker.strip('/')}/"
        if marker in normalized:
            normalized = root_marker.strip("/") + "/" + normalized.split(marker, 1)[1]
    return normalized.rstrip("/")


def matches_any(patterns: Iterable[str], paths: Iterable[str], root_marker: str | None = None) -> bool:
    """True when any glob in *patterns* matches any path in *paths*."""
    normalized_paths = [normalize_path(path, root_marker) for path in paths]
    return any(
        fnmatch.fnmatch(path, normalize_path(pattern, root_marker))
        for pattern in patterns
        for path in normalized_paths
    )


def select_names(
    candidates: Iterable[tuple[str, Sequence[str]]],
    changed_files: Iterable[str],
    *,
    always: Sequence[str] = (),
    harness_paths: Sequence[str] = (),
    root_marker: str | None = None,
) -> list[str]:
    """Names of the recipes a change should run, in candidate order.

    *candidates* is ``(name, ci_paths)`` pairs. *always* names recipes that run
    regardless — a smoke set worth having on every change.

    *harness_paths* are globs covering the test harness itself. When a change
    touches those, the mapping from product paths to recipes is exactly what is
    in question, so path matching is skipped and only *always* runs. Selecting
    everything would be the other defensible answer; this one keeps the
    diff-time signal fast and leaves full coverage to the full run.
    """
    pairs = list(candidates)
    names = [name for name, _ in pairs]
    selected = {name for name in always if name in names}

    paths = list(changed_files)
    if harness_paths and matches_any(harness_paths, paths, root_marker):
        return [name for name in names if name in selected]

    for name, ci_paths in pairs:
        if matches_any(ci_paths, paths, root_marker):
            selected.add(name)
    return [name for name in names if name in selected]


def select_recipes(
    recipes: Sequence[Recipe],
    changed_files: Iterable[str],
    *,
    always: Sequence[str] = (),
    harness_paths: Sequence[str] = (),
    root_marker: str | None = None,
) -> list[Recipe]:
    """:func:`select_names` for this package's :class:`~termproof.models.Recipe`."""
    chosen = set(
        select_names(
            [(recipe.name, recipe.ci_paths) for recipe in recipes],
            changed_files,
            always=always,
            harness_paths=harness_paths,
            root_marker=root_marker,
        )
    )
    return [recipe for recipe in recipes if recipe.name in chosen]


__all__ = [
    "matches_any",
    "normalize_path",
    "read_changed_files",
    "select_names",
    "select_recipes",
]
