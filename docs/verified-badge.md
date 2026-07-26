# Verified by TermProof badge

Projects that verify their terminal or TUI with TermProof can display the badge in their README. It signals that evidence (casts, screenshots, videos, reports) exists and is reviewed in CI.

## Badge

![Verified by TermProof](https://img.shields.io/badge/verified%20by-TermProof-0a7a2e?style=flat-square)

### Markdown (recommended)

```md
[![Verified by TermProof](https://img.shields.io/badge/verified%20by-TermProof-0a7a2e?style=flat-square)](https://github.com/md-mt/termproof)
```

### HTML

```html
<a href="https://github.com/md-mt/termproof">
  <img src="https://img.shields.io/badge/verified%20by-TermProof-0a7a2e?style=flat-square" alt="Verified by TermProof">
</a>
```

### Variants

| Style | URL |
| --- | --- |
| Flat square (default) | `https://img.shields.io/badge/verified%20by-TermProof-0a7a2e?style=flat-square` |
| Flat | `https://img.shields.io/badge/verified%20by-TermProof-0a7a2e?style=flat` |
| Plastic | `https://img.shields.io/badge/verified%20by-TermProof-0a7a2e?style=plastic` |
| For-the-badge | `https://img.shields.io/badge/verified%20by-TermProof-0a7a2e?style=for-the-badge` |

Examples:

- Flat square:

  [![Verified by TermProof](https://img.shields.io/badge/verified%20by-TermProof-0a7a2e?style=flat-square)](https://github.com/md-mt/termproof)

  ```md
  [![Verified by TermProof](https://img.shields.io/badge/verified%20by-TermProof-0a7a2e?style=flat-square)](https://github.com/md-mt/termproof)
  ```

- Flat plastic:

  [![Verified by TermProof](https://img.shields.io/badge/verified%20by-TermProof-0a7a2e?style=plastic)](https://github.com/md-mt/termproof)

  ```md
  [![Verified by TermProof](https://img.shields.io/badge/verified%20by-TermProof-0a7a2e?style=plastic)](https://github.com/md-mt/termproof)
  ```

## Guidelines

- Link the badge to `https://github.com/md-mt/termproof`.
- Use it only if your repository runs TermProof in CI and exposes evidence (artifact, release asset, or checked-in `examples/artifacts/`-style report).
- Prefer the flat-square style for consistency with this repository.
- If you use a custom color, keep the text `verified by TermProof` to preserve recognition.

## Adoption

Add your project to [`docs/plugins.md`](plugins.md) or open a PR mentioning the badge once it is live — we will include you in the community list and in the Pages site.

## Verification check (optional)

If you want to prove the badge is backed by evidence, add this to your CI summary:

```bash
cat .termproof/ci/latest-report.md >> "$GITHUB_STEP_SUMMARY"
```

Or link to your evidence artifact from your README alongside the badge:

```md
[![Verified by TermProof](https://img.shields.io/badge/verified%20by-TermProof-0a7a2e?style=flat-square)](https://github.com/md-mt/termproof) — [evidence](https://github.com/<you>/<repo>/actions)
```
