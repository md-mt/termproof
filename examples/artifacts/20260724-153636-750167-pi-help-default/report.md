# TUI Verification - PASS

- Recipe: `pi-help`
- Renderer: `default`
- Priority: `P0`
- Execution: `scripted`
- Score: `1.00`
- Exit code: `0`
- Duration: `0.97s`

## Artifacts

- cast: `examples/artifacts/20260724-153636-750167-pi-help-default/session.cast`
- screenshot: `examples/artifacts/20260724-153636-750167-pi-help-default/final.svg`
- screen_text: `examples/artifacts/20260724-153636-750167-pi-help-default/final.txt`
- exit_code_file: `examples/artifacts/20260724-153636-750167-pi-help-default/session.exitcode`
- step_screenshots: `examples/artifacts/20260724-153636-750167-pi-help-default/steps`
- video: `examples/artifacts/20260724-153636-750167-pi-help-default/session.mp4`

## Assertions

- PASS `output_contains` - contains 'Usage:'
- PASS `output_contains` - contains 'Built-in Tool Names'
- PASS `sandbox failure is absent` - sandbox failure is absent
- PASS `sandbox launcher error is absent` - sandbox launcher error is absent
- PASS `exit_code` - expected 0, got 0

## Steps

- PASS `1:wait_for_text` - found 'Usage:'
