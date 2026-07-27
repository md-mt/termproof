# FAQ

## Is TermProof a browser testing tool?

No. TermProof drives a real terminal session and records terminal-native evidence.

## Do I need video evidence?

No. Casts, final screenshots, text snapshots, JSON results, and Markdown reports are available without video. MP4 output is useful for review workflows where motion matters.

## How do visual baselines work?

Use `termproof run --diff` to compare final screenshots against `.termproof/baselines/<recipe>/<renderer>/final.svg` or `.png`. Use `--update-baselines` to refresh them.

## How do large suites stay fast?

Use `--parallel N` to run independent recipes concurrently and `--skip-unchanged` to reuse the last passing result for unchanged recipe inputs.
