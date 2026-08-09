# Colour Stress Recipe Pack

Every other recipe in `examples/` drives a monochrome TUI, so the corpus cannot
distinguish a renderer that reproduces colour from one that throws it away.
This pack exists to make that difference visible: the fixture emits 16-colour,
256-colour and 24-bit truecolour cells, the full set of SGR text attributes,
box drawing, wide CJK characters and an animated progress bar.

```bash
uv run termproof run examples/colorstress --video
```

Today's screen renderers draw it in flat monochrome. That is the defect this
fixture exists to expose, not a bug in the fixture: `termproof/screen.py`
flattens the terminal buffer to plain text, so colour and attributes are
discarded before any renderer is called. Fixing that needs an additive change
to the renderer interface and is deliberately not done here — this pack is the
regression surface that has to exist first.
