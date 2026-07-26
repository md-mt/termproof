# Social Assets

Placeholder directory for avatar/banner source guidance — do not commit binary assets in launch-kit PR to keep review diffs clean.

## Avatar Guidance

- Source: `examples/generic/generic_tui.py` final state or shield-check icon
- Colors: badge green #0a7a2e bg + white `>_ ✓` glyph (from `docs/verified-badge.md`)
- Sizes: 400x400 PNG for X/Twitter, 512x512 for Mastodon/Bluesky
- Generation: export `examples/artifacts/generic-tui-workflow/final.svg` → PNG via `agg` + `ffmpeg` or Cairo, crop to square

## Banner Guidance

- Layout: 3-panel collage — recipe JSON left, final.svg center, session.mp4 thumbnail right + text "Recipe → PTY → Cast → Evidence"
- Size: 1500x500 (X banner), 1200x630 (OG image)
- Font: prefer system monospace for recipe snippet

Human gate t_550ba351 creates finalized PNGs after avatar approval and uploads to hosting (or commits to `docs/launch/social/assets/` in follow-up PR).

This file prevents git from ignoring empty `assets/` directory.
