# API Reference

TermProof stabilizes the recipe format and plugin protocols as public integration surfaces.

## Recipe Format

- `recipe_version: 1` marks the stable JSON recipe format.
- `command.argv` launches the target process.
- `steps` drive terminal input and waits.
- `assertions` evaluate output, screen text, exit code, files, or JSON Schema.
- `renderers` fan one recipe out across multiple frontend implementations.

See `docs/recipe-format-v1.md` and `docs/recipe-schema-v1.json` in the repository for the complete schema and migration policy. The schema the installed package validates against is `termproof/_resources/recipe-schema-v1.json`, inside the package; the `docs/` file is a byte-identical copy of it, kept so the published path it has always been at does not move.

## Plugin Protocols

Stable protocols cover:

- `StepAction`
- `AssertionType`
- `StepAwareAssertionType`
- `ExecutionMode`
- `Reporter`
- `ScreenRenderer`
- `VideoBackend`
- `AgentRunner`
- `SessionBackend`
- `ArtifactPublisher`

See `docs/plugin-protocols.md` for signatures and compatibility policy.
