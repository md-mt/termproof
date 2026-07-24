# TUI Verification - PASS

- Recipe: `pi-version`
- Renderer: `default`
- Priority: `P0`
- Execution: `scripted`
- Score: `1.00`
- Exit code: `71`
- Duration: `2.28s`

## Artifacts

- cast: `examples/artifacts/pi-version/session.cast`
- screenshot: `examples/artifacts/pi-version/final.svg`
- screen_text: `examples/artifacts/pi-version/final.txt`
- exit_code_file: `examples/artifacts/pi-version/session.exitcode`
- step_screenshots: `examples/artifacts/pi-version/steps`
- video: `examples/artifacts/pi-version/session.mp4`

## Assertions

- PASS `output_contains` - contains 'Pi at Meta'
- PASS `output_contains` - contains 'Using AI Gateway'

## Steps

- PASS `1:wait_for_text` - found 'Pi at Meta'
