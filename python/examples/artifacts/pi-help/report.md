# TUI Verification - PASS

- Recipe: `pi-help`
- Renderer: `default`
- Priority: `P0`
- Execution: `scripted`
- Score: `1.00`
- Exit code: `0`
- Duration: `0.97s`

## Artifacts

- cast: `examples/artifacts/pi-help/session.cast`
- screenshot: `examples/artifacts/pi-help/final.svg`
- screen_text: `examples/artifacts/pi-help/final.txt`
- exit_code_file: `examples/artifacts/pi-help/session.exitcode`
- step_screenshots: `examples/artifacts/pi-help/steps`
- video: `examples/artifacts/pi-help/session.mp4`

## Assertions

- PASS `output_contains` - contains 'Usage:'
- PASS `output_contains` - contains 'Built-in Tool Names'
- PASS `sandbox failure is absent` - sandbox failure is absent
- PASS `sandbox launcher error is absent` - sandbox launcher error is absent
- PASS `exit_code` - expected 0, got 0

## Steps

- PASS `1:wait_for_text` - found 'Usage:'
