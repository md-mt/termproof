# Generic TUI Recipe Pack

This pack demonstrates how to verify a terminal workflow that is not tied to
Pi or any coding-agent CLI.

```bash
uv run termproof run examples/generic --video
```

Use the same shape in downstream projects: put one or more `*.recipe.json`
files beside any helper scripts, then pass the directory to `termproof run`.
