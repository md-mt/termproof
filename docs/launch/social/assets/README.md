# Social Assets

Placeholder directory for avatar/banner source guidance — do not commit binary assets in launch-kit PR to keep review diffs clean.

## Avatar Guidance

- Source: run `uv run termproof run examples/generic --video` and use `final.svg` from the output directory, or use a shield-check icon
- Colors: badge green #0a7a2e bg + white `>_ ✓` glyph
- Sizes: 400x400 PNG for X/Twitter, 512x512 for Mastodon/Bluesky
- Generation: convert `final.svg` to PNG via `rsvg-convert` (librsvg2-bin) or Inkscape:
  ```bash
  # From a termproof run output:
  rsvg-convert -w 400 -h 400 .termproof/runs/<id>/final.svg -o avatar-400.png
  rsvg-convert -w 512 -h 512 .termproof/runs/<id>/final.svg -o avatar-512.png
  # Or with Inkscape:
  inkscape --export-type=png --export-width=400 .termproof/runs/<id>/final.svg -o avatar-400.png
  ```
  Crop to square if the SVG is not already square (`mogrify -gravity center -extent 400x400 avatar-400.png` with ImageMagick).

## Banner Guidance

- Layout: 3-panel collage — recipe JSON left, final.svg center, session.mp4 thumbnail right + text "Recipe → PTY → Cast → Evidence"
- Size: 1500x500 (X banner), 1200x630 (OG image)
- Font: prefer system monospace for recipe snippet

Human gate t_550ba351 creates finalized PNGs after avatar approval and uploads to hosting (or commits to `docs/launch/social/assets/` in follow-up PR).

This file prevents git from ignoring empty `assets/` directory.
