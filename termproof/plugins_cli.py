from __future__ import annotations

import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .config import VerifierConfig

DEFAULT_REGISTRY_PATH = Path("docs/plugins.md")


@dataclass(frozen=True)
class InstalledPlugin:
    category: str
    name: str
    target: str


@dataclass(frozen=True)
class CommunityPlugin:
    name: str
    description: str
    install: str
    author: str


def installed_plugins(config: VerifierConfig) -> list[InstalledPlugin]:
    rows: list[InstalledPlugin] = []
    registries = [
        ("steps", config.steps),
        ("assertions", config.assertions),
        ("agent_runners", config.agent_runners),
        ("execution_modes", config.execution_modes),
        ("reporters", config.reporters),
        ("screen_renderers", config.screen_renderers),
        ("video_backends", config.video_backends),
    ]
    for category, mapping in registries:
        for name, target in sorted(mapping.items()):
            rows.append(InstalledPlugin(category, name, target))
    rows.append(InstalledPlugin("session_backend", "active", config.session_backend))
    return rows


def load_community_plugins(path: Path = DEFAULT_REGISTRY_PATH) -> list[CommunityPlugin]:
    if not path.exists():
        return []
    rows: list[CommunityPlugin] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 4 or cells[0] == "Name" or set(cells[0]) <= {"-", ":"}:
            continue
        if cells[0].startswith("_"):
            continue
        rows.append(
            CommunityPlugin(
                _plain(cells[0]),
                _plain(cells[1]),
                _plain(cells[2]),
                _plain(cells[3]),
            )
        )
    return rows


def search_community_plugins(
    query: str,
    path: Path = DEFAULT_REGISTRY_PATH,
) -> list[CommunityPlugin]:
    needle = query.lower()
    matches = []
    for plugin in load_community_plugins(path):
        haystack = " ".join(
            [plugin.name, plugin.description, plugin.install, plugin.author]
        ).lower()
        if needle in haystack:
            matches.append(plugin)
    return matches


def install_community_plugin(
    name: str,
    path: Path = DEFAULT_REGISTRY_PATH,
    dry_run: bool = False,
) -> tuple[int, str]:
    plugin = next(
        (item for item in load_community_plugins(path) if item.name == name),
        None,
    )
    if plugin is None:
        return 1, f"unknown plugin: {name}"
    package = _install_package(plugin.install)
    if package is None:
        return 1, f"plugin {name!r} has no supported install command"
    command = [sys.executable, "-m", "pip", "install", package]
    if dry_run:
        return 0, shlex.join(command)
    return subprocess.call(command), shlex.join(command)


def _plain(value: str) -> str:
    value = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", value)
    return value.replace("`", "").strip()


def _install_package(value: str) -> str | None:
    tokens = shlex.split(value)
    if not tokens:
        return None
    if len(tokens) >= 3 and tokens[0] == "pip" and tokens[1] == "install":
        candidates = tokens[2:]
    elif len(tokens) >= 3 and tokens[0] == "uv" and tokens[1] == "add":
        candidates = tokens[2:]
    elif len(tokens) >= 4 and tokens[0] == "uv" and tokens[1:3] == ["pip", "install"]:
        candidates = tokens[3:]
    else:
        candidates = tokens
    for token in candidates:
        if not token.startswith("-"):
            return token
    return None
