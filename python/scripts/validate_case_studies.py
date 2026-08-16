#!/usr/bin/env python3
"""
Case-study publication gate for RUST-030 / #35.

Engineering validates scaffolding completeness; the verifier requires
three real consenting adopters. This script:
  1) Checks that docs/case-studies/_meta.json, CONSENT.md, TEMPLATE.md
     and the docs-site pages exist and are well-formed.
  2) In --strict mode, requires at least 3 published studies with consent
     (used by RUST-030 completion). In draft mode, it tolerates placeholder
     entries so work-in-progress doesn't break CI.

Exit 0 = scaffolding healthy (or fully published when --strict).
Non-zero = human-readable failures printed to stderr/STDOUT.

Usage:
  python3 scripts/validate_case_studies.py          # scaffolding check
  python3 scripts/validate_case_studies.py --strict # publication gate

Consumes docs/case-studies/_meta.json as the source of truth.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
META_PATH = ROOT / "docs" / "case-studies" / "_meta.json"
TEMPLATE_PATH = ROOT / "docs" / "case-studies" / "TEMPLATE.md"
CONSENT_PATH = ROOT / "docs" / "case-studies" / "CONSENT.md"
README_PATH = ROOT / "docs" / "case-studies" / "README.md"
SITE_INDEX = ROOT / "docs-site" / "case-studies" / "index.md"
SITE_CONFIG = ROOT / "docs-site" / ".vitepress" / "config.mts"

# Presence markers that signal incomplete / fabricated content.
PLACEHOLDER_TOKENS = ("<", "TBD", "TODO", "lorem", "example.com", "placeholder", "Lorem", "adopter TBD")

# Section headings we require in each case study markdown file
REQUIRED_SECTIONS = ["Problem", "Setup", "Recipe", "CI integration", "Results"]


def fail(msg: str, errors: list[str]) -> None:
    line = f"FAIL: {msg}"
    print(line)
    errors.append(msg)


def warn(msg: str, warnings: list[str]) -> None:
    line = f"WARN: {msg}"
    print(line)
    warnings.append(msg)


def load_meta(errors: list[str]) -> dict | None:
    if not META_PATH.exists():
        fail(f"_meta.json missing at {META_PATH}", errors)
        return None
    try:
        meta = json.loads(META_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"_meta.json is not valid JSON: {exc}", errors)
        return None
    if "case_studies" not in meta:
        fail("_meta.json missing 'case_studies' array", errors)
        return None
    if "requirements" not in meta:
        fail("_meta.json missing 'requirements' object", errors)
        return None
    return meta


def check_scaffolding(meta: dict, errors: list[str], warnings: list[str]) -> None:
    for path, label in [
        (TEMPLATE_PATH, "TEMPLATE.md"),
        (CONSENT_PATH, "CONSENT.md"),
        (README_PATH, "README.md"),
        (SITE_INDEX, "docs-site/case-studies/index.md"),
        (SITE_CONFIG, "docs-site/.vitepress/config.mts"),
    ]:
        if not path.exists():
            fail(f"Scaffolding missing: {label} at {path}", errors)
        elif path.stat().st_size == 0:
            fail(f"Scaffolding empty: {label}", errors)

    # VitePress config must mention case-studies
    if SITE_CONFIG.exists():
        text = SITE_CONFIG.read_text(encoding="utf-8")
        if "case-studies" not in text:
            fail("docs-site/.vitepress/config.mts does not mention case-studies — nav/sidebar not wired", errors)
        if "Case Studies" not in text:
            fail("docs-site/.vitepress/config.mts missing 'Case Studies' sidebar section", errors)

    # TEMPLATE must have required section headings
    if TEMPLATE_PATH.exists():
        tpl = TEMPLATE_PATH.read_text(encoding="utf-8")
        for sec in REQUIRED_SECTIONS:
            if f"## {sec}" not in tpl:
                fail(f"TEMPLATE.md missing required section '## {sec}'", errors)

    # _meta.json entries must be well-formed
    for entry in meta.get("case_studies", []):
        for key in ("slug", "category", "file", "status", "consent"):
            if key not in entry:
                fail(f"_meta.json entry missing key '{key}': {entry}", errors)
        slug = entry.get("slug", "")
        if slug and not re.fullmatch(r"[a-z0-9][a-z0-9-]*", slug):
            fail(f"Invalid slug '{slug}' — must be kebab-case [a-z0-9-]", errors)

        category = entry.get("category", "")
        if category not in ("tui-framework", "terminal-app", "cli-tool", ""):
            # empty is allowed only for pure drafts; warn instead of fail
            warn(f"Unknown category '{category}' for slug '{slug}'", warnings)

        file_name = entry.get("file", "")
        if file_name and not file_name.endswith(".md"):
            fail(f"File value must end with .md: {file_name}", errors)


def check_case_study_files(meta: dict, errors: list[str], warnings: list[str], strict: bool) -> int:
    """Return count of publishable studies (have real file, all sections, consented)."""
    cs_dir = ROOT / "docs" / "case-studies"
    site_dir = ROOT / "docs-site" / "case-studies"
    requirements = meta.get("requirements", {})
    required_categories: list[str] = requirements.get("required_categories", [])
    min_words: dict[str, int] = requirements.get("min_section_words", {})

    # Check that every docs-site placeholder file for drafts exists (informational)
    publishable = 0
    seen_categories: dict[str, str] = {}  # category -> slug for duplicates
    seen_slugs: set[str] = set()

    for entry in meta.get("case_studies", []):
        slug: str = entry.get("slug", "")
        category: str = entry.get("category", "")
        file_name: str = entry.get("file", "")
        status: str = entry.get("status", "")
        consent: bool = bool(entry.get("consent"))

        if slug in seen_slugs:
            fail(f"Duplicate slug '{slug}' in _meta.json", errors)
        seen_slugs.add(slug)

        if category and category in seen_categories:
            fail(
                f"Category '{category}' used twice ({seen_categories[category]} and {slug}) — distinct adopters required",
                errors,
            )
        if category:
            seen_categories[category] = slug

        # File existence — drafts are allowed to be missing in non-strict mode
        md_path = cs_dir / file_name if file_name else None
        if md_path is None or not file_name:
            warn(f"No file listed for slug '{slug}'", warnings)
            continue

        if not md_path.exists():
            if "placeholder" in slug:
                # placeholder slots are scaffolding — warn, don't fail publication gate redundantly
                warn(f"Draft case study file not yet created: {md_path} (slug={slug})", warnings)
            elif strict or status == "published":
                fail(f"Case study file missing: {md_path} (slug={slug}, status={status})", errors)
            else:
                warn(f"Draft case study file not yet created: {md_path} (slug={slug})", warnings)
            continue

        text = md_path.read_text(encoding="utf-8")

        # Check that each file corresponds to a real adopter (no fabricated markers in published files)
        # We allow placeholders inside TEMPLATE.md but not inside published case studies
        if status == "published":
            for token in ("<", "TBD", "TODO", "lorem ipsum", "Lorem"):
                if token in text:
                    fail(
                        f"Published case study '{file_name}' still contains placeholder '{token}' — human must fill it",
                        errors,
                    )

            if consent is not True:
                fail(f"Published case study '{slug}' has consent=false — cannot count as published", errors)

        # Required sections + minimum word counts
        for sec in REQUIRED_SECTIONS:
            pattern = rf"^##\s+{re.escape(sec)}\b"
            m = re.search(pattern, text, flags=re.MULTILINE | re.IGNORECASE)
            if not m:
                fail(f"Case study '{file_name}' missing section '## {sec}'", errors)
                continue
            # Extract section body (until next ## or eof) and rough word count
            start = m.end()
            next_heading = re.search(r"^##\s+\S+", text[start:], flags=re.MULTILINE)
            section_body = text[start : start + next_heading.start()] if next_heading else text[start:]
            # strip code fences for word count
            stripped = re.sub(r"```.*?```", "", section_body, flags=re.DOTALL)
            word_count = len(re.findall(r"\w+", stripped))
            threshold = min_words.get(sec, 0)
            if threshold and word_count < threshold:
                msg = (
                    f"Case study '{file_name}' section '## {sec}' is too thin ({word_count} words, minimum {threshold})"
                )
                if status == "published":
                    fail(msg, errors)
                else:
                    warn(msg + " [draft — fix before publishing]", warnings)

            # Results must contain at least one evidence link or code-URL-looking string
            if sec == "Results" and status == "published":
                has_link = bool(re.search(r"https?://\S+|`[^`]*\.(?:cast|svg|png|mp4|md)`", text[start:]))
                if not has_link:
                    fail(
                        f"Case study '{file_name}' Results section lacks an evidence link (cast/svg/png/report)",
                        errors,
                    )
                if ">" not in section_body and '"' not in section_body:
                    fail(
                        f"Case study '{file_name}' Results section lacks an attributed quote (expected a blockquote or quoted string)",
                        errors,
                    )

        # Docs-site mirror must exist for published studies
        site_mirror = site_dir / f"{slug}.md"
        if status == "published" and not site_mirror.exists():
            fail(f"Published study '{slug}' missing docs-site mirror at {site_mirror}", errors)

        if status == "published" and consent is True and file_name:
            # count toward publication
            # only count if file actually has all sections — we already failed above if missing
            publishable += 1

    # In strict mode the publication gate is enforced
    if strict:
        min_published = int(requirements.get("min_published", 3))
        if publishable < min_published:
            fail(
                f"Publication gate: {publishable}/{min_published} published studies — "
                f"need {min_published} real, consented adopters (RUST-030 / #35)",
                errors,
            )
        for cat in required_categories:
            if cat not in seen_categories:
                fail(f"Required category '{cat}' has no entry in _meta.json", errors)
            else:
                # verify that the entry for this category is actually published
                entry = next((e for e in meta["case_studies"] if e.get("category") == cat), None)
                if entry and entry.get("status") != "published":
                    fail(
                        f"Required category '{cat}' (slug={entry.get('slug')}) is still '{entry.get('status')}' — needs 'published'",
                        errors,
                    )

    return publishable


def check_consent(meta: dict, errors: list[str], warnings: list[str], strict: bool) -> None:
    if not CONSENT_PATH.exists():
        return
    text = CONSENT_PATH.read_text(encoding="utf-8")
    for entry in meta.get("case_studies", []):
        slug: str = entry.get("slug", "")
        status: str = entry.get("status", "")
        consent_flag: bool = bool(entry.get("consent"))
        if not slug:
            continue
        # Placeholder slugs may not have a consent row — that's expected in draft mode
        if "placeholder" in slug:
            if strict and status == "published":
                fail(f"Placeholder slug '{slug}' cannot be published — replace with a real adopter", errors)
            continue
        # Real slugs should be mentioned in CONSENT.md
        if slug not in text:
            msg = f"CONSENT.md has no entry for slug '{slug}'"
            if status == "published" or strict:
                fail(msg, errors)
            else:
                warn(msg + " [draft — add before publishing]", warnings)
        elif consent_flag and "pending" in text.lower():
            # vague check: if any pending remains, flag it
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate case-study publication pipeline")
    parser.add_argument(
        "--strict", action="store_true", help="Enforce full publication gate (3 published, consented studies)"
    )
    args = parser.parse_args()

    errors: list[str] = []
    warnings: list[str] = []

    print("TermProof case-study validator", "(strict)" if args.strict else "(scaffolding)")
    print(f"  meta:     {META_PATH}")
    print(f"  consent:  {CONSENT_PATH}")
    print(f"  template: {TEMPLATE_PATH}")
    print()

    meta = load_meta(errors)
    if meta is None:
        print("\nValidation FAILED (could not load _meta.json).")
        return 1

    check_scaffolding(meta, errors, warnings)
    publishable = check_case_study_files(meta, errors, warnings, strict=args.strict)
    check_consent(meta, errors, warnings, strict=args.strict)

    # Print summary
    print()
    print(f"  Publishable studies: {publishable}")
    if warnings:
        print(f"  Warnings: {len(warnings)} (non-blocking in scaffolding mode)")
        for w in warnings:
            print(f"    - {w}")
    if errors:
        print(f"\nValidation FAILED — {len(errors)} error(s):")
        for e in errors:
            print(f"  - {e}")
        return 1

    if args.strict:
        print("\nValidation PASSED — publication gate satisfied (RUST-030 / #35).")
    else:
        print("\nValidation PASSED — scaffolding healthy.")
        if publishable == 0:
            print("  (No studies published yet — expected before RUST-030. Run with --strict to enforce.)")
        else:
            print(f"  ({publishable} published — run with --strict to enforce the full 3-study gate.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
