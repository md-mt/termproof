# TermProof Pages Site

This directory is the source for the GitHub Pages demo at https://md-mt.github.io/termproof/ (when enabled).

## Contents

- `index.html` — landing: what, comparison, demo, 3-command quickstart, CI snippet, badge, community.
- `getting-started.html` — install, scaffold, run, recipe anatomy, steps, assertions.
- `evidence.html` — sample evidence structure, checked-in artifacts, the generic and agent-UI example sets, CI evidence.
- `comparison.html` — why TermProof vs screenshots / expect / Playwright / VHS / asciinema.
- `plugins.html` — community plugin directory (mirrors `docs/plugins.md` but rendered as HTML).
- `assets/style.css` — minimal dark theme, no dependencies.

## Local preview

```bash
python3 -m http.server 8000 --directory site
# open http://localhost:8000
```

## Pages deployment

Workflow: `.github/workflows/pages.yml`

- **Build** job: copies `site/` to `_site/`, copies `docs/`, copies curated evidence from `site/artifacts/`, and creates an artifact preview. Runs on push to `main` **and** on pull requests touching `site/**`, `docs/**`, `README.md`, `examples/artifacts/**`.
- **Validate relative links** step: after building `_site`, checks that every relative `href`/`src` in the HTML files resolves inside `_site`. Fails the build if any link is broken.
- **Deploy** job: guarded for private repos. Deploys only if:
  - `vars.ENABLE_PAGES == 'true'` OR
  - repository visibility is public
  - Only on push to `main` or `workflow_dispatch` (not on PR builds).
- **Private-repo safety**: when the guard fails, a `deploy-skipped` job explains how to enable Pages and leaves the preview artifact `termproof-pages-preview` for review.

To enable on this private repo:

1. Settings → Pages → Source: GitHub Actions
2. Settings → Secrets and variables → Actions → Variables → New: `ENABLE_PAGES=true`
3. Re-run workflow or push to `main`.

The site is static HTML, no Jekyll build needed, so it works even when artifacts contain large SVGs/MP4s elsewhere.

## Dogfooding

The site itself is inspired by TermProof evidence principles: real casts, screenshots, and reports are hosted via the CI artifacts `termproof-ci-evidence` and release assets `termproof-release-evidence.tgz`. The Pages site links to those, rather than duplicating binaries, to stay within GitHub Pages size limits.
