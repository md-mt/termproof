# Handoff: `thin-consumer-api` branch

**Written:** 2026-08-19
**Branch:** `thin-consumer-api`, 5 commits on top of `main` (`3d2367e`)
**Status:** unpushed. Rust is **compiled but never tested**. Python is fully tested.

This branch makes `termproof` usable by a consumer whose recipes are imperative
— they branch on what the screen shows — which is what the MetaCode TUI
validator in `fbsource` is. Everything here is additive; nothing existing
changes signature or behaviour.

Read §3 first. It is the list of things I could not verify.

---

## 1. What is on the branch

| commit | what |
|---|---|
| `4ce382a` | `EvidenceCollector::capture_text` — record a screen the caller already holds |
| `7a2ed9e` | `Recording` + `attach_recording` + `recordings` in the manifest |
| `9839122` | `selection::Selectable` and `before_after::Comparable` — generic over the caller's own types |
| `6be5ba8` | `fancy-regex` narrowed `>=0.16,<0.20` → `>=0.16,<0.17` |
| `1430b18` | `python/termproof/collector.py` — the evidence collector Rust already had |

Each commit message carries its own rationale; this document only covers what
the messages cannot, which is what was not checked.

---

## 2. The environment this was written in

**There is no `cargo` on the devserver and no way to install one.**
`static.rust-lang.org` and `sh.rustup.rs` both return 403 through Meta's
fwdproxy — the same egress control that blocks github.com. So:

- **No Rust test ever ran.** Not one. The `#[cfg(test)]` blocks I added are
  unexecuted code.
- **No `clippy`, no `rustfmt`.** Formatting may not match `cargo fmt`.
- **No `cargo package`, no semver-checks, no `cargo deny`.**

What I *could* do is compile the library, by copying `rust/crates/termproof/src`
over fbsource's vendored `third-party/rust/vendor/termproof-0.3.4/src` and
running `buck2 build fbsource//third-party/rust:termproof`. I validated that
this check can fail before trusting it: injecting a call to a non-existent
method produced `rc=3` and `error[E0599]`. So **the Rust code compiles**, with
`--all-features` unknown and tests uncompiled.

Python was fine: `python3 -m venv` plus `pip --proxy http://fwdproxy:8080`
gives a working environment. **757 tests, ruff clean, mypy clean.** The single
failure, `test_version_bump.DryRunAgainstTheRealTreeTest`, shells out to
`cargo` and is environmental.

---

## 3. First thing to run on the laptop

```sh
cd rust
cargo fmt --all                       # expect churn; none of it was checked
cargo test --workspace                # the real gate, never run
cargo clippy --workspace --all-targets --all-features -- -D warnings
cd ../python
uv run coverage run -m unittest discover -s tests
uv run ruff check . && uv run mypy termproof
```

Then, because the `fancy-regex` change touches resolution:

```sh
cargo update -p fancy-regex --dry-run     # should be a no-op: lock is 0.16.2
cargo test --workspace                    # the floor-testing CI step covers 0.16
```

---

## 4. Specific things I am unsure about

### 4.1 `fancy-regex` — the change most likely to be wrong

`6be5ba8` narrows `>=0.16, <0.20` to `>=0.16, <0.17`.

**The reasoning.** The manifest comment already said the intent was to collapse
onto one copy, shared with `jsonschema`'s `^0.16`. It does not do that. These
are 0.x releases, so cargo will not unify across 0.16/0.17/0.18/0.19 and takes
the highest in range. The workspace lockfile hid it — we resolve to 0.16.2 —
but a fresh resolve gets 0.19.0. Observed: vendoring 0.3.4 into fbsource, which
already carried 0.16.2, 0.17.0 and 0.18.0, still added 0.19.0 as a seventh copy
and tripped a duplicate-dependency check. I confirmed with
`buck2 cquery 'deps(fbsource//third-party/rust:termproof)'` that it resolves to
`fancy-regex-0.19.0` today.

**What I could not check.** That the crate actually *compiles* against 0.16.2 —
that requires cargo. The manifest says "tested at 0.16.2" and the CI floor step
exercises it, and the lock is already 0.16.2, so this should be a no-op. But it
is a resolution change and I could not run a resolution.

