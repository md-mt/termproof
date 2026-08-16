---
name: Feature request
about: Propose an enhancement or new capability for TermProof
title: "feat: <short description>"
labels: ["enhancement"]
assignees: []
---

<!--
Before filing: please search existing issues first.
Questions and open-ended ideas are welcome as GitHub issues — see SUPPORT.md.
-->

## Which implementation

- [ ] Python (`python/`)
- [ ] Rust (`rust/`)
- [ ] Both — the recipe format, the spec, or the conformance corpus

## Problem / motivation

What problem are you trying to solve? What is the current behavior and why is
it insufficient? Link any related issues.

## Proposed solution

Describe the feature or change you'd like. If it affects recipe semantics or
artifact contracts, note that explicitly (these require a minor/major version
bump per `python/docs/releases.md`).

## Alternatives considered

Other approaches you evaluated and why you didn't choose them.

## Scope / contribution ladder

Where does this land on the contribution ladder (see CONTRIBUTING.md)?

- [ ] Recipe (a `python/examples/*.recipe.json`)
- [ ] Plugin (external step / assertion / backend / reporter)
- [ ] Core change (`python/termproof/` or `rust/crates/` internals)

## Additional context

Mockups, example recipes, prior art, or anything else that clarifies the ask.

## Area (optional)

Add one of the area labels if you know which area this touches:
`area:core`, `area:cli`, `area:ci`, `area:docs`, `area:community`,
`area:distro`, `area:plugins`.
