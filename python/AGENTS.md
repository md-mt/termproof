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

### Where a user-visible claim can live

A claim about what the artifacts contain drifts across surfaces, and correcting
it by hand does not converge — three consecutive review rounds each found the
same overclaim surviving somewhere the previous sweep had not reached:
module docstrings, then the PR body, then the published site page.

`tests/test_public_claims.py` now does the sweep. It enumerates tracked files
from `git ls-files` rather than a hand-written list, so a new page is covered the
day it is added, and it fails on phrasings that have actually had to be
withdrawn. When you correct a claim, add its phrasing there rather than only
fixing the file you found it in. The surfaces it covers:

- prose: `*.md` anywhere — root, `docs/`, `docs-site/`, `examples/**/README.md`,
  `plugin-template/`, case studies, launch and outreach copy
- the published site: `site/*.html`, including `<meta>` description and social tags
- code: every `*.py`, module docstrings included
- package and distribution metadata: `pyproject.toml` (description, keywords),
  `Formula/termproof.rb`, `action.yml`, `docker/*Dockerfile`,
  `docs-site/.vitepress/config.mts`
- example fixtures whose output is published as evidence — `examples/apps/*.py`
  print text that lands in the corpus screenshots
- `*.sh`, `*.json`, `*.yml`

Not covered, deliberately: `examples/artifacts/**` and `site/artifacts/**` are
recorded evidence, not prose — a stale claim inside a recording is a fact about
when it was recorded. `docs/evidence/*.png` are research images that cannot be
linted; check them by eye if the claim they illustrate changes. The PR body is
not a tracked file, so it stays a manual check.

### What the grid actually carries

Two limits, both pinned by tests; check them before making any blanket claim
about colour in the artifacts:

- **A step screenshot renders from the grid only when the session reported
  one.** `StepResult.screen_attributed` is optional and defaults to `None`;
  `evidence._render_step_screens` falls back to re-parsing `StepResult.screen`,
  which is flattened text and therefore monochrome. Every built-in session
  backend reports a grid, so on a stock install the `steps/` images carry
  colour — but "TermProof step screenshots are in colour" is still an
  overclaim, because a third-party `SessionBackend` need not implement
  `screen_attributed()`. Say "when the session supplies a grid".
- **The `png` renderer has no `render_attributed`,** so a PNG step screenshot is
  monochrome however colourful the grid is. Colour in step screenshots is a
  property of the `svg` renderer.
- **Dim (SGR 2) is lost on the cast-replay path and on the pty session**,
  because pyte 0.8.2's `Char` has no dim field. A grid parsed from SGR text —
  the tmux backend's `capture-pane -e` — does carry it. Do not list dim as a
  supported attribute of a screenshot without saying which path.
- **The corpus gate re-renders step entries from their recorded `.txt`.** That
  matches how those entries were recorded, but it is no longer how a live run
  produces a step image. Nothing on disk carries a step's grid, so regenerating
  the corpus from a colour-emitting recipe needs the gate extended at the same
  time. See `CorpusByteIdentityTest`.

Reading a screen for a step goes through `screen.capture_screen`, which reads
the grid first and derives the text from it. Do not "simplify" it back into two
reads: text and grid fetched separately can come from different instants, and
the result is a `steps/NN.txt` that describes one screen while `steps/NN.svg`
and the dedup verdict describe another. The Rust `ScreenSource::capture_screen`
makes the same choice for the same reason.

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
