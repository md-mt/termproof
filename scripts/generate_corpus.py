#!/usr/bin/env python3
"""Deterministic contract-corpus generator for RUST-001 (issue #94).

Freezes the Python implementation's observable behavior as committed
fixtures under ``corpus/``. The Python implementation is the executable
oracle for the Rust reimplementation; every public command, flag, exit
code, config-precedence case, built-in step/assertion, and evidence
artifact is captured in normalized form.

Determinism contract
--------------------
Generation must be reproducible byte-for-byte on any machine with the
same oracle code and locked dependencies. Unstable values are normalized
before writing (see corpus/normalization-policy.md):

- wall-clock durations        -> canonical 0.0 in fixtures (semantic >= 0 check)
- JUnit timestamp/hostname    -> fixed placeholders
- asciinema cast header/times -> canonical v2 header, merged output events
- artifact paths              -> relative to the run directory
- build provenance            -> fixed tokens (binary path, version, git commit)
- video bytes                 -> never compared; presence + warning text only
- PNG pixels                  -> byte compare when Pillow matches oracle, else
                                 semantic (dimensions) compare

The oracle commit is recorded in ``corpus/oracle.json``. Run the drift
check with ``--check`` (regenerates into a temp dir and diffs against the
committed corpus); this is what tests/test_corpus_drift.py invokes.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# The Python oracle state frozen by this corpus. MUST equal the termproof/
# tree at generation time; scripts/generate_corpus.py verifies it.
ORACLE_COMMIT = "165c367ca0b0e2a4663a8773ee18b67c2264979c"

# -- path helpers ------------------------------------------------------------

RUN_DIR_RE = re.compile(r"/\d{8}-\d{6}-\d{6}-[^/]+")


def apps_dir(root: Path) -> Path:
    return root / "apps"


def recipes_dir(root: Path) -> Path:
    return root / "recipes"


def runs_dir(root: Path) -> Path:
    return root / "runs"


def cli_dir(root: Path) -> Path:
    return root / "cli"


def config_dir(root: Path) -> Path:
    return root / "config"


def evidence_dir(root: Path) -> Path:
    return root / "evidence"


# -- normalization helpers ---------------------------------------------------


def normalize_json_value(value: object, *, key: str | None = None) -> object:
    """Return a copy of *value* with unstable fields normalized in place.

    Only known unstable keys are touched; everything else is preserved so
    drift in structure, names, or text still fails byte comparison.
    """
    if isinstance(value, dict):
        return {
            k: normalize_json_value(v, key=k) for k, v in value.items()
        }
    if isinstance(value, list):
        return [normalize_json_value(v, key=key) for v in value]
    if key == "duration_seconds" and isinstance(value, (int, float)):
        return 0.0
    return value


def canonical_json(data: object) -> str:
    """Serialize *data* as canonical JSON (sorted keys, indent=2)."""
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def normalize_result_json(text: str, *, run_rel: str | None = None) -> str:
    data = json.loads(text)
    data = normalize_json_value(data)
    if isinstance(data, dict) and isinstance(data.get("artifacts"), dict):
        data["artifacts"] = normalize_artifact_map(data["artifacts"], run_rel=run_rel)
    if isinstance(data, dict) and isinstance(data.get("steps"), list):
        for step in data["steps"]:
            if isinstance(step, dict) and "screen" in step:
                step["screen"] = _stable_screen(step["screen"])
    return canonical_json(data)


def normalize_artifact_map(artifacts: dict, *, run_rel: str | None = None) -> dict:
    out: dict[str, str] = {}
    for key, value in artifacts.items():
        if key == "cache":
            out[key] = "<cache>"
            continue
        path = Path(str(value))
        if run_rel and str(path).startswith(run_rel):
            out[key] = str(path.relative_to(run_rel))
        else:
            out[key] = path.name
    return out


def _stable_screen(screen: str) -> str:
    """Strip trailing whitespace from each line for stable byte compare."""
    return "\n".join(line.rstrip() for line in screen.splitlines())


def normalize_report_md(text: str, *, run_rel: str | None = None) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("- Duration:"):
            line = "- Duration: `0.00s`"
        elif line.startswith("- ") and ": `" in line and line.endswith("`"):
            marker, value = line[2:].split(": `", 1)
            path_value = value[:-1]
            basename = Path(path_value).name
            if basename and basename != path_value:
                line = f"- {marker}: `{basename}`"
        lines.append(line)
    return "\n".join(lines) + "\n"


def normalize_latest_report_md(text: str, run_rel: str | None = None) -> str:
    out = normalize_report_md(text, run_rel=run_rel)
    # Build provenance records machine state; normalize to fixed tokens.
    out = re.sub(r"- Binary: `[^`]*`", "- Binary: `python3`", out)
    out = re.sub(r"- Version: `[^`]*`", "- Version: `Python 3.x`", out)
    out = re.sub(r"- Git commit: `[^`]*`", "- Git commit: `<oracle-commit>`", out)
    # Evidence links embed absolute run-dir paths; collapse to basenames.
    out = re.sub(r"(\[[a-z_]+\])\([^)]*/([^/)]+)\)", r"\1(\2)", out)
    out = re.sub(r"\[([a-z_]+)\]\(([^)]*)\)", r"[\1](\2)", out)
    # Any remaining timestamped run-dir tokens are environment-specific.
    out = RUN_DIR_RE.sub("/<run-dir>", out)
    return out


def normalize_junit_xml(text: str) -> str:
    out = re.sub(r'timestamp="[^"]*"', 'timestamp="1970-01-01T00:00:00+00:00"', text)
    out = re.sub(r'hostname="[^"]*"', 'hostname="localhost"', out)
    out = re.sub(r' time="[^"]*"', ' time="0.000"', out)
    # system-out/failure artifact lines embed absolute run-dir paths.
    out = re.sub(r"(  [a-z_]+: )([^<\n]*/)([^/<\n]+)", r"\1\3", out)
    return out


def normalize_cast(text: str) -> str:
    """Canonicalize an asciinema cast for stable comparison.

    The recorder's header (version, timestamp, env, command) and per-event
    wall-clock times are tool-dependent. The contract is the terminal
    *output* bytes in order; the canonical form merges all ``o`` events
    into a single deterministic event and drops non-output events.
    """
    lines = text.splitlines()
    if not lines:
        return text
    header = json.loads(lines[0])
    width = int(header.get("width") or header.get("term", {}).get("cols", 100))
    height = int(header.get("height") or header.get("term", {}).get("rows", 30))
    payload: list[str] = []
    for line in lines[1:]:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if len(event) >= 3 and event[1] == "o":
            payload.append(str(event[2]))
    canonical = {
        "version": 2,
        "width": width,
        "height": height,
        "timestamp": 0,
        "command": "",
        "env": {},
    }
    merged = "".join(payload)
    body = [json.dumps(canonical)]
    if merged:
        body.append(json.dumps([0.0, "o", merged]))
    return "\n".join(body) + "\n"


def normalize_png_bytes(data: bytes, *, oracle_pillow: str | None = None) -> str:
    """Return a stable descriptor for PNG bytes.

    When Pillow matches the oracle's version, PNG bytes are deterministic
    and returned verbatim (base64). Otherwise only dimensions/decodability
    are compared (font rendering normalization).
    """
    import base64

    import PIL
    from PIL import Image

    try:
        with Image.open(io.BytesIO(data)) as image:
            size = f"{image.width}x{image.height}"
            fmt = image.format or "UNKNOWN"
    except Exception as exc:  # noqa: BLE001 - descriptor must not raise
        return f"<invalid-png: {exc}>"
    if oracle_pillow is not None and PIL.__version__ == oracle_pillow:
        return base64.b64encode(data).decode("ascii")
    return f"<png {fmt} {size}>"


def normalize_oracle_json(text: str) -> str:
    data = json.loads(text)
    data.pop("generated_at", None)
    return canonical_json(data)


# -- CLI helpers -------------------------------------------------------------


def run_cli(argv: list[str], *, cwd: Path | None = None) -> tuple[int, str, str]:
    """Run the termproof CLI in-process, returning (exit_code, stdout, stderr)."""
    from termproof.cli import main

    stdout, stderr = io.StringIO(), io.StringIO()
    previous = os.getcwd()
    if cwd is not None:
        os.chdir(cwd)
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                code = main(argv)
            except SystemExit as exc:
                code = int(exc.code or 0)
    finally:
        os.chdir(previous)
    return code, stdout.getvalue(), stderr.getvalue()


# -- app fixtures ------------------------------------------------------------

# Fixture apps are generated in a ruff/isort-clean canonical form so the whole
# repo (including corpus/apps) passes `ruff check .` in CI. Do not hand-edit
# the committed copies; change the templates here and regenerate.
APPS: dict[str, str] = {
    "banner.py": """#!/usr/bin/env python3
