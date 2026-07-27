# Textual Integration Guide

Textual apps work best with TermProof when the recipe drives a deterministic
screen: seed data, fixed terminal dimensions, and a command that exits cleanly
after the verified flow.

## Recipe Setup

Use the same command you use locally, usually a module or app entry point:

```json
{
  "recipe_version": 1,
  "name": "textual-smoke",
  "command": {
    "argv": ["python", "-m", "my_app"],
    "env": {"TERM": "xterm-256color"},
    "pty": true
  },
  "cols": 100,
  "rows": 30,
  "steps": [
    {"action": "wait_for_text", "text": "Dashboard", "timeout_seconds": 5},
    {"action": "press", "key": "tab"},
    {"action": "send_line", "text": "alice"},
    {"action": "wait_for_text", "text": "Results for alice", "timeout_seconds": 5}
  ],
  "assertions": [
    {"type": "screen_contains", "value": "Results for alice"},
    {"type": "output_not_contains", "value": "Traceback"}
  ]
}
```

Prefer a test fixture mode in the app that disables network calls, clocks, and
random data.

## Common Patterns

- Wait for visible widget labels or stable screen text, not internal Textual
  object names.
- Use `press` for navigation keys and `send_text` or `send_line` for form input.
- Assert both final screen state and absence of Python tracebacks.
- Use `--screen-renderer png` when visual-diff workflows need raster artifacts.

## CI Configuration

```yaml
jobs:
  termproof:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync
      - run: uv run termproof run .termproof/recipes/textual --out .termproof/runs
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: termproof-textual-evidence
          path: .termproof/runs
```

## Example Repo

Until first-party framework repos are split out, use this layout:

```text
my-textual-app/
  pyproject.toml
  src/my_app/__main__.py
  .termproof/recipes/textual/smoke.recipe.json
```

The portable reference pack is [`examples/generic`](../../examples/generic).
