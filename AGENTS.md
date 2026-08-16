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

Renderers and video backends reach that config through the optional
`from_config` classmethod owned by
[`docs/plugin-protocols.md`](docs/plugin-protocols.md);
`runner._construct_evidence_plugin` is the call site.

`termproof/screen.py:render_svg` is a thin wrapper over
`builtin_renderers.SvgRenderer` — it constructs the renderer and calls it. There
is one renderer, not two copies to keep in step, so a rendering change goes in
`SvgRenderer` (or in `attributed.screen_svg` beneath it) and reaches both entry
points. `tests/test_evidence_config.py` pins that the wrapper stays a wrapper.

Renderers may implement an optional `render_attributed(screen, ...)` alongside
`render(text, ...)`; `evidence._render_screen` prefers it when the pipeline has
a grid. It is additive — a renderer with only `render` still works and still
gets text. Do not make it required: third-party renderers are written against
the text-only protocol, and `docs/plugin-protocols.md` promises they keep
working.

The defaults are load-bearing: `tests/test_evidence_config.py` replays every
`session.cast` under `examples/artifacts/` and asserts the re-rendered SVG is
byte-identical to the checked-in one. Changing a default breaks that test by
design — the checked-in corpus is the contract. Each artifact is re-rendered
through the same path `evidence.render_artifacts` uses for it, so the gate pins
what the product actually writes; do not "simplify" it back to rendering
everything from text.

## Why `examples/colorstress/` exists

Screenshots render from an attributed per-cell grid, so colour and text
attributes survive into the SVG. Every other example recipe drives a monochrome
TUI, which means byte-identity against the rest of the corpus would hold just as
well for a renderer that had thrown every attribute away — the bytes would be
wrong in a consistent, reproducible way, and no assertion would notice.

`examples/colorstress/` is the only corpus entry that can catch a regression
back to monochrome. Its recorded run under
`examples/artifacts/colour-stress/` emits 16-colour, 256-colour and 24-bit
truecolour cells, the full set of SGR attributes, box drawing and wide CJK
characters, and its `final.svg` carries several hundred distinct fill colours.
`CorpusByteIdentityTest.test_the_corpus_still_holds_a_screen_that_is_not_monochrome`
fails if that entry goes missing or goes grey.

Do not "simplify" the fixture to a plain TUI, and do not drop its corpus entry
to make a rendering diff smaller. See
[`docs/evidence-quality.md`](docs/evidence-quality.md).
