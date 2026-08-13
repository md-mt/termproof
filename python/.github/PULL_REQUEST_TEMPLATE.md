<!--
Thanks for contributing to TermProof! Please read CONTRIBUTING.md.
All changes go through pull requests — no direct commits to `main`.
Open as a draft early and request review when CI is green.
-->

## Summary

What does this PR do and why? Keep changes small and incremental
(~100 lines of logic, <200 with tests). Split larger work into stacked PRs.

## Linked issue

<!-- Use a closing keyword so the issue auto-closes on merge. -->

Closes #

## Test plan

How did you verify this change?

```bash
uv run python -m unittest discover -s tests
uv build
# if you touched runner/renderer/video:
uv run termproof run examples/generic --video --out .termproof/ci
```

- [ ] Added/updated unit tests for behavioral changes
- [ ] Screenshots / evidence attached (if UX or output changed)

## Tidy First

Following Tidy First, structural moves and behavioral changes are not mixed in
the same diff.

- [ ] This PR is a **structural** change only (renames/moves/formatting), OR
- [ ] This PR is a **behavioral** change only, OR
- [ ] N/A (docs / chore)

## Checklist

- [ ] Title and commits follow Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`)
- [ ] No comments/docstrings/type hints added to untouched code
- [ ] Branch follows naming convention (`feat/`, `fix/`, `docs/`, `refactor/`, `chore/`)
- [ ] No large binaries checked in (`examples/artifacts/` kept lean)
- [ ] Backward-compatibility contract respected (legacy `tui-verifier` paths / plugin prefix — see CONTRIBUTING.md)
