from __future__ import annotations

from .models import Recipe


def selected_renderers(recipe: Recipe, selection: str) -> list[tuple[str, list[str]]]:
    renderers = recipe.renderers or {"default": []}
    if selection in ("all", "both"):
        return [(name, list(argv)) for name, argv in renderers.items()]
    if selection in renderers:
        return [(selection, list(renderers[selection]))]
    available = ", ".join(sorted(renderers))
    raise ValueError(f"unknown renderer {selection!r}; available: {available}")
