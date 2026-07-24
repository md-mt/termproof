# TUI Verification - 0/1 Passed

## Build Provenance

- Mode: `installed`
- Command: `pi --help`
- Binary: `/usr/local/bin/pi`
- Version: `Pi at Meta (https://www.npmjs.com/package/@earendil-works/pi-coding-agent) / Using AI Gateway (Anthropic upstream) / sandbox-exec: sandbox_apply: Operation not permitted`
- Git commit: `731f9898d933e8210877c90687a6d8dabda42ff6`
- Verified: `yes`

| Recipe | Renderer | Priority | Execution | Result | Score | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| `pi-codex-operator` | `default` | `P1` | `agent-driven` | FAIL | 0.00 | [screenshot](examples/artifacts/20260724-152350-148325-pi-codex-operator-default/final.svg) / [video](examples/artifacts/20260724-152350-148325-pi-codex-operator-default/session.mp4) / [cast](examples/artifacts/20260724-152350-148325-pi-codex-operator-default/session.cast) / [screen_text](examples/artifacts/20260724-152350-148325-pi-codex-operator-default/final.txt) / [step_screenshots](examples/artifacts/20260724-152350-148325-pi-codex-operator-default/steps) |

<details><summary>FAIL pi-codex-operator [default]</summary>

### Assertions

- FAIL `Pi launcher banner renders` - agent did not report pass
- FAIL `Meta launcher help options render` - agent did not report pass
- FAIL `terminal evidence is recorded` - agent did not report pass

### Steps

- FAIL `codex-operator` - operator exit code 71

</details>
