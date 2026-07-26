# Social Assets

Verified source and reproducible generation commands for avatar and banner assets.
Binary assets (PNG) are not committed to keep PR diffs clean; the commands below
produce them deterministically from checked-in sources.

## Avatar

- **Source:** `examples/artifacts/pi-workflow-guarded-edit/final.svg` (checked in)
- **Generation (400x400 PNG for X/Twitter):**
  ```bash
  rsvg-convert -w 400 -h 400 examples/artifacts/pi-workflow-guarded-edit/final.svg -o avatar-400.png
  ```
- **Generation (512x512 PNG for Mastodon/Bluesky):**
  ```bash
  rsvg-convert -w 512 -h 512 examples/artifacts/pi-workflow-guarded-edit/final.svg -o avatar-512.png
  ```
- **Verification:**
  ```bash
  file avatar-400.png   # expected: PNG image data, 400 x 400
  file avatar-512.png   # expected: PNG image data, 512 x 512
  du -h avatar-400.png  # should be < 500KB for platform acceptance
  ```
- **Crop to square if source SVG is not square:**
  ```bash
  convert avatar-400.png -gravity center -extent 400x400 avatar-400-squared.png
  ```
  (requires ImageMagick: `brew install imagemagick` or `apt install imagemagick`)

## Banner

- **Source:** Composite from `examples/artifacts/pi-workflow-guarded-edit/` artifacts
- **Layout:** 3-panel collage — recipe JSON left, final.svg center, session.mp4 thumbnail right
  + text "Recipe → PTY → Cast → Evidence"
- **X banner (1500x500):**
  ```bash
  # Generate using ImageMagick montage:
  convert \
    -size 500x500 -background '#0a0a0a' -fill '#0a7a2e' -gravity center \
    label:"Recipe\n→\nPTY\n→\nCast\n→\nEvidence" \
    -font Courier -pointsize 24 panel-left.png
  rsvg-convert -w 500 examples/artifacts/pi-workflow-guarded-edit/final.svg -o panel-center.png
  convert panel-left.png panel-center.png +append -resize 1500x500! banner-1500.png
  ```
- **OG image (1200x630):**
  ```bash
  convert banner-1500.png -resize 1200x630! og-image.png
  ```
- **Verification:**
  ```bash
  file banner-1500.png   # expected: PNG image data, 1500 x 500
  file og-image.png      # expected: PNG image data, 1200 x 630
  du -h banner-1500.png  # should be < 5MB
  ```

## Deliverables Checklist

Before launch, verify all assets exist and meet platform constraints:

```bash
# Avatar verification
test -f avatar-400.png && file avatar-400.png | grep -q "400 x 400"
test -f avatar-512.png && file avatar-512.png | grep -q "512 x 512"

# Banner verification
test -f banner-1500.png && file banner-1500.png | grep -q "1500 x 500"
test -f og-image.png && file og-image.png | grep -q "1200 x 630"

# File size checks (warn if too large)
echo "Avatar 400: $(du -h avatar-400.png | cut -f1)"
echo "Avatar 512: $(du -h avatar-512.png | cut -f1)"
echo "Banner 1500: $(du -h banner-1500.png | cut -f1)"
echo "OG image: $(du -h og-image.png | cut -f1)"
```

Human gate t_550ba351 approves the final PNGs and uploads to hosting (or commits to
`docs/launch/social/assets/` in follow-up PR) after avatar approval.
