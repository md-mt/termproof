#!/usr/bin/env python3
"""Oracle half of the config / run-cache differential harness.

Records two things the Python implementation emits for fixed scenarios:

* the serialised :class:`termproof.config.VerifierConfig` document
  (``dataclasses.asdict`` of what :func:`termproof.config.load_config`
  returns) for a fixed set of YAML overlays cascaded over the built-in
  defaults — plus the ``ValueError`` text for overlays it rejects, and
* the run-cache key (:func:`termproof.run_cache._cache_key`) for a fixed
  set of (recipe, options, evidence) inputs, as a hex digest or ``null``.

The Rust half (``differential_config.rs``) transcribes the same scenarios
through ``config::VerifierConfig::load`` and ``cache::cache_key``.

The scenarios are code in each half, not a corpus of cases, as with the
run result: the overlay strings below are the scenario, and the Rust test
carries the identical strings. Each load runs against fresh temporary
directories — an empty project directory, a user path that does not
exist, and the overlay as the explicit ``--config`` file — so no real
user or project config leaks in from the recording machine.

This half records the Python behaviour as it is. The known divergences
(#209) — the typed, defaulted ``evidence`` block and the
``artifact_publishers`` map existing only here (the Rust config carries
no such fields; a supplied ``evidence:`` block is preserved there as an
unvalidated extension echo and changes nothing), three built-in plugin
entries and the ``session_backend`` spelling, unknown keys dropped here
and preserved there, evidence validation existing only here, the two
coercions the exercised overlays hit refused there (Python applies
further ``str()`` coercions no overlay exercises — ``session_backend``
and ``docker.image``/``workdir`` in ``_from_mapping`` — so nothing here
pins those), an explicit ``idle_cap_seconds: null`` honoured as
``None`` here but collapsed to the default ``3.0`` there, the cache
key folding the whole
``EvidenceConfig`` in here while the Rust key has no evidence input at
all, and a missing recipe file yielding no key here but a key there —
are **not** recorded here: they are named allowances in the Rust test,
so the checked-in expectation stays the oracle's testimony and each
allowance has to be edited deliberately, in code, if either side
changes. Cache digests are recorded as facts about the Python payload
only; the two implementations serialise different payloads (the evidence
member, the JSON spacing), so no digest is expected to compare across
languages — the Rust half pins availability and which inputs move the
key, per side.

Cache inputs use fixed *relative* path strings (``recipe.yaml``,
``ci.txt``, ``out``) with the probe chdir'd into its temporary
directory: both implementations hash the path string as given, so the
recorded digests reproduce on any machine. ``_cache_key`` is private;
it is also exactly the input-folding this harness exists to pin, and
nothing else calls it in isolation.

Regenerate deliberately::

    cd /path/to/termproof/python
    TERMPROOF_PYTHON_REPO=$PWD uv run python \\
        ../conformance/probe_config.py \\
        > ../conformance/corpus/config.expected.json
"""

from __future__ import annotations

import json
import os
import platform
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, os.environ.get("TERMPROOF_PYTHON_REPO", str(Path(__file__).parent.parent / "python")))

from termproof.config import EvidenceConfig, SvgRenderConfig, load_config  # noqa: E402
from termproof.models import CommandSpec, Recipe  # noqa: E402
from termproof.run_cache import _cache_key  # noqa: E402

# The fixed config scenarios: (name, overlay YAML or None for no overlay).
# Keep in step with differential_config.rs, which carries the same strings.
OVERLAYS: list[tuple[str, str | None]] = [
    ("defaults", None),
    (
        "evidence-populated",
        "evidence:\n"
        "  dedup_step_screenshots: true\n"
        "  svg:\n"
        "    char_width: 7.5\n"
        "    font_size: 12\n"
        "  png:\n"
        "    scale: 2\n"
        "    font_path: /usr/share/fonts/custom.ttf\n"
        "  video:\n"
        "    fps: 30\n"
        "    crf: 18\n",
    ),
    (
        "docker-full",
        "docker:\n"
        "  image: myimg:1.0\n"
        "  workdir: /app\n"
        "  env:\n"
        "    FOO: bar\n"
        "  volumes:\n"
        "    - host: ./src\n"
        "      container: /src\n",
    ),
    (
        "plugin-overrides",
        "steps:\n"
        "  custom_step: mypkg.steps:CustomStep\n"
        "  sleep: mypkg.steps:MySleep\n"
        "artifact_publishers:\n"
        "  gcs: mypkg.pub:GcsPublisher\n",
    ),
    ("idle-null", "defaults:\n  idle_cap_seconds: null\n"),
    ("idle-string", "defaults:\n  idle_cap_seconds: '2.5'\n"),
    ("idle-negative", "defaults:\n  idle_cap_seconds: -1\n"),
    ("docker-env-numeric", "docker:\n  env:\n    FOO: 1\n"),
    ("unknown-top-level", "bogus_section:\n  x: 1\n"),
    ("unknown-docker-key", "docker:\n  bogus_knob: 3\n"),
    ("unknown-defaults-key", "defaults:\n  bogus_knob: 3\n"),
    ("unknown-evidence-key", "evidence:\n  bogus_knob: 3\n"),
    ("unknown-evidence-svg-key", "evidence:\n  svg:\n    bogus_knob: 3\n"),
    ("evidence-bad-type", "evidence:\n  svg:\n    font_size: 'twelve'\n"),
    ("evidence-below-minimum", "evidence:\n  svg:\n    font_size: 0\n"),
]

