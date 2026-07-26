# termproof-my-plugin examples

Recipe that exercises the custom ``wait_for_regex`` step and ``screen_count``
assertion with a PTY-backed command.

## Config

Add to your project's ``.termproof/config.yaml``:

```yaml
steps:
  wait_for_regex: termproof_my_plugin.steps:WaitForRegex
assertions:
  screen_count: termproof_my_plugin.assertions:ScreenCount
reporters:
  json_summary: termproof_my_plugin.reporters:JsonSummaryReporter
```

## Run

From the plugin-template directory (with ``PYTHONPATH=src``):

```bash
termproof run examples/demo.recipe.json \
  --config examples/.termproof/config.yaml \
  --reporter json_summary
```

Expected: the recipe waits for ``Dashboard N/M`` via custom step, then asserts
zero ``TODO`` matches on the final screen via custom assertion. The JSON
reporter produces a machine-readable summary.
