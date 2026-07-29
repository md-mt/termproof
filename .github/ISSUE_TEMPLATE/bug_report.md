---
name: Bug report
about: Report a reproducible bug in TermProof
title: "bug: <short description>"
labels: ["bug"]
assignees: []
---

<!--
Before filing: please search existing issues first (open and closed).
For security vulnerabilities, do NOT open a public issue — email md@mt.com
instead (see SECURITY.md).
-->

## What happened

A clear description of the bug: what you observed vs. what you expected.

**Observed:**

**Expected:**

## Reproduction recipe

The `*.recipe.json` (or a minimal reduction of it) that triggers the bug.
Reproductions must be deterministic and runnable in CI.

```json
{
  "name": "repro",
  "command": ["..."],
  "steps": []
}
```

## `termproof --help` output

<details>
<summary>termproof --help</summary>

```text
$ termproof --help
...paste output here...
```

</details>

## Environment

- TermProof version: <!-- e.g. 0.2.0 (run `termproof --version`) -->
- Python version: <!-- run `python --version` -->
- OS / architecture: <!-- e.g. macOS 14 arm64, Ubuntu 24.04 x86_64 -->
- `ffmpeg` / `agg` available: <!-- yes/no, only relevant for --video/render -->

## Additional context

Logs, a `.cast` file, screenshots, or anything else that helps. Avoid
attaching large binaries — link to a gist or trimmed artifact instead.

## Area (optional)

If you know which area this touches, add one of the area labels:
`area:core`, `area:cli`, `area:ci`, `area:docs`, `area:community`,
`area:distro`, `area:plugins`.
