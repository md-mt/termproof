# Community plugins

TermProof is extensible via a plugin registry: steps, assertions, session backends, video backends, reporters, execution modes, and agent runners. This directory lists community-provided plugins.

## What counts as a plugin?

A plugin is a Python class referenced in `.termproof/config.yaml` (or `~/.config/termproof/config.yaml`) and installed alongside `termproof`. Example layout:

```yaml
# .termproof/config.yaml
steps:
  wait_for_regex: my_org.termproof_steps:WaitForRegexStep
assertions:
  json_schema: my_org.termproof_assertions:JsonSchemaAssertion
session_backends:
  docker: my_org.termproof_session:DockerSessionBackend
reporters:
  junit_xml: my_org.termproof_reporters:JunitReporter
```

See [`docs/recipe-packs.md`](recipe-packs.md) for the contract and `termproof/config.py` for built-ins.

## Listing

| Name | Description | Install | Author |
| --- | --- | --- | --- |
| _Be the first_ | Show us your step/assertion/session/reporter | `pip install <your-package>` | you |

To list your plugin here, open a PR editing this file with:

- Name — package or plugin identifier.
- Description — one-line purpose + which registry it targets.
- Install — pip / uv instruction.
- Author — GitHub handle or organization.
- Optional: link to repository and documentation.

### Example entry

```md
| textual-snapshot | `wait_for_textual` step that waits for Textual DOM selectors | `pip install termproof-textual` | [@you](https://github.com/you) |
```

### Sought plugins

From open issues:

- **WaitForRegex** (`wait_for_regex`) — see [#14](https://github.com/md-mt/termproof/issues/14)
- **JsonSchema assertion** (`json_schema`) — see [#20](https://github.com/md-mt/termproof/issues/20)
- **JunitXml reporter** (`junit_xml`) — see [#15](https://github.com/md-mt/termproof/issues/15)
- **PNG renderer** for pixel-level screenshots — see [#19](https://github.com/md-mt/termproof/issues/19)
- **Docker session backend** — see [#18](https://github.com/md-mt/termproof/issues/18)
- **Plugins CLI** (`termproof plugins`) — see [#21](https://github.com/md-mt/termproof/issues/21)

## Publishing

If you publish a first-party example as a separate repo (per [#23](https://github.com/md-mt/termproof/issues/23)), follow:

1. Name: `termproof-<integration>` (e.g., `termproof-textual`, `termproof-bubbletea`).
2. Entry points in `pyproject.toml` or documented `module:Class` references.
3. Include a recipe pack under `examples/` or `recipes/` and a CI job that runs `termproof run` with `--video`.
4. Add the **Verified by TermProof** badge (see [`verified-badge.md`](verified-badge.md)).

## Registry roadmap

- Manual list (now, this file) → automated registry when >30 entries (see [#22](https://github.com/md-mt/termproof/issues/22)).
- Protocol stability guarantee (see [#32](https://github.com/md-mt/termproof/issues/32)) and recipe format v1.0 (see [#31](https://github.com/md-mt/termproof/issues/31)) will precede a stable external plugin API.
