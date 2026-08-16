# Colour Stress Recipe Pack

Every other recipe in `examples/` drives a monochrome TUI, so the corpus cannot
distinguish a renderer that reproduces colour from one that throws it away.
This pack exists to make that difference visible: the fixture emits 16-colour,
256-colour and 24-bit truecolour cells, the full set of SGR text attributes,
box drawing, wide CJK characters and an animated progress bar.

```bash
uv run termproof run examples/colorstress --video
```

Since 0.3.0 `final.svg` and the `attributed_rsvg` video are drawn in colour.
`termproof/attributed.py` keeps a per-cell grid — foreground and background,
bold, italic, underline, strikethrough, reverse, double width — and `screen_svg`
emits one `<text>` per cell, so the screenshot looks like what the operator saw.

Two attributes this fixture emits do *not* come through, both by known
limitation rather than oversight: the per-step screenshots under `steps/` are
still rendered from plain text, and dim (SGR 2) is dropped on the cast-replay
path because pyte has no field for it. Both are pinned by tests and described in
[docs/evidence-quality.md](../../docs/evidence-quality.md).

The fixture's job did not end there; it changed. It is now the regression
surface that keeps colour working. A recorded run lives at
[`examples/artifacts/colour-stress/`](../artifacts/colour-stress/) and is
replayed by `CorpusByteIdentityTest`: `final.svg` is pinned byte for byte, and a
second assertion fails if this entry ever renders monochrome. Every other recipe
in the corpus drives a monochrome TUI, so without this one a renderer that
discarded every attribute would still pass the whole suite.

## Before and after

Both files are the same recorded session — `examples/artifacts/colour-stress/session.cast`
— replayed through the two renderers:

| | File | Distinct fill colours |
| --- | --- | --- |
| 0.2.x, one `<text>` per line | [`before-monochrome.svg`](before-monochrome.svg) | 1 |
| 0.3.0, one `<text>` per cell | [`../artifacts/colour-stress/final.svg`](../artifacts/colour-stress/final.svg) | 400 |

`before-monochrome.svg` is kept only as that comparison. It is not part of the
corpus and no test renders it; regenerating it means replaying the same cast
through the 0.2.x `screen.render_svg`.

Do not simplify this pack to a plain TUI. See
[docs/evidence-quality.md](../../docs/evidence-quality.md).
