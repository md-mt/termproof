# TUI Verification - 3/3 Passed

## Build Provenance

- Mode: `installed`
- Command: `examples/bin/pi-clean --help`
- Binary: `examples/bin/pi-clean`
- Version: `0.80.6`
- Git commit: `78b09b5d6a192654f17505db9fdb864aedf8ab0c`
- Verified: `yes`

| Recipe | Renderer | Priority | Execution | Result | Score | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| `pi-help` | `default` | `P0` | `scripted` | PASS | 1.00 | [screenshot](examples/artifacts/20260724-153636-750167-pi-help-default/final.svg) / [video](examples/artifacts/20260724-153636-750167-pi-help-default/session.mp4) / [cast](examples/artifacts/20260724-153636-750167-pi-help-default/session.cast) / [screen_text](examples/artifacts/20260724-153636-750167-pi-help-default/final.txt) / [step_screenshots](examples/artifacts/20260724-153636-750167-pi-help-default/steps) |
| `pi-list` | `default` | `P0` | `scripted` | PASS | 1.00 | [screenshot](examples/artifacts/20260724-153637-721339-pi-list-default/final.svg) / [video](examples/artifacts/20260724-153637-721339-pi-list-default/session.mp4) / [cast](examples/artifacts/20260724-153637-721339-pi-list-default/session.cast) / [screen_text](examples/artifacts/20260724-153637-721339-pi-list-default/final.txt) / [step_screenshots](examples/artifacts/20260724-153637-721339-pi-list-default/steps) |
| `pi-version` | `default` | `P0` | `scripted` | PASS | 1.00 | [screenshot](examples/artifacts/20260724-153638-478778-pi-version-default/final.svg) / [video](examples/artifacts/20260724-153638-478778-pi-version-default/session.mp4) / [cast](examples/artifacts/20260724-153638-478778-pi-version-default/session.cast) / [screen_text](examples/artifacts/20260724-153638-478778-pi-version-default/final.txt) / [step_screenshots](examples/artifacts/20260724-153638-478778-pi-version-default/steps) |

<details><summary>PASS pi-help [default]</summary>

### Assertions

- PASS `output_contains` - contains 'Usage:'
- PASS `output_contains` - contains 'Built-in Tool Names'
- PASS `sandbox failure is absent` - sandbox failure is absent
- PASS `sandbox launcher error is absent` - sandbox launcher error is absent
- PASS `exit_code` - expected 0, got 0

### Steps

- PASS `1:wait_for_text` - found 'Usage:'

</details>

<details><summary>PASS pi-list [default]</summary>

### Assertions

- PASS `output_contains` - contains 'pi list'
- PASS `output_contains` - contains 'List installed packages'
- PASS `sandbox failure is absent` - sandbox failure is absent
- PASS `sandbox launcher error is absent` - sandbox launcher error is absent
- PASS `exit_code` - expected 0, got 0

### Steps

- PASS `1:wait_for_text` - found 'Usage:'

</details>

<details><summary>PASS pi-version [default]</summary>

### Assertions

- PASS `sandbox failure is absent` - sandbox failure is absent
- PASS `sandbox launcher error is absent` - sandbox launcher error is absent
- PASS `exit_code` - expected 0, got 0

### Steps

- PASS `1:wait_for_text` - found '.'

</details>
