# Plugin Protocol v1 (RUST-024)

Plugins use a versioned, newline-delimited JSON process protocol over stdin/stdout (spec section 4.5).

## Roles

- `StepAction`, `AssertionType`, `ExecutionMode`, `Reporter`, `ScreenRenderer`, `VideoBackend`, `AgentRunner`, `SessionBackend`

## Handshake

```json
{"protocol": "termproof/plugin-v1", "capabilities": ["step", "assertion"], "version": "1.0"}
```

## Messages

Requests carry typed context and bounded extension data; responses contain typed results and diagnostics. `stderr` is diagnostic output. Timeouts, cancellation, maximum message size, and lifecycle are specified and tested.

## Python bridge

During migration a small Python host loads existing entry points and legacy import references, then bridges them to the process protocol. See `rust/crates/termproof-plugin-protocol`.
