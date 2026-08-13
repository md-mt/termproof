# TUI Verification - PASS

- Recipe: `pi-version`
- Renderer: `default`
- Priority: `P0`
- Execution: `scripted`
- Score: `1.00`
- Exit code: `0`
- Duration: `0.78s`

## Artifacts

- cast: `examples/artifacts/pi-version/session.cast`
- screenshot: `examples/artifacts/pi-version/final.svg`
- screen_text: `examples/artifacts/pi-version/final.txt`
- exit_code_file: `examples/artifacts/pi-version/session.exitcode`
- step_screenshots: `examples/artifacts/pi-version/steps`
- video: `examples/artifacts/pi-version/session.mp4`

## Assertions

- PASS `sandbox failure is absent` - sandbox failure is absent
- PASS `sandbox launcher error is absent` - sandbox launcher error is absent
- PASS `exit_code` - expected 0, got 0

## Steps

- PASS `1:wait_for_text` - found '.'
