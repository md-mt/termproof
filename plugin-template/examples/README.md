# termproof-my-plugin examples

Recipe that exercises the plugin if configured:

```yaml
steps:
  wait_for_regex: termproof_my_plugin.steps:WaitForRegex
assertions:
  screen_count: termproof_my_plugin.assertions:ScreenCount
```

Run with custom config:

```bash
termproof run examples/demo.recipe.json --config .termproof/config.yaml
```
