# TUI Verification - 0/1 Passed

## Build Provenance

- Mode: `installed`
- Command: `examples/bin/pi-clean --help`
- Binary: `examples/bin/pi-clean`
- Version: `0.80.6`
- Git commit: `78b09b5d6a192654f17505db9fdb864aedf8ab0c`
- Verified: `yes`

| Recipe | Renderer | Priority | Execution | Result | Score | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| `pi-codex-operator` | `default` | `P1` | `agent-driven` | FAIL | 0.00 | [screenshot](examples/artifacts/20260724-153619-129937-pi-codex-operator-default/final.svg) / [video](examples/artifacts/20260724-153619-129937-pi-codex-operator-default/session.mp4) / [cast](examples/artifacts/20260724-153619-129937-pi-codex-operator-default/session.cast) / [screen_text](examples/artifacts/20260724-153619-129937-pi-codex-operator-default/final.txt) / [step_screenshots](examples/artifacts/20260724-153619-129937-pi-codex-operator-default/steps) |

<details><summary>FAIL pi-codex-operator [default]</summary>

### Assertions

- FAIL `Pi help renders` - agent did not report pass
- FAIL `sandbox failure is absent` - agent did not report pass
- FAIL `terminal evidence is recorded` - agent did not report pass

### Steps

- FAIL `codex-operator` - operator exit code 1

</details>