**If it breaks:** the fallback is `>=0.16, <0.20` plus a documented note telling
vendoring consumers to pin. Worse, but honest.

### 4.2 The Rust tests are unexecuted

Highest risk of a silly failure, in rough order:

- `recordings_reach_the_manifest_alongside_the_steps` and
  `a_run_with_no_recordings_writes_the_document_it_always_wrote` use the
  existing `identity()` / `session()` / `tempfile::tempdir()` helpers. I checked
  they exist at the right paths but never ran them.
- `a_foreign_recipe_type_can_be_selected` and friends in `selection.rs` define a
  local struct implementing `Selectable`. The `cfg()` helper they use is the
  existing one; I assumed its `harness_root` is `"verify/"` from reading the
  other tests.
- `before_after.rs`'s `ProductResult` has `#[allow(dead_code)]` on
  `agent_model` — clippy may want that differently.

The one real compile bug I did hit and fix was `key(r)` inside
`.find(|r| ...)`, where `r` is `&&R` and the generic inferred `&R: Comparable`.
Fixed by `key(*r)`. There may be more of that shape in code paths the library
build does not reach.

### 4.3 `BeforeAfterResult<R = RunResult>`

A default type parameter keeps the bare name meaning what it meant, but it is
a breaking-ish change for anyone who wrote `BeforeAfterResult` in a position
requiring an explicit parameter. I believe there are none in-tree. `cargo
semver-checks` will say; I could not run it.

### 4.4 The Python collector duplicates rather than replaces

`python/termproof/collector.py` is **new and unused** — nothing in the Python
package calls it yet. `termproof.evidence`'s module functions still do what
they did. That is deliberate for a first landing, but it means:

- the two now have overlapping responsibilities, and `evidence.render_artifacts`
  has its own step-screenshot dedup that does not share code with the
  collector's;
- `EvidenceManifest` here has no `attach_to`, because Python's `RunResult` has
  no equivalent of the Rust `artifacts` merge contract. Worth adding.

Consolidating them is the obvious follow-up and I did not attempt it.

### 4.5 Cross-implementation shape

`CrossImplementationShapeTest` asserts the manifest key set matches Rust's by
spelling it out. **I derived that list by reading the Rust structs, not by
running both and diffing.** Once you have cargo, generate a manifest from each
side against the same input and diff the JSON. That is the check that actually
proves it, and it is worth adding to `conformance/`.

Known intentional difference: Rust's `RunIdentity` has a `run_id` constructor
with more logic (`from_run_dir`); Python's is a plain dataclass.

---

## 5. Things I deliberately did not do

**`ScreenSource` was not widened to three methods.** The fbsource consumer
implements `get_screen`/`get_raw_output`/`get_attributed_screen`. Upstream's
single `capture_screen` is the better design for the reason its docstring
gives, so the consumer should adapt. Do not "fix" this upstream.

**The declarative/imperative recipe split was not touched.** `Recipe` stays
declarative. The consumer keeps its own recipe type and drives the library.
This is documented as out of scope and is correct.

**Nothing was published.** No PyPI, no crates.io, no tag, no version bump.
`0.3.4` is still what the manifests say. A release will need a version bump
across both plus a CHANGELOG entry — none of which I wrote, because the shape
of the release is yours to choose.

**No PR.** github.com is unreachable from the agent. Push and open it yourself;
the five commit messages are written to stand as the PR body if you want to
squash, or to be read individually if you don't.

---

## 6. Why each piece exists — the consumer's side

For context on what these unblock, the consumer is
`fbsource//users/me/mengwei/metacode_validate` (Rust) and
`fbcode//3pai_tooling/metacode/e2e_tests/metacode_e2e/validation` (Python).

| upstream addition | what it lets the consumer delete |
|---|---|
| `capture_text`, `Recording`, `attach_recording` | `evidence.rs` (1,012) / `evidence.py` (474) |
| `Selectable` | `ci_selection.rs` (240) |
| `Comparable` | `before_after.rs` (161) |
| Python `collector.py` | the Python `EvidenceCollector` half of `evidence.py` |

The consumer cannot use any of it until a release is cut and vendored, which is
why none of the corresponding fbsource work is on this branch.

---

## 7. If you only do one thing

Run `cargo test --workspace`. Everything else in this document is a footnote to
the fact that it has never run.
