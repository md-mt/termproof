# Bubble Tea Integration Guide

Bubble Tea apps are straightforward to verify when the command starts in a
known model state and accepts normal keyboard input.

## Recipe Setup

Run either a built binary or `go run`:

```json
{
  "recipe_version": 1,
  "name": "bubbletea-smoke",
  "command": {
    "argv": ["go", "run", "./cmd/my-tui"],
    "env": {"TERM": "xterm-256color"},
    "pty": true
  },
  "cols": 100,
  "rows": 30,
  "steps": [
    {"action": "wait_for_text", "text": "Tasks", "timeout_seconds": 10},
    {"action": "press", "key": "down"},
    {"action": "press", "key": "enter"},
    {"action": "wait_for_text", "text": "Task details", "timeout_seconds": 5}
  ],
  "assertions": [
    {"type": "screen_contains", "value": "Task details"},
    {"type": "exit_code", "value": 0}
  ]
}
```

For faster CI, build the binary first and point `command.argv` at the compiled
artifact.

## Common Patterns

- Seed the Bubble Tea model with fixture data instead of live services.
- Prefer text that users actually see: titles, selected rows, prompts, and
  status messages.
- Use `wait_for_regex` for dynamic counters or generated identifiers.
- Keep terminal dimensions fixed so viewport and list rendering stay stable.

## CI Configuration

```yaml
jobs:
  termproof:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-go@v5
        with:
          go-version: stable
      - run: go build -o ./bin/my-tui ./cmd/my-tui
      - uses: astral-sh/setup-uv@v5
      - run: uvx --from git+https://github.com/md-mt/termproof.git termproof run .termproof/recipes/bubbletea --out .termproof/runs
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: termproof-bubbletea-evidence
          path: .termproof/runs
```

## Example Repo

```text
my-bubbletea-app/
  cmd/my-tui/main.go
  internal/tui/
  .termproof/recipes/bubbletea/smoke.recipe.json
```

Use [`examples/generic`](../../examples/generic) as the recipe-pack reference
until the first-party Bubble Tea example repo is published.
