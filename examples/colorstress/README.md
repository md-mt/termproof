# Colour Stress Recipe Pack

Every other recipe in `examples/` drives a monochrome TUI, so the corpus cannot
distinguish a renderer that reproduces colour from one that throws it away.
This pack exists to make that difference visible: the fixture emits 16-colour,
256-colour and 24-bit truecolour cells, the full set of SGR text attributes,
box drawing, wide CJK characters and an animated progress bar.

```bash
uv run termproof run examples/colorstress --video
```

Since 0.3.0 the renderers draw it in colour. `termproof/attributed.py` keeps a
per-cell grid — foreground and background, bold, dim, italic, underline,
strikethrough, reverse, double width — and `screen_svg` emits one `<text>` per
cell, so the screenshot looks like what the operator saw.

The fixture's job did not end there; it changed. It is now the regression
surface that keeps colour working. A recorded run lives at
[`examples/artifacts/colour-stress/`](../artifacts/colour-stress/) and is
replayed by `CorpusByteIdentityTest`: `final.svg` is pinned byte for byte, and a
second assertion fails if this entry ever renders monochrome. Every other recipe
in the corpus drives a monochrome TUI, so without this one a renderer that
discarded every attribute would still pass the whole suite.

Do not simplify this pack to a plain TUI. See
[docs/evidence-quality.md](../../docs/evidence-quality.md).
