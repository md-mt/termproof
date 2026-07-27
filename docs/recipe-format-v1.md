# Recipe format v1

TermProof recipe files are JSON files ending in `.recipe.json`.

## Versioning

New recipes should set:

```json
{
  "recipe_version": 1
}
```

Recipes without `recipe_version` are treated as legacy v0.x recipes and remain loadable. `termproof validate` reports that as a warning so maintainers can migrate incrementally.

Breaking recipe format changes require a future major `recipe_version`.

## Required fields

| Field | Type | Notes |
| --- | --- | --- |
| `recipe_version` | integer | Stable value is `1`; omitted legacy recipes still run. |
| `name` | string | Human-readable recipe identifier. |
| `command.argv` | string array | Target command and arguments. |

## Common optional fields

| Field | Type | Default |
| --- | --- | --- |
| `description` | string | `""` |
| `intent` | string | `""` |
| `priority` | string | `"P2"` |
| `execution` | string | `"scripted"` |
| `determinism` | string | `"deterministic"` |
| `command.cwd` | string or null | `null` |
| `command.env` | object of string values | `{}` |
| `command.pty` | boolean | `true` |
| `steps` | object array | `[]` |
| `assertions` | object array | `[]` |
| `expect_exit_code` | integer or null | `0` |
| `timeout_seconds` | positive number | `30` |
| `cols` | positive integer | `100` |
| `rows` | positive integer | `30` |
| `renderers` | object of string arrays | `{ "default": [] }` |

## Validation

Run:

```bash
termproof validate .termproof/recipes
```

The validator checks JSON shape, required fields, configured step/action names, configured assertion names, and basic timeout/dimension sanity. It accepts `--config` with the same config cascade behavior as `termproof run`.

The formal JSON Schema is published at [`recipe-schema-v1.json`](recipe-schema-v1.json).

## Migrating v0.x recipes

Existing recipes usually need only one edit:

```json
{
  "recipe_version": 1,
  "name": "existing-recipe",
  "command": {"argv": ["my-tui"]}
}
```

After adding `recipe_version`, run `termproof validate` and fix any plugin-name or type-shape errors it reports.
