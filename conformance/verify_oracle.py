#!/usr/bin/env python3
"""Check that the recorded oracle expectations still match the Python probes.

The Rust differential tests compare the port against the checked-in
``corpus/*.expected.json`` files, but nothing re-ran the Python probes that
recorded them, so a Python-side behaviour change could leave stale
expectations that every gate still passed (#216, #172). This script is that
missing check: it re-runs every probe, parses the fresh output in memory and
compares it with the checked-in file. It never writes into ``corpus/``.

Usage, from the repository root or from ``python/``::

    python3 conformance/verify_oracle.py

Each probe runs the way ``conformance/README.md`` documents regeneration
(``uv run`` from ``python/``, so dependencies come from ``python/uv.lock``).
The case payload and the ``environment`` block are compared separately:
a payload difference always fails (exit 1), an environment difference is
reported field by field and only fails under ``--strict-environment``,
because the recorded blocks already disagree with each other (Python
3.12.13, 3.13.2 and 3.13.5, all on Darwin) and no single interpreter
reproduces all three. Neither the interpreter patch version nor the
operating system is pinned anywhere in this repository. The full policy,
including why CI does not run this yet, is in ``conformance/README.md``
under "Checking oracle freshness".
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, NamedTuple

CONFORMANCE = Path(__file__).resolve().parent
CORPUS = CONFORMANCE / "corpus"

#: (probe, expectation it records), in README table order.
PROBES = (
    ("probe_steps.py", "steps.expected.json"),
    ("probe_assertions.py", "assertions.expected.json"),
    ("probe_evidence_manifest.py", "evidence_manifest.expected.json"),
    ("probe_before_after.py", "before_after.expected.json"),
    ("probe_cast_replay.py", "cast_replay.expected.json"),
)

#: How many differing cases to spell out per file before summarising the rest.
MAX_SHOWN = 5
#: Bound on one rendered value in a diff line.
RENDER_LIMIT = 300


class Comparison(NamedTuple):
    """Outcome for one expectation file: verdict plus human-readable lines."""

    ok: bool
    payload_diffs: list[str]
    environment_diffs: list[str]


def split_document(document: Any) -> tuple[Any, dict[str, Any] | None]:
    """Split a recorded document into its case payload and environment block.

    ``_comment`` goes with the environment side of the line: it is generator
    prose, identical by construction, and comparing it would only ever
    measure this file's own wording. List documents and the evidence
    manifest have no header at all, so their payload is the whole document.
    """
    if isinstance(document, dict) and ("environment" in document or "cases" in document):
        payload = {k: v for k, v in document.items() if k not in ("environment", "_comment")}
        return payload, document.get("environment")
    return document, None


def _render(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return text if len(text) <= RENDER_LIMIT else text[:RENDER_LIMIT] + "…"


def _label(item: Any, index: int) -> str:
    if isinstance(item, dict):
        for key in ("id", "name"):
            if item.get(key):
                return f"case {index} ({item[key]})"
        expected = item.get("expected") or {}
        if isinstance(expected, dict) and expected.get("name"):
            return f"case {index} (expected {expected['name']})"
    return f"case {index}"


def _list_diffs(stored: list[Any], fresh: list[Any]) -> list[str]:
    diffs = []
    if len(stored) != len(fresh):
        diffs.append(f"length differs: recorded {len(stored)}, fresh {len(fresh)}")
    differing = [i for i, (a, b) in enumerate(zip(stored, fresh, strict=False)) if a != b]
    for i in differing[:MAX_SHOWN]:
        diffs.append(
            f"{_label(fresh[i], i)} differs:\n"
            f"    recorded: {_render(stored[i])}\n"
            f"    fresh:    {_render(fresh[i])}"
        )
    if len(differing) > MAX_SHOWN:
        diffs.append(f"… and {len(differing) - MAX_SHOWN} more differing cases")
    return diffs


def _payload_diffs(stored: Any, fresh: Any) -> list[str]:
    if isinstance(stored, dict) and isinstance(fresh, dict) and "cases" in stored:
        diffs = [
            f"key {key!r} differs outside the cases"
            for key in sorted(set(stored) | set(fresh))
            if key != "cases" and stored.get(key) != fresh.get(key)
        ]
        return diffs + _list_diffs(stored.get("cases", []), fresh.get("cases", []))
    if isinstance(stored, list) and isinstance(fresh, list):
        return _list_diffs(stored, fresh)
    if stored == fresh:
        return []
    if isinstance(stored, dict) and isinstance(fresh, dict):
        return [
            f"key {key!r} differs:\n    recorded: {_render(stored.get(key))}\n"
            f"    fresh:    {_render(fresh.get(key))}"
            for key in sorted(set(stored) | set(fresh))
            if stored.get(key) != fresh.get(key)
        ][:MAX_SHOWN]
    return [f"document differs:\n    recorded: {_render(stored)}\n    fresh:    {_render(fresh)}"]


def _environment_diffs(
    stored: dict[str, Any] | None, fresh: dict[str, Any] | None
) -> list[str]:
    if stored is None and fresh is None:
        return []
    if stored is None or fresh is None:
        return [f"environment block present on one side only: recorded {stored}, fresh {fresh}"]
    return [
        f"environment.{key}: recorded {stored.get(key)!r}, fresh {fresh.get(key)!r}"
        for key in sorted(set(stored) | set(fresh))
        if stored.get(key) != fresh.get(key)
    ]


def compare_documents(stored: Any, fresh: Any, *, strict_environment: bool = False) -> Comparison:
    """Compare one recorded document against a fresh probe run."""
    stored_payload, stored_env = split_document(stored)
    fresh_payload, fresh_env = split_document(fresh)
    payload_diffs = _payload_diffs(stored_payload, fresh_payload)
    environment_diffs = _environment_diffs(stored_env, fresh_env)
    ok = not payload_diffs and (not strict_environment or not environment_diffs)
    return Comparison(ok=ok, payload_diffs=payload_diffs, environment_diffs=environment_diffs)


def run_probe(python_dir: Path, probe: Path) -> Any:
    """Run one probe exactly as the README's regeneration commands do."""
    env = {**os.environ, "TERMPROOF_PYTHON_REPO": str(python_dir)}
    try:
        result = subprocess.run(
            ["uv", "run", "python", str(probe)],
            cwd=python_dir,
            env=env,
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"could not run {probe.name}: {exc}") from exc
    if result.returncode != 0:
        tail = "\n".join(result.stderr.splitlines()[-10:])
        raise RuntimeError(f"{probe.name} exited {result.returncode}:\n{tail}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{probe.name} did not emit JSON: {exc}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--strict-environment",
        action="store_true",
        help="fail when a fresh environment block differs from the recorded one",
    )
    args = parser.parse_args(argv)

    python_dir = Path(
        os.environ.get("TERMPROOF_PYTHON_REPO") or CONFORMANCE.parent / "python"
    ).resolve()
    if not python_dir.is_dir():
        print(f"error: TERMPROOF_PYTHON_REPO is not a directory: {python_dir}", file=sys.stderr)
        return 2

    failures = 0
    for probe_name, expected_name in PROBES:
        stored = json.loads((CORPUS / expected_name).read_text(encoding="utf-8"))
        try:
            fresh = run_probe(python_dir, CONFORMANCE / probe_name)
        except RuntimeError as exc:
            failures += 1
            print(f"FAIL {expected_name}: {exc}")
            continue
        comparison = compare_documents(
            stored, fresh, strict_environment=args.strict_environment
        )
        if comparison.ok:
            suffix = " (payload matches; environment differs)" if comparison.environment_diffs else ""
            print(f"ok   {expected_name}{suffix}")
        else:
            failures += 1
            print(f"FAIL {expected_name} (via {probe_name})")
        for diff in comparison.payload_diffs:
            print(f"  {diff}")
        for diff in comparison.environment_diffs:
            print(f"  {diff}")
        if comparison.payload_diffs and comparison.environment_diffs:
            print(
                "  note: the environment also differs, so part of this payload "
                "difference may be environment-owned wording; read the diff "
                "before re-recording."
            )

    checked = len(PROBES)
    if failures:
        print(f"\n{failures}/{checked} expectation files are stale or could not be checked.")
        print("Do not re-record to silence this without reading the diff above;")
        print("see 'Checking oracle freshness' in conformance/README.md.")
        return 1
    print(f"\nAll {checked} expectation files match a fresh probe run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