\"\"\"Deterministic non-interactive fixture app.\"\"\"
from __future__ import annotations

import sys


def main() -> int:
    sys.stdout.write("TermProof Fixture App v1.2.3\\n")
    sys.stdout.write("status: ready\\n")
    sys.stdout.write("menu: [status] [help] [quit]\\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
""",
    "interact.py": """#!/usr/bin/env python3
\"\"\"Deterministic interactive fixture app.\"\"\"
from __future__ import annotations

import sys


def main() -> int:
    sys.stdout.write("version: 1.2.3\\n")
    sys.stdout.write("demo> ")
    sys.stdout.flush()
    for raw in sys.stdin:
        line = raw.rstrip("\\n").rstrip("\\r")
        if line == "quit":
            sys.stdout.write("bye\\n")
            sys.stdout.flush()
            return 0
        if line == "status":
            sys.stdout.write("STATUS: ok\\n")
        elif line == "help":
            sys.stdout.write("HELP: available\\n")
        else:
            sys.stdout.write(f"got: {line}\\n")
        sys.stdout.write("demo> ")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
""",
    "json_app.py": """#!/usr/bin/env python3
\"\"\"Deterministic JSON-output fixture app.\"\"\"
from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    payload = {"app": "fixture", "version": "1.2.3", "status": "ok", "items": ["alpha", "beta", "gamma"]}
    sys.stdout.write(json.dumps(payload) + "\\n")
    sys.stdout.flush()
    Path("fixture-artifact.txt").write_text("fixture artifact content\\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
""",
    "fail_app.py": """#!/usr/bin/env python3
\"\"\"Deterministic failing fixture app.\"\"\"
from __future__ import annotations

import sys


def main() -> int:
    sys.stdout.write("fixture failure app\\n")
    sys.stdout.write("about to exit non-zero\\n")
    sys.stdout.flush()
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
""",
    "stage_app.py": """#!/usr/bin/env python3
\"\"\"Deterministic multi-stage fixture app.\"\"\"
from __future__ import annotations

import sys
import time


def main() -> int:
    sys.stdout.write("stage one\\n")
    sys.stdout.flush()
    time.sleep(0.2)
    sys.stdout.write("stage two complete\\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
""",
}


def write_apps(root: Path) -> None:
    app_dir = apps_dir(root)
    app_dir.mkdir(parents=True, exist_ok=True)
    for name, content in APPS.items():
        (app_dir / name).write_text(content, encoding="utf-8")


# -- recipe fixtures ---------------------------------------------------------

# Canonical recipe fixtures committed under corpus/recipes/. ``run`` is the
# scenario id used for evidence output; ``argv_cwd`` must resolve relative to
# the repo root when the oracle runs them.
RECIPES: list[dict] = [
    {
        "id": "banner-basic",
        "kind": "v1",
        "filename": "v1/banner-basic.recipe.json",
        "content": {
            "recipe_version": 1,
            "name": "banner-basic",
            "description": "Representative v1 recipe: fixed banner app, PTY mode.",
            "priority": "P2",
            "execution": "scripted",
            "determinism": "deterministic",
            "command": {"argv": ["python3", "banner.py"], "cwd": "corpus/apps", "pty": True},
            "expect_exit_code": 0,
            "timeout_seconds": 15,
            "cols": 100,
            "rows": 30,
            "steps": [
                {"name": "wait for banner title", "action": "wait_for_text", "text": "TermProof Fixture App", "timeout_seconds": 5},
                {"name": "wait for ready status", "action": "wait_for_text", "text": "status: ready", "timeout_seconds": 5},
            ],
            "assertions": [
                {"name": "output has fixture title", "type": "output_contains", "value": "TermProof Fixture App"},
                {"name": "screen has menu", "type": "screen_contains", "value": "menu:"},
            ],
        },
    },
    {
        "id": "banner-legacy",
        "kind": "legacy",
        "filename": "legacy/banner-legacy.recipe.json",
        "content": {
            "name": "banner-legacy",
            "description": "Representative legacy recipe (no recipe_version key): fixed banner app, process mode.",
            "priority": "P1",
            "execution": "scripted",
            "determinism": "deterministic",
            "command": {"argv": ["python3", "banner.py"], "cwd": "corpus/apps", "pty": False},
            "expect_exit_code": 0,
            "timeout_seconds": 15,
            "cols": 80,
            "rows": 24,
            "assertions": [
                {"name": "legacy output contains title", "type": "output_contains", "value": "TermProof Fixture App"},
            ],
        },
    },
    {
        "id": "interact-all-steps",
        "kind": "v1",
        "filename": "v1/interact-all-steps.recipe.json",
        "content": {
            "recipe_version": 1,
            "name": "interact-all-steps",
            "description": "Exercises all seven built-in steps against the deterministic interactive app.",
            "priority": "P0",
            "execution": "scripted",
            "determinism": "deterministic",
            "command": {"argv": ["python3", "interact.py"], "cwd": "corpus/apps", "pty": True},
            "expect_exit_code": 0,
            "timeout_seconds": 20,
            "cols": 100,
            "rows": 30,
            "steps": [
                {"name": "wait for version banner", "action": "wait_for_text", "text": "version: 1.2.3", "timeout_seconds": 5},
                {"name": "wait for idle prompt", "action": "wait_for_idle", "stable_seconds": 0.3, "timeout_seconds": 3},
                {"name": "type status without newline", "action": "send_text", "text": "status"},
                {"name": "press enter to submit", "action": "press", "key": "enter"},
                {"name": "wait for status result", "action": "wait_for_text", "text": "STATUS: ok", "timeout_seconds": 5},
                {"name": "capture status via regex", "action": "wait_for_regex", "pattern": "STATUS: (?P<state>\\w+)", "timeout_seconds": 3},
                {"name": "send help line", "action": "send_line", "text": "help"},
                {"name": "wait for help result", "action": "wait_for_text", "text": "HELP: available", "timeout_seconds": 5},
                {"name": "brief sleep", "action": "sleep", "seconds": 0.2},
                {"name": "quit cleanly", "action": "send_line", "text": "quit"},
                {"name": "wait for bye", "action": "wait_for_text", "text": "bye", "timeout_seconds": 5},
            ],
            "assertions": [
                {"name": "interaction output present", "type": "output_contains", "value": "STATUS: ok"},
                {"name": "help text on screen", "type": "screen_contains", "value": "HELP: available"},
                {"name": "clean exit", "type": "exit_code", "value": 0},
            ],
        },
    },
    {
        "id": "json-all-assertions",
        "kind": "v1",
        "filename": "v1/json-all-assertions.recipe.json",
        "content": {
            "recipe_version": 1,
            "name": "json-all-assertions",
            "description": "Exercises all eight built-in assertions against the deterministic JSON app.",
            "priority": "P0",
            "execution": "scripted",
            "determinism": "deterministic",
            "command": {"argv": ["python3", "json_app.py"], "cwd": "corpus/apps", "pty": False},
            "expect_exit_code": 0,
            "timeout_seconds": 15,
            "cols": 80,
            "rows": 24,
            "steps": [
                {"name": "wait for json output", "action": "wait_for_text", "text": "fixture", "timeout_seconds": 5},
            ],
            "assertions": [
                {"name": "output contains app name", "type": "output_contains", "value": "fixture"},
                {"name": "output does not contain absent marker", "type": "output_not_contains", "value": "not-present-marker"},
                {"name": "screen contains status", "type": "screen_contains", "value": "ok"},
                {"name": "screen does not contain absent marker", "type": "screen_not_contains", "value": "not-present-marker"},
                {"name": "exit code is zero", "type": "exit_code", "value": 0},
                {"name": "artifact file exists", "type": "file_exists", "value": "fixture-artifact.txt"},
                {"name": "artifact file contains content", "type": "file_contains", "path": "fixture-artifact.txt", "value": "fixture artifact content"},
                {"name": "output matches json schema", "type": "json_schema", "schema": {
                    "type": "object",
                    "required": ["app", "status", "items"],
                    "properties": {
                        "app": {"type": "string"},
                        "status": {"type": "string"},
                        "version": {"type": "string"},
                        "items": {"type": "array", "items": {"type": "string"}},
                    },
                }},
            ],
        },
    },
    {
        "id": "fail-exit-code",
        "kind": "v1",
        "filename": "v1/fail-exit-code.recipe.json",
        "content": {
            "recipe_version": 1,
            "name": "fail-exit-code",
            "description": "Deterministic failing recipe: app exits 3 but recipe expects 0.",
            "priority": "P2",
            "execution": "scripted",
            "determinism": "deterministic",
            "command": {"argv": ["python3", "fail_app.py"], "cwd": "corpus/apps", "pty": False},
            "expect_exit_code": 0,
            "timeout_seconds": 15,
            "cols": 80,
            "rows": 24,
            "assertions": [
                {"name": "failure prefix appears", "type": "output_contains", "value": "fixture failure app"},
            ],
        },
    },
    {
        "id": "stage-timing",
        "kind": "v1",
        "filename": "v1/stage-timing.recipe.json",
        "content": {
            "recipe_version": 1,
            "name": "stage-timing",
            "description": "Two-stage app used to freeze wait_for_idle / wait_for_regex semantics.",
            "priority": "P3",
            "execution": "scripted",
            "determinism": "deterministic",
            "command": {"argv": ["python3", "stage_app.py"], "cwd": "corpus/apps", "pty": False},
            "expect_exit_code": 0,
            "timeout_seconds": 15,
            "cols": 80,
            "rows": 24,
            "steps": [
                {"name": "wait for stage one", "action": "wait_for_text", "text": "stage one", "timeout_seconds": 5},
                {"name": "wait for stage two", "action": "wait_for_text", "text": "stage two complete", "timeout_seconds": 5},
                {"name": "capture completion via regex", "action": "wait_for_regex", "pattern": "stage (two) complete", "timeout_seconds": 3},
            ],
            "assertions": [
                {"name": "stage output present", "type": "output_contains", "value": "stage two complete"},
            ],
        },
    },
]


def write_recipes(root: Path) -> None:
    for recipe in RECIPES:
        path = recipes_dir(root) / recipe["filename"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(recipe["content"], indent=2) + "\n", encoding="utf-8")


# -- CLI help / flags / exit codes ------------------------------------------

# Every public command surface from cli.py, including subcommands.
PUBLIC_COMMANDS: list[tuple[str, list[str]]] = [
    ("termproof", ["--help"]),
    ("run", ["run", "--help"]),
    ("list", ["list", "--help"]),
    ("validate", ["validate", "--help"]),
    ("plugins", ["plugins", "--help"]),
    ("plugins-list", ["plugins", "list", "--help"]),
    ("plugins-search", ["plugins", "search", "--help"]),
    ("plugins-install", ["plugins", "install", "--help"]),
    ("init", ["init", "--help"]),
    ("demo", ["demo", "--help"]),
]

# Public run flags asserted in the flags inventory (from cli.py run_parser).
RUN_FLAGS = [
    "--out",
    "--video",
    "--no-video",
    "--video-fps",
    "--priority",
    "--recipe-name",
    "--parallel",
    "--renderer",
    "--operator-command",
    "--config",
    "--reporter",
    "--xml-path",
    "--screen-renderer",
    "--video-backend",
    "--diff",
    "--baseline-dir",
    "--update-baselines",
    "--skip-unchanged",
    "--cache-dir",
]

# Exit-code scenarios: (label, argv, note). Each runs against the oracle from
# a sandbox workdir; recipe paths are repo-relative.
EXIT_CODE_SCENARIOS: list[dict] = [
    {"label": "no-args", "argv": [], "note": "argparse requires a subcommand"},
    {"label": "unknown-command", "argv": ["frobnicate"], "note": "argparse rejects unknown subcommand"},
    {"label": "run-pass", "argv": ["run", "corpus/recipes/v1/banner-basic.recipe.json"], "note": "passing recipe exits 0"},
    {"label": "run-fail", "argv": ["run", "corpus/recipes/v1/fail-exit-code.recipe.json"], "note": "failing recipe exits 1"},
    {"label": "run-parallel-zero", "argv": ["run", "corpus/recipes/v1/banner-basic.recipe.json", "--parallel", "0"], "note": "--parallel must be >= 1"},
    {"label": "run-skip-diff-conflict", "argv": ["run", "corpus/recipes/v1/banner-basic.recipe.json", "--skip-unchanged", "--diff"], "note": "--skip-unchanged cannot combine with --diff"},
    {"label": "list", "argv": ["list", "corpus/recipes/v1/banner-basic.recipe.json"], "note": "list succeeds"},
    {"label": "validate-pass", "argv": ["validate", "corpus/recipes/v1/banner-basic.recipe.json"], "note": "valid recipe"},
    {"label": "validate-invalid", "argv": ["validate", "corpus/recipes/invalid/not-a-recipe.json"], "note": "invalid recipe exits 1"},
    {"label": "validate-missing", "argv": ["validate", ".termproof/corpus/empty-dir"], "note": "no recipe files found exits 1"},
    {"label": "plugins-list", "argv": ["plugins", "list"], "note": "plugin list succeeds"},
    {"label": "plugins-search-nomatch", "argv": ["plugins", "search", "no-such-plugin-xyz", "--registry", "corpus/fixtures/plugins.md"], "note": "search with no matches exits 0"},
    {"label": "plugins-install-unknown", "argv": ["plugins", "install", "no-such-plugin-xyz", "--registry", "corpus/fixtures/plugins.md", "--dry-run"], "note": "unknown plugin exits 1"},
    {"label": "init-new", "argv": ["init", ".termproof/corpus/init-target", "--name", "demo-tui", "--command", "python3 -c 'print(42)'", "--non-pty"], "note": "creates a recipe pack"},
    {"label": "init-existing", "argv": ["init", ".termproof/corpus/init-existing", "--name", "demo-tui", "--command", "python3 -c 'print(42)'", "--non-pty"], "note": "existing recipe exits 1"},
    {"label": "demo", "argv": ["demo", "--out", ".termproof/corpus/demo", "--no-open"], "note": "demo succeeds (exit 0)"},
]


def write_cli_help(root: Path) -> None:
    out_dir = cli_dir(root) / "help"
    out_dir.mkdir(parents=True, exist_ok=True)
    for command, argv in PUBLIC_COMMANDS:
        code, stdout, stderr = run_cli(argv, cwd=REPO_ROOT)
        if code != 0 and not stdout:
            stdout = stderr or f"(exit {code})"
        safe = command.replace("-", "_")
        (out_dir / f"{safe}-help.txt").write_text(stdout, encoding="utf-8")


def write_flags_inventory(root: Path) -> None:
    out_dir = cli_dir(root)
    out_dir.mkdir(parents=True, exist_ok=True)
    inventory = {
        "public_commands": [c for c, _ in PUBLIC_COMMANDS],
        "run_flags": RUN_FLAGS,
        "other_command_flags": {
            "list": ["--priority"],
            "validate": ["--config"],
            "plugins": ["list", "search", "install"],
            "plugins_search": ["--registry"],
            "plugins_install": ["--registry", "--dry-run"],
            "init": ["--name", "--command", "--non-pty", "--priority", "--cols", "--rows", "--force"],
            "demo": ["--out", "--no-open", "--video", "--video-fps", "--config", "--reporter", "--xml-path", "--screen-renderer", "--video-backend"],
        },
    }
    (out_dir / "flags.json").write_text(canonical_json(inventory), encoding="utf-8")


def write_exit_codes(root: Path) -> None:
    out_dir = cli_dir(root)
    out_dir.mkdir(parents=True, exist_ok=True)
    work = REPO_ROOT / ".termproof" / "corpus"
    work.mkdir(parents=True, exist_ok=True)
    exit_runs = str((work / "exit-runs").resolve())
    # Reset stateful targets so generation is deterministic across runs.
    for stale in ("init-target", "exit-runs"):
        target = work / stale
        if target.exists():
            shutil.rmtree(target)
    # Prepare the init-existing target and invalid recipe fixture.
    existing = work / "init-existing"
    if existing.exists():
        shutil.rmtree(existing)
    existing.mkdir(parents=True)
    (existing / "demo-tui.recipe.json").write_text(
        '{"name": "demo-tui", "command": {"argv": ["python3", "-c", "print(42)"]}}\n',
        encoding="utf-8",
    )
    empty_dir = work / "empty-dir"
    empty_dir.mkdir(parents=True, exist_ok=True)
    invalid_dir = recipes_dir(root) / "invalid"
    invalid_dir.mkdir(parents=True, exist_ok=True)
    (invalid_dir / "not-a-recipe.json").write_text(
        '{"recipe_version": 1, "name": "bad"}\n', encoding="utf-8"
    )
    fixtures_dir = root / "fixtures"
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    (fixtures_dir / "plugins.md").write_text(
        "# Community Plugins\n\n| Name | Description | Install | Author |\n"
        "| --- | --- | --- | --- |\n"
        "| demo-plugin | A demo plugin | pip install demo-plugin | demo |\n",
        encoding="utf-8",
    )

    rows: list[dict] = []
    for scenario in EXIT_CODE_SCENARIOS:
        if scenario["label"].startswith("run-") and "--out" not in scenario["argv"]:
            # run-* scenarios need an absolute out dir so the cast path is
            # resolved from the runner's cwd, not the app's cwd.
            argv = [*scenario["argv"], "--out", exit_runs]
        else:
            argv = scenario["argv"]
        code, stdout, _stderr = run_cli(argv, cwd=REPO_ROOT)
        rows.append(
            {
                "label": scenario["label"],
                "argv": scenario["argv"],
                "exit_code": code,
                "note": scenario["note"],
                "stdout_first_line": stdout.splitlines()[0] if stdout.splitlines() else "",
            }
        )
    (out_dir / "exit-codes.json").write_text(canonical_json(rows), encoding="utf-8")


# -- config precedence -------------------------------------------------------

CONFIG_CASES: list[dict] = [
    {
        "label": "builtin-only",
        "note": "No config files; resolved config equals builtin defaults.",
        "files": {},
    },
    {
        "label": "legacy-user-wins",
        "note": "Legacy user config (~/.config/tui-verifier/config.yaml) overrides defaults.",
        "files": {
            "user-legacy": "defaults:\n  idle_cap_seconds: 1.5\n",
        },
    },
    {
        "label": "termproof-user-wins",
        "note": "TermProof user config (~/.config/termproof/config.yaml) beats legacy user config.",
        "files": {
            "user-legacy": "defaults:\n  idle_cap_seconds: 1.5\n",
            "user-termproof": "defaults:\n  idle_cap_seconds: 2.5\n",
        },
    },
    {
        "label": "legacy-project-wins",
        "note": "Legacy project config (.tui-verifier/config.yaml) beats both user configs.",
        "files": {
            "user-termproof": "defaults:\n  idle_cap_seconds: 2.5\n",
            "project-legacy": "defaults:\n  idle_cap_seconds: 3.5\n",
        },
    },
    {
        "label": "termproof-project-wins",
        "note": "TermProof project config (.termproof/config.yaml) beats legacy project config.",
        "files": {
            "project-legacy": "defaults:\n  idle_cap_seconds: 3.5\n",
            "project-termproof": "defaults:\n  idle_cap_seconds: 4.5\n",
        },
    },
    {
        "label": "explicit-config-wins",
        "note": "Explicit --config beats every discovery location.",
        "files": {
            "user-termproof": "defaults:\n  idle_cap_seconds: 4.5\n",
            "project-termproof": "defaults:\n  idle_cap_seconds: 5.5\n",
            "explicit": "defaults:\n  idle_cap_seconds: 6.5\n",
        },
    },
]


def write_config_precedence(root: Path) -> None:
    from termproof.config import load_config

    out_dir = config_dir(root) / "precedence"
    fixtures_out = config_dir(root) / "precedence" / "fixtures"
    out_dir.mkdir(parents=True, exist_ok=True)
    fixtures_out.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        home_dir = base / "home"
        project_dir = base / "project"
        home_dir.mkdir()
        project_dir.mkdir()

        for case in CONFIG_CASES:
            # Lay out the documented discovery locations.
            (home_dir / ".config" / "tui-verifier").mkdir(parents=True, exist_ok=True)
            (home_dir / ".config" / "termproof").mkdir(parents=True, exist_ok=True)
            (project_dir / ".tui-verifier").mkdir(parents=True, exist_ok=True)
            (project_dir / ".termproof").mkdir(parents=True, exist_ok=True)
            for location, content in case["files"].items():
                if location == "user-legacy":
                    (home_dir / ".config" / "tui-verifier" / "config.yaml").write_text(content, encoding="utf-8")
                elif location == "user-termproof":
                    (home_dir / ".config" / "termproof" / "config.yaml").write_text(content, encoding="utf-8")
                elif location == "project-legacy":
                    (project_dir / ".tui-verifier" / "config.yaml").write_text(content, encoding="utf-8")
                elif location == "project-termproof":
                    (project_dir / ".termproof" / "config.yaml").write_text(content, encoding="utf-8")
                elif location == "explicit":
                    (base / "explicit.yaml").write_text(content, encoding="utf-8")

            # Preserve the resolved result under the fixture dir for inspection.
            case_fixture = fixtures_out / f"{case['label']}.yaml"
            if case["files"]:
                merged = "\n".join(case["files"].values())
                case_fixture.write_text(merged, encoding="utf-8")

            explicit = base / "explicit.yaml" if "explicit" in case["files"] else None
            config = load_config(
                project_path=project_dir,
                user_path=home_dir / ".config" / "termproof" / "config.yaml"
                if "user-termproof" in case["files"]
                else home_dir / ".config" / "tui-verifier" / "config.yaml"
                if "user-legacy" in case["files"]
                else None,
                config_path=explicit,
            )
            resolved = {
                "defaults": {
                    "idle_cap_seconds": config.defaults.idle_cap_seconds,
                },
                "docker": {
                    "image": config.docker.image,
                    "workdir": config.docker.workdir,
                },
                "session_backend": config.session_backend,
            }
            (out_dir / f"{case['label']}.json").write_text(
                canonical_json(
                    {
                        "label": case["label"],
                        "note": case["note"],
                        "resolved": resolved,
                    }
                ),
                encoding="utf-8",
            )


# -- run evidence ------------------------------------------------------------

EVIDENCE_RUNS: list[dict] = [
    {"recipe": "v1/banner-basic.recipe.json", "id": "banner-basic", "kind": "pass"},
    {"recipe": "legacy/banner-legacy.recipe.json", "id": "banner-legacy", "kind": "legacy"},
    {"recipe": "v1/interact-all-steps.recipe.json", "id": "interact-all-steps", "kind": "pass"},
    {"recipe": "v1/json-all-assertions.recipe.json", "id": "json-all-assertions", "kind": "pass"},
    {"recipe": "v1/fail-exit-code.recipe.json", "id": "fail-exit-code", "kind": "fail"},
    {"recipe": "v1/stage-timing.recipe.json", "id": "stage-timing", "kind": "pass"},
]


def _run_recipe_to_dir(root: Path, recipe_rel: str, out_dir: Path) -> None:
    """Run one committed recipe via the runner into *out_dir*."""
    from termproof.models import load_recipe
    from termproof.runner import VerificationRunner

    recipe_path = recipes_dir(root) / recipe_rel
    recipe = load_recipe(recipe_path)
    runner = VerificationRunner()
    runner.run(recipe, out_dir=out_dir, render_video=False, screen_renderer_name="svg")


def write_run_evidence(root: Path) -> None:
    runs_root = runs_dir(root)
    runs_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        sandbox = Path(tmp) / "out"
        sandbox.mkdir()
        for run in EVIDENCE_RUNS:
            recipe_rel = run["recipe"]
            _run_recipe_to_dir(root, recipe_rel, sandbox)
            # Locate the generated run dir (timestamped).
            run_dirs = sorted(sandbox.glob("*-*"))
            if not run_dirs:
                raise RuntimeError(f"no run dir produced for {recipe_rel}")
            run_dir = run_dirs[0]
            # Copy normalized evidence into the corpus.
            dest = runs_root / run["id"]
            dest.mkdir(parents=True, exist_ok=True)
            for name in ("result.json", "report.md", "final.txt", "final.svg", "session.cast", "session.exitcode"):
                src = run_dir / name
                if not src.exists():
                    continue
                raw = src.read_bytes()
                if name == "result.json":
                    content = normalize_result_json(raw.decode("utf-8")).encode("utf-8")
                elif name == "report.md":
                    content = normalize_report_md(raw.decode("utf-8")).encode("utf-8")
                elif name == "session.cast":
                    content = normalize_cast(raw.decode("utf-8")).encode("utf-8")
                else:
                    content = raw
                (dest / name).write_bytes(content)
            steps_src = run_dir / "steps"
            if steps_src.exists():
                shutil.copytree(steps_src, dest / "steps", dirs_exist_ok=True)
            # Cleanup between runs.
            for existing in sandbox.iterdir():
                if existing.is_dir():
                    shutil.rmtree(existing)
                else:
                    existing.unlink()
    # The json-all-assertions app writes an artifact into its cwd
    # (corpus/apps) as part of the run; remove it so it is never committed.
    (apps_dir(root) / "fixture-artifact.txt").unlink(missing_ok=True)


def write_reports(root: Path) -> None:
    """Capture CLI-level aggregate reports (Markdown + JUnit) for a run."""
    out_dir = root / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        sandbox = Path(tmp)
        out_path = sandbox / "runs"
        recipe = str((recipes_dir(root) / "v1" / "banner-basic.recipe.json").resolve())
        code, stdout, _ = run_cli(
            ["run", recipe, "--out", str(out_path), "--reporter", "markdown"],
            cwd=REPO_ROOT,
        )
        if code != 0:
            raise RuntimeError(f"markdown report run failed: {stdout}")
        latest = out_path / "latest-report.md"
        if latest.exists():
            (out_dir / "latest-report.md").write_text(
                normalize_latest_report_md(latest.read_text(encoding="utf-8")),
                encoding="utf-8",
            )
        run_dirs = sorted(out_path.glob("*-*"))
        if run_dirs:
            result_json = run_dirs[0] / "result.json"
            if result_json.exists():
                (out_dir / "result.json").write_text(
                    normalize_result_json(result_json.read_text(encoding="utf-8")),
                    encoding="utf-8",
                )
        xml_path = sandbox / "junit.xml"
        code, stdout, _ = run_cli(
            ["run", recipe, "--out", str(out_path), "--xml-path", str(xml_path)],
            cwd=REPO_ROOT,
        )
        if code != 0:
            raise RuntimeError(f"junit run failed: {stdout}")
        if xml_path.exists():
            (out_dir / "junit.xml").write_text(
                normalize_junit_xml(xml_path.read_text(encoding="utf-8")),
                encoding="utf-8",
            )


# -- video, cache, diff contracts --------------------------------------------


def write_video_contract(root: Path) -> None:
    """Capture the deterministic missing-tools video warning and presence semantics.

    Video *bytes* are never compared (encoder/platform dependent). The frozen
    contract is: requesting --video with tools present yields a session.mp4
    artifact; with tools missing it emits an exact loud warning and omits the
    artifact. We capture the warning text here and the presence contract in
    the drift test's semantic checks.
    """
    out_dir = root / "video"
    out_dir.mkdir(parents=True, exist_ok=True)
    from termproof.builtin_renderers import SvgRenderer
    from termproof.evidence import _missing_video_tools as real_missing_video_tools
    from termproof.evidence import render_artifacts

    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp)
        (run_dir / "session.cast").write_text(
            '{"version": 2, "width": 80, "height": 24}\n[0.1, "o", "fixture"]\n',
            encoding="utf-8",
        )
        import warnings

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            import termproof.evidence as evidence

            evidence._missing_video_tools = lambda: ["agg", "ffmpeg"]  # type: ignore[method-assign]
            try:
                artifacts = render_artifacts(
                    run_dir,
                    render_video=True,
                    video_fps=60,
                    screen_renderer=SvgRenderer(),
                )
            finally:
                evidence._missing_video_tools = real_missing_video_tools
        warning_texts = [str(w.message) for w in caught]
        (out_dir / "missing-tools-warning.txt").write_text(
            "\n".join(warning_texts) + "\n", encoding="utf-8"
        )
        has_video = "video" in artifacts
        (out_dir / "presence-contract.json").write_text(
            canonical_json(
                {
                    "requested_video": True,
                    "video_artifact_present_with_missing_tools": has_video,
                    "expected_artifact_name": "session.mp4",
                }
            ),
            encoding="utf-8",
        )


def write_cache_contract(root: Path) -> None:
    """Capture the cache key inputs and a cached-result shape."""
    from dataclasses import replace as replace_dataclass

    from termproof.models import load_recipe
    from termproof.run_cache import _cache_key

    out_dir = root / "cache"
    out_dir.mkdir(parents=True, exist_ok=True)
    recipe_path = recipes_dir(root) / "v1" / "banner-basic.recipe.json"
    recipe = load_recipe(recipe_path)
    # The cache key hashes the recipe *source path*; pin it to the canonical
    # repo-relative path so the recorded key is stable across checkouts.
    recipe = replace_dataclass(recipe, source_path="corpus/recipes/v1/banner-basic.recipe.json")
    key = _cache_key(
        recipe,
        "default",
        [],
        out_dir=Path(".termproof/runs"),
        screen_renderer="svg",
        video_backend="agg_ffmpeg",
        render_video=False,
        video_fps=60,
    )
    (out_dir / "cache-key-inputs.json").write_text(
        canonical_json(
            {
                "recipe_source_path": "corpus/recipes/v1/banner-basic.recipe.json",
                "renderer": "default",
                "renderer_argv": [],
                "out_dir": ".termproof/runs",
                "screen_renderer": "svg",
                "video_backend": "agg_ffmpeg",
                "render_video": False,
                "video_fps": 60,
                "key_sha256": key,
            }
        ),
        encoding="utf-8",
    )


def write_diff_contract(root: Path) -> None:
    """Capture the visual-diff assertion output for two differing screenshots."""
    out_dir = root / "diff"
    out_dir.mkdir(parents=True, exist_ok=True)
    from termproof.builtin_renderers import SvgRenderer
    from termproof.models import AssertionResult, RunResult, StepResult
    from termproof.visual_diff import apply_visual_diff

    baseline_root = out_dir / "baselines"
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        baseline = baseline_root / "recipe-a" / "default" / "final.svg"
        baseline.parent.mkdir(parents=True, exist_ok=True)
        # Screenshot A (baseline) and screenshot B (drifted) differ by one line.
        screen_a = "alpha\nbeta\n"
        screen_b = "alpha\nBETA-CHANGED\n"
        baseline_svg = tmp_dir / "final.svg"
        SvgRenderer().render(screen_a, baseline_svg, 80, 24)
        shutil.copy2(baseline_svg, baseline)
        actual_svg = tmp_dir / "final.svg"
        SvgRenderer().render(screen_b, actual_svg, 80, 24)

        result = RunResult(
            recipe_name="recipe-a",
            passed=True,
            exit_code=0,
            duration_seconds=1.0,
            priority="P2",
            execution="scripted",
            renderer="default",
            score=1.0,
            steps=[StepResult("step", True, "ok", screen_b)],
            assertions=[AssertionResult("output_contains", True, "contains alpha")],
            artifacts={"screenshot": str(actual_svg), "cast": "session.cast"},
        )
        diffed = apply_visual_diff(result, baseline_root, update=False)
        diffed_dict = diffed.to_dict()
        # Tokenize environment-specific absolute paths in detail strings so
        # the fixture is byte-stable across checkouts.
        detail_text = json.dumps(diffed_dict, indent=2)
        detail_text = detail_text.replace(str(tmp_dir), "<tmp>")
        detail_text = detail_text.replace(str(baseline_root), "<baseline>")
        diffed_dict = json.loads(detail_text)
        (out_dir / "diff-result.json").write_text(
            normalize_result_json(json.dumps(diffed_dict, indent=2)),
            encoding="utf-8",
        )
        diff_svg = actual_svg.with_name("visual-diff.svg")
        if diff_svg.exists():
            (out_dir / "visual-diff.svg").write_text(
                diff_svg.read_text(encoding="utf-8"), encoding="utf-8"
            )


# -- oracle record -----------------------------------------------------------


def write_oracle(root: Path, *, check: bool = False) -> None:
    import PIL

    import termproof

    oracle = {
        "oracle_commit": ORACLE_COMMIT,
        "termproof_version": getattr(termproof, "__version__", "0.2.1"),
        "python_version": ".".join(str(v) for v in sys.version_info[:3]),
        "pillow_version": PIL.__version__,
        "generator": "scripts/generate_corpus.py",
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    path = root / "oracle.json"
    if check and path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        existing["generated_at"] = oracle["generated_at"]
        oracle = existing
    path.write_text(canonical_json(oracle), encoding="utf-8")


# -- orchestration -----------------------------------------------------------


def generate_all(root: Path, *, check: bool = False) -> None:
    """Generate the full contract corpus into *root*.

    Every fixture is written in normalized, deterministic form. In ``check``
    mode, the oracle record preserves the committed generated_at so drift
    comparison ignores it.
    """
    write_apps(root)
    write_recipes(root)
    write_cli_help(root)
    write_flags_inventory(root)
    write_exit_codes(root)
    write_config_precedence(root)
    write_run_evidence(root)
    write_reports(root)
    write_video_contract(root)
    write_cache_contract(root)
    write_diff_contract(root)
    write_oracle(root, check=check)


def _normalize_fixture(rel: Path, data: bytes) -> str:
    text = data.decode("utf-8")
    if rel.name == "result.json" or rel.name == "diff-result.json":
        return normalize_result_json(text)
    if rel.name == "report.md":
        return normalize_report_md(text)
    if rel.name == "latest-report.md":
        return normalize_latest_report_md(text)
    if rel.name == "junit.xml":
        return normalize_junit_xml(text)
    if rel.name == "session.cast":
        return normalize_cast(text)
    if rel.name == "oracle.json":
        return normalize_oracle_json(text)
    if rel.suffix == ".png":
        return normalize_png_bytes(data)
    return text


def check_drift(committed: Path) -> int:
    """Regenerate into a temp dir and diff against the committed corpus.

    Returns 0 when every fixture matches after normalization, 1 otherwise.
    Prints a per-file report to stdout.
    """
    with tempfile.TemporaryDirectory() as tmp:
        fresh = Path(tmp)
        generate_all(fresh, check=True)
        # json_app writes its artifact relative to the runner cwd (the real
        # repo, not the temp corpus); ensure it never lingers in the tree.
        (REPO_ROOT / "corpus" / "apps" / "fixture-artifact.txt").unlink(missing_ok=True)
        committed_oracle = json.loads((committed / "oracle.json").read_text(encoding="utf-8"))
        oracle_pillow = committed_oracle.get("pillow_version")

        mismatches: list[str] = []
        compared = 0
        for fresh_path in sorted(fresh.rglob("*")):
            if not fresh_path.is_file():
                continue
            rel = fresh_path.relative_to(fresh)
            committed_path = committed / rel
            if not committed_path.exists():
                mismatches.append(f"MISSING IN COMMITTED: {rel}")
                continue
            compared += 1
            fresh_data = fresh_path.read_bytes()
            committed_data = committed_path.read_bytes()
            if rel.suffix == ".png":
                a = normalize_png_bytes(fresh_data, oracle_pillow=oracle_pillow)
                b = normalize_png_bytes(committed_data, oracle_pillow=oracle_pillow)
            else:
                a = _normalize_fixture(rel, fresh_data)
                b = _normalize_fixture(rel, committed_data)
            if a != b:
                mismatches.append(f"DIFF: {rel}")

        print(f"compared {compared} fixture files")
        if mismatches:
            print(f"{len(mismatches)} mismatch(es):")
            for line in mismatches:
                print(f"  {line}")
            return 1
        print("DRIFT CHECK PASS: regenerated corpus matches committed fixtures")
        return 0


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="generate_corpus",
        description="Generate or drift-check the termproof contract corpus.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="regenerate into a temp dir and diff against corpus/ (drift check)",
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=REPO_ROOT / "corpus",
        help="corpus root to write into (default: repo corpus/)",
    )
    args = parser.parse_args(argv)

    if args.check:
        committed = REPO_ROOT / "corpus"
        return check_drift(committed)

    generate_all(args.target)
    print(f"generated contract corpus in {args.target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
