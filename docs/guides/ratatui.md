# Ratatui Integration Guide

Ratatui apps should expose a deterministic fixture mode for TermProof so CI can
drive the same terminal flow on every run.

## Recipe Setup

Run with `cargo run` for early adoption or a prebuilt binary for faster CI:

```json
{
  "recipe_version": 1,
  "name": "ratatui-smoke",
  "command": {
    "argv": ["cargo", "run", "--bin", "my-tui", "--", "--fixture", "termproof"],
    "env": {"TERM": "xterm-256color", "RUST_BACKTRACE": "1"},
    "pty": true
  },
  "cols": 100,
  "rows": 30,
  "steps": [
    {"action": "wait_for_text", "text": "Overview", "timeout_seconds": 15},
    {"action": "press", "key": "tab"},
    {"action": "wait_for_text", "text": "Logs", "timeout_seconds": 5},
    {"action": "press", "key": "q"}
  ],
  "assertions": [
    {"type": "output_not_contains", "value": "panicked at"},
    {"type": "screen_contains", "value": "Logs"}
  ]
}
```

Use a fixture flag or feature gate to provide stable data and to skip external
I/O during the recipe.

## Common Patterns

- Wait on panel titles, focused tab labels, status bars, and command prompts.
- Use `press` for navigation and quit keys; avoid sleeps except for animations
  that have no stable text boundary.
- Assert `output_not_contains` for panic strings and backtraces.
- Capture PNG screenshots when future visual-diff checks need pixel artifacts.

## CI Configuration

```yaml
jobs:
  termproof:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: dtolnay/rust-toolchain@stable
      - run: cargo build --locked --bin my-tui
      - uses: astral-sh/setup-uv@v5
      - run: uvx --from git+https://github.com/md-mt/termproof.git termproof run .termproof/recipes/ratatui --out .termproof/runs --screen-renderer png
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: termproof-ratatui-evidence
          path: .termproof/runs
```

## Example Repo

```text
my-ratatui-app/
  Cargo.toml
  src/bin/my-tui.rs
  .termproof/recipes/ratatui/smoke.recipe.json
```

Use [`examples/generic`](../../examples/generic) as the recipe-pack reference
until the first-party Ratatui example repo is published.