RECIPE_BYTES = b"name: login\ncommand: [cat]\n"
RECIPE_BYTES_B = b"name: login\ncommand: [cat]\ndescription: changed\n"
CI_BYTES_A = b"ci content A\n"
CI_BYTES_B = b"ci content B\n"


def config_cases() -> list[dict[str, object]]:
    cases: list[dict[str, object]] = []
    for name, overlay in OVERLAYS:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "proj"
            project.mkdir()
            config_path = None
            if overlay is not None:
                config_path = root / "overlay.yaml"
                config_path.write_text(overlay, encoding="utf-8")
            try:
                config = load_config(
                    project_path=project,
                    user_path=root / "no-user.yaml",
                    config_path=config_path,
                )
            except ValueError as error:
                cases.append({"name": name, "error": f"ValueError: {error}"})
            else:
                cases.append({"name": name, "config": asdict(config)})
    return cases


def cache_cases() -> list[dict[str, object]]:
    def key(
        recipe: Recipe,
        *,
        renderer: str = "default",
        evidence: EvidenceConfig | None = None,
        render_video: bool = False,
        video_backend: str = "agg_ffmpeg",
        video_fps: int = 60,
    ) -> str | None:
        return _cache_key(
            recipe,
            renderer,
            [],
            out_dir=Path("out"),
            screen_renderer="svg",
            video_backend=video_backend,
            render_video=render_video,
            video_fps=video_fps,
            evidence=evidence,
        )

    previous = Path.cwd()
    with tempfile.TemporaryDirectory() as tmp:
        os.chdir(tmp)
        try:
            Path("recipe.yaml").write_bytes(RECIPE_BYTES)
            Path("ci.txt").write_bytes(CI_BYTES_A)
            recipe = Recipe(
                name="login",
                command=CommandSpec(argv=["cat"]),
                ci_paths=["ci.txt"],
                source_path="recipe.yaml",
            )
            cases: list[dict[str, object]] = [
                {"name": "base", "key": key(recipe)},
                {
                    "name": "evidence-tweaked",
                    "key": key(recipe, evidence=EvidenceConfig(svg=SvgRenderConfig(font_size=12))),
                },
                {"name": "renderer-changed", "key": key(recipe, renderer="other")},
                {
                    "name": "video-off-fps-changed",
                    "key": key(recipe, video_backend="other", video_fps=30),
                },
                {
                    "name": "video-on",
                    "key": key(recipe, render_video=True, video_fps=30),
                },
                {
                    "name": "no-source-path",
                    "key": key(
                        Recipe(
                            name="login",
                            command=CommandSpec(argv=["cat"]),
                            ci_paths=["ci.txt"],
                            source_path=None,
                        )
                    ),
                },
                {
                    "name": "missing-recipe-file",
                    "key": key(
                        Recipe(
                            name="login",
                            command=CommandSpec(argv=["cat"]),
                            ci_paths=["ci.txt"],
                            source_path="missing.yaml",
                        )
                    ),
                },
            ]
            Path("ci.txt").write_bytes(CI_BYTES_B)
            cases.append({"name": "ci-content-changed", "key": key(recipe)})
            Path("ci.txt").write_bytes(CI_BYTES_A)
            Path("recipe.yaml").write_bytes(RECIPE_BYTES_B)
            cases.append({"name": "recipe-content-changed", "key": key(recipe)})
            return cases
        finally:
            os.chdir(previous)


def main() -> None:
    document = {
        "_comment": (
            "Generated by conformance/probe_config.py against the Python "
            "implementation. Do not hand-edit; regenerate instead."
        ),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.system(),
        },
        "cases": config_cases(),
        "cache_cases": cache_cases(),
    }
    json.dump(document, sys.stdout, indent=2, sort_keys=True, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
