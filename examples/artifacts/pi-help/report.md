# TUI Verification - PASS

- Recipe: `pi-help`
- Renderer: `default`
- Priority: `P0`
- Execution: `scripted`
- Score: `1.00`
- Exit code: `71`
- Duration: `2.50s`

## Artifacts

- cast: `examples/artifacts/pi-help/session.cast`
- screenshot: `examples/artifacts/pi-help/final.svg`
- screen_text: `examples/artifacts/pi-help/final.txt`
- exit_code_file: `examples/artifacts/pi-help/session.exitcode`
- step_screenshots: `examples/artifacts/pi-help/steps`
- video: `examples/artifacts/pi-help/session.mp4`

## Assertions

- PASS `output_contains` - contains 'Pi at Meta'
- PASS `output_contains` - contains 'Meta Launcher Options'
- PASS `output_contains` - contains '--doctor'

## Steps

- PASS `1:wait_for_text` - found 'Meta Launcher Options'
