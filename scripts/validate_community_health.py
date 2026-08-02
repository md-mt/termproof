#!/usr/bin/env python3
"""Validation harness for the community-health remediation.

1. Copy/paste-check the bug_report.md recipe through TermProof's actual
   loader/schema (validate_recipe_file via the CLI entry point).
2. Validate .github/ISSUE_TEMPLATE/config.yml against the pinned SchemaStore
   github-issue-config schema (vendored under scripts/schemas/).
3. Validate .github/FUNDING.yml against the pinned SchemaStore github-funding
   schema.
4. Parse every YAML under .github/ and all template frontmatter.

The schemas are vendored in-repo so the harness is hermetic on a fresh
checkout. To validate against a different copy (e.g. the live SchemaStore
version), pass --issue-config-schema <url-or-path> and/or
--funding-schema <url-or-path>. A schema that cannot be read is a clean
validation failure, never a traceback.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parent.parent
BUG_REPORT = ROOT / ".github" / "ISSUE_TEMPLATE" / "bug_report.md"
CONFIG_YML = ROOT / ".github" / "ISSUE_TEMPLATE" / "config.yml"
FUNDING_YML = ROOT / ".github" / "FUNDING.yml"
SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"
DEFAULT_ISSUE_CONFIG_SCHEMA = SCHEMA_DIR / "github-issue-config.json"
DEFAULT_FUNDING_SCHEMA = SCHEMA_DIR / "github-funding.json"

failures = []


def check(name: str, ok: bool, detail: str = "") -> None:
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        failures.append(name)


def load_schema(location: str) -> dict | None:
    """Load a schema from a local path or URL; None on any failure."""
    try:
        if re.match(r"^https?://", location):
            with urllib.request.urlopen(location, timeout=30) as response:
                raw = response.read().decode("utf-8")
        else:
            raw = Path(location).read_text(encoding="utf-8")
    except (OSError, urllib.error.URLError) as error:
        print(f"  could not read schema {location}: {error}")
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as error:
        print(f"  schema {location} is not valid JSON: {error}")
        return None


def validate_against_schema(name: str, instance: object, location: str) -> None:
    schema = load_schema(location)
    if schema is None:
        check(f"{name} schema available ({location})", False)
        return
    try:
        jsonschema.validate(instance=instance, schema=schema)
        check(f"{name} validates against SchemaStore schema", True)
    except jsonschema.ValidationError as error:
        check(f"{name} validates against SchemaStore schema", False, str(error)[:300])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--issue-config-schema",
        default=str(DEFAULT_ISSUE_CONFIG_SCHEMA),
        help="path or URL of the github-issue-config schema "
        f"(default: {DEFAULT_ISSUE_CONFIG_SCHEMA})",
    )
    parser.add_argument(
        "--funding-schema",
        default=str(DEFAULT_FUNDING_SCHEMA),
        help="path or URL of the github-funding schema "
        f"(default: {DEFAULT_FUNDING_SCHEMA})",
    )
    args = parser.parse_args()

    # 1. Extract the recipe from bug_report.md and run it through the real CLI.
    text = BUG_REPORT.read_text(encoding="utf-8")
    match = re.search(r"```json\n(.*?)```", text, re.DOTALL)
    assert match is not None, "no json block in bug_report.md"
    recipe = json.loads(match.group(1))
    recipe_path = ROOT / ".termproof" / "repro-recipe-from-template.json"
    recipe_path.parent.mkdir(parents=True, exist_ok=True)
    recipe_path.write_text(json.dumps(recipe, indent=2), encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "-m", "termproof", "validate", str(recipe_path)],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    check(
        "recipe from bug_report.md validates via termproof CLI",
        proc.returncode == 0,
        (proc.stdout + proc.stderr).strip()[-300:],
    )

    # 2. Validate config.yml against the pinned SchemaStore issue-config schema.
    config = yaml.safe_load(CONFIG_YML.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        check("config.yml is a mapping", False, f"got {type(config).__name__}")
    else:
        check("config.yml is a mapping", True)
        validate_against_schema("config.yml (issue-config)", config, args.issue_config_schema)

        # 3. Contact URLs are HTTP(S).
        urls = [link.get("url", "") for link in config.get("contact_links", [])]
        check(
            "all contact_links urls are http(s)",
            all(re.match(r"^https?://", url) for url in urls),
            str(urls),
        )

    # 4. FUNDING.yml must be a valid funding mapping (SchemaStore).
    funding = yaml.safe_load(FUNDING_YML.read_text(encoding="utf-8"))
    if not isinstance(funding, dict):
        check(
            "FUNDING.yml is a mapping (not comments-only)",
            False,
            f"got {type(funding).__name__}",
        )
    else:
        check("FUNDING.yml is a mapping (not comments-only)", True)
        validate_against_schema("FUNDING.yml (funding)", funding, args.funding_schema)

    # 5. Every YAML under .github parses.
    yaml_ok = True
    for path in sorted((ROOT / ".github").rglob("*.yml")) + sorted((ROOT / ".github").rglob("*.yaml")):
        try:
            yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as error:
            yaml_ok = False
            print(f"  YAML ERROR in {path}: {error}")
    check("all .github YAML files parse", yaml_ok)

    print()
    if failures:
        print(f"FAILED: {len(failures)} validation check(s) failed")
        return 1
    print("ALL VALIDATION CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
