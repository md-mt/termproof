#!/usr/bin/env python3
"""Validation harness for the community-health remediation.

1. Copy/paste-check the bug_report.md recipe through TermProof's actual
   loader/schema (validate_recipe_file via the CLI entry point).
2. Validate .github/ISSUE_TEMPLATE/config.yml against the SchemaStore
   github-issue-config.json schema (downloaded to /tmp).
3. Parse every YAML under .github/ and all template frontmatter.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parent.parent
BUG_REPORT = ROOT / ".github" / "ISSUE_TEMPLATE" / "bug_report.md"
CONFIG_YML = ROOT / ".github" / "ISSUE_TEMPLATE" / "config.yml"
SCHEMA = Path("/tmp/github-issue-config.schema.json")

failures = []


def check(name: str, ok: bool, detail: str = "") -> None:
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        failures.append(name)


def main() -> int:
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

    # 2. Validate config.yml against the real SchemaStore schema.
    config = yaml.safe_load(CONFIG_YML.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    try:
        jsonschema.validate(instance=config, schema=schema)
        check("config.yml validates against SchemaStore issue-config schema", True)
    except jsonschema.ValidationError as error:
        check("config.yml validates against SchemaStore issue-config schema", False, str(error)[:300])

    # 3. Contact URLs are HTTP(S).
    urls = [link.get("url", "") for link in config.get("contact_links", [])]
    check(
        "all contact_links urls are http(s)",
        all(re.match(r"^https?://", url) for url in urls),
        str(urls),
    )

    # 4. Every YAML under .github parses.
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
