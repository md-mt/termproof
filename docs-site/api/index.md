# API Reference

TermProof stabilizes the recipe format and plugin protocols as public integration surfaces.

## Recipe Format

- `recipe_version: 1` marks the stable JSON recipe format.
- `command.argv` launches the target process.
- `steps` drive terminal input and waits.
- `assertions` evaluate output, screen text, exit code, files, or JSON Schema.
- `renderers` fan one recipe out across multiple frontend implementations.

See `docs/recipe-format-v1.md` and `docs/recipe-schema-v1.json` in the repository for the complete schema and migration policy.

## Plugin Protocols

Stable protocols cover:

- `StepAction`
- `AssertionType`
- `ExecutionMode`
- `Reporter`
- `ScreenRenderer`
- `VideoBackend`
- `AgentRunner`
- `SessionBackend`
- `ArtifactPublisher`

See `docs/plugin-protocols.md` for signatures and compatibility policy.
