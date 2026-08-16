# Getting help with TermProof

One tracker, one project, two implementations. Here is where to go depending
on what you need.

## Before you ask

- [`README.md`](README.md) — what TermProof is, and which implementation to
  reach for.
- [`rust/docs/status-and-parity.md`](rust/docs/status-and-parity.md) — read
  this before asking why the Rust CLI does not do something the Python one
  does. Most "why doesn't this work the way I expect" questions about the Rust
  implementation are answered there, including the list of what a run still
  cannot do.
- [`conformance/README.md`](conformance/README.md) — the measured differences
  between the two implementations, with the numbers.

## Questions & ideas

For usage questions, "how do I verify X?", recipe help, and open-ended
proposals, open a **[GitHub issue](https://github.com/md-mt/termproof/issues)**
using the closest template. Issues are searchable and let the whole community
benefit from answers. The issue tracker is the only channel — there is no
separate forum, chat or mailing list.

## Bug reports & feature requests

Open a **[GitHub issue](https://github.com/md-mt/termproof/issues)** using the
appropriate template:

- **Bug report** — say which implementation you are running, and include a
  reproduction recipe, `termproof --help` output, your Python or Rust
  toolchain version, OS, and observed vs. expected behaviour.
- **Feature request** — describe the problem, the proposed solution, and where
  it lands on the contribution ladder.
- **Parity gap** — when the two implementations disagree on the same recipe.
  The Python implementation is the behavioural oracle, so a disagreement is a
  gap in the Rust port until measured otherwise.

Please search existing issues (open and closed) before filing a new one.

## Security issues

**Do not** open a public issue for security vulnerabilities. Use the private
reporting path in [SECURITY.md](SECURITY.md) — GitHub's *Report a
vulnerability* form, or the address listed there.

## What support you can expect

This is a small, best-effort, pre-1.0 project. The maintainers answer issues
as time allows — there is **no SLA** and no guaranteed response time. Issues
that are clearly answered by the README, the docs, or a search of the tracker
may be closed with a pointer rather than a full reply.

## Contributing

Want to help? See [CONTRIBUTING.md](CONTRIBUTING.md) for the contribution
ladder, per-implementation setup, and the PR-only process. All participants
are expected to follow our [Code of Conduct](CODE_OF_CONDUCT.md).

## Documentation

- [`README.md`](README.md) — the front door for both implementations.
- [`spec/`](spec) — the recipe format and the built-in step and assertion
  semantics both implementations answer to.
- [`python/docs/`](python/docs) — guides, recipe packs, CI templates,
  plugins, release flow.
- [`rust/docs/`](rust/docs) — status and parity, architecture, engineering
  baseline, publishing.
