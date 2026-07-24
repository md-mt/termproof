# TUI Verification - FAIL

- Recipe: `pi-codex-operator`
- Renderer: `default`
- Priority: `P1`
- Execution: `agent-driven`
- Score: `0.00`
- Exit code: `1`
- Duration: `0.71s`

## Artifacts

- cast: `examples/artifacts/20260724-153619-129937-pi-codex-operator-default/session.cast`
- screenshot: `examples/artifacts/20260724-153619-129937-pi-codex-operator-default/final.svg`
- screen_text: `examples/artifacts/20260724-153619-129937-pi-codex-operator-default/final.txt`
- exit_code_file: `examples/artifacts/20260724-153619-129937-pi-codex-operator-default/session.exitcode`
- step_screenshots: `examples/artifacts/20260724-153619-129937-pi-codex-operator-default/steps`
- agent_prompt: `examples/artifacts/20260724-153619-129937-pi-codex-operator-default/agent_prompt.md`
- agent_transcript: `examples/artifacts/20260724-153619-129937-pi-codex-operator-default/agent_transcript.md`
- agent_outcome: `examples/artifacts/20260724-153619-129937-pi-codex-operator-default/agent_outcome.json`
- video: `examples/artifacts/20260724-153619-129937-pi-codex-operator-default/session.mp4`

## Assertions

- FAIL `Pi help renders` - agent did not report pass
- FAIL `sandbox failure is absent` - agent did not report pass
- FAIL `terminal evidence is recorded` - agent did not report pass

## Steps

- FAIL `codex-operator` - operator exit code 1
