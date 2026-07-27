# Recipe Packs

A recipe pack is a directory that contains one or more `*.recipe.json` files
plus any helper scripts needed to drive the target terminal application.

```text
.termproof/
  recipes/
    smoke.recipe.json
    regression.recipe.json
    apps/
      scripted_fixture.py
```

Run a pack with:

```bash
termproof run .termproof/recipes --video
```

Validate a pack with:

```bash
termproof validate .termproof/recipes
```

Create a starter pack with:

```bash
termproof init .termproof/recipes --name my-tui --command "my-tui"
```

## Package Contract

- Recipes are JSON and can be checked into any repository.
- New recipes should declare `recipe_version: 1`; legacy recipes without it remain loadable.
- Discovery is recursive, so larger projects can group recipes by feature.
- Helper scripts are project-owned and can launch any TUI, CLI, or test fixture.
- `command.argv` is the target process.
- `command.pty` should be `true` for interactive TUI workflows.
- `steps` drive the terminal with waits (including `wait_for_regex` with regex validation and match-group evidence), keypresses, text, lines, and sleeps.
- `assertions` evaluate raw output, final screen text, exit code, files, or JSON Schema.

JSON-producing CLIs can validate output with an inline schema:

```json
{
  "type": "json_schema",
  "schema": {
    "type": "object",
    "required": ["status"],
    "properties": {
      "status": { "const": "ok" }
    }
  }
}
```

For larger schemas, set `schema` to a recipe-relative JSON file path.
- `reporters` include `markdown` and `junit_xml` (JUnit XML consumable by Jenkins, GitLab CI, CircleCI, etc).
- `termproof demo` provides a self-contained demo TUI that exercises all step and assertion types without external dependencies.
- `renderers` let one recipe fan out across multiple frontend implementations.

See [`recipe-format-v1.md`](recipe-format-v1.md) for the stable field reference and migration policy.

## Recommended Layout

Use three layers for a real product:

```text
.termproof/
  recipes/
    p0/
      smoke.recipe.json
    p1/
      resize.recipe.json
      multi-turn.recipe.json
    fixtures/
      seed-project.sh
```

Run P0 on every pull request and broader P1/P2 suites on release candidates.
Upload `.termproof/runs` as a CI artifact so reviewers can inspect casts,
screenshots, MP4 videos, and reports.

The Pi recipes under `examples/` are one recipe pack. The portable non-Pi pack
under `examples/generic/` demonstrates the same interface for arbitrary terminal
software.
