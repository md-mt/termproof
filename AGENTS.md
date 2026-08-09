# AGENTS.md

## PTY tests must not depend on how fast the child starts

`wait_for_idle` must not arm its stable window before the child's first byte:
until something has been emitted, a blank screen is a session that has not
started, not a session that has settled.

The test-side corollary is that a PTY test must never depend on first output
arriving within `stable_seconds`. Time-to-first-PTY-byte is environment-bound —
a cold interpreter (for example the ephemeral overlay `uv run --with <pkg>`
builds per invocation) or a loaded machine measures ~0.35 s against a warm
~0.10 s, which is enough to cross a 0.3 s window. Gate on observed output with
`wait_for_text` before measuring quiescence, rather than assuming the child is
already talking. Both directions of the arming rule are pinned by
`QuiescenceBehaviorTest` in `tests/test_runner.py`.

## Evidence rendering

Every screenshot and video parameter lives under `evidence:` in the cascading
config (`termproof/config.py`), not as a literal in a renderer. Unknown keys
under `evidence` raise rather than being ignored, because a misspelled rendering
knob that silently does nothing looks exactly like one that had no effect.

Renderers and video backends reach that config by declaring an optional
`from_config(cls, evidence)` classmethod; `runner._construct_evidence_plugin`
calls it when present and falls back to `cls()` otherwise, so third-party
plugins written against the bare protocols keep working.

`termproof/screen.py:render_svg` is a deliberate duplicate of
`builtin_renderers.SvgRenderer`. Any change to one must be applied to both;
`tests/test_evidence_config.py` pins them together until the duplicate is
removed in a separate structural change.

The defaults are load-bearing: `tests/test_evidence_config.py` replays every
`session.cast` under `examples/artifacts/` and asserts the re-rendered SVG is
byte-identical to the checked-in one. Changing a default breaks that test by
design — the checked-in corpus is the contract.

## Why `examples/colorstress/` exists

`screen.py` flattens pyte's buffer to plain text, so all colour and attributes
are discarded before any renderer runs. Every other example recipe is
monochrome, so no test in the corpus could detect that. The colour-stress
fixture is the only recipe that can. Do not "simplify" it to a plain TUI. See
[`docs/evidence-quality.md`](docs/evidence-quality.md).
