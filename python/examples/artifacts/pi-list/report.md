# TUI Verification - PASS

- Recipe: `pi-list`
- Renderer: `default`
- Priority: `P0`
- Execution: `scripted`
- Score: `1.00`
- Exit code: `0`
- Duration: `0.76s`

## Artifacts

- cast: `examples/artifacts/pi-list/session.cast`
- screenshot: `examples/artifacts/pi-list/final.svg`
- screen_text: `examples/artifacts/pi-list/final.txt`
- exit_code_file: `examples/artifacts/pi-list/session.exitcode`
- step_screenshots: `examples/artifacts/pi-list/steps`
- video: `examples/artifacts/pi-list/session.mp4`

## Assertions

- PASS `output_contains` - contains 'pi list'
- PASS `output_contains` - contains 'List installed packages'
- PASS `sandbox failure is absent` - sandbox failure is absent
- PASS `sandbox launcher error is absent` - sandbox launcher error is absent
- PASS `exit_code` - expected 0, got 0

## Steps

- PASS `1:wait_for_text` - found 'Usage:'
