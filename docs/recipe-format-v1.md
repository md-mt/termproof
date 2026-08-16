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

Recipes that verify JSON-producing CLIs can use the built-in `json_schema` assertion. Set `schema` to either an inline JSON Schema object or a recipe-relative schema file path.

## Asserting on an intermediate screen

`screen_contains` reads the last screen of the run. To assert on a state the
target passes through and then leaves, name the step whose screen to read:

```json
{
  "steps": [
    { "name": "open the palette", "action": "wait_for_text", "text": "Command palette" },
    { "name": "dismiss", "action": "press", "key": "escape" }
  ],
  "assertions": [
    { "type": "step_screen_contains", "step": "open the palette", "value": "Command palette" },
    { "type": "screen_not_contains", "value": "Command palette" }
  ]
}
```

`step` matches the step's `name`. A step without one is named `"<index>:<action>"`,
so naming the steps you assert on is worth doing.

Recipes are not required to give their steps distinct names, and `step` reads the
screen of the **first** step whose name matches. Two steps sharing a name is
therefore a silently confusing assertion rather than an error — keep the name of
any step you assert on unique within the recipe.

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
