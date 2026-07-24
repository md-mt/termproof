# TUI Verification - PASS

- Recipe: `pi-help`
- Renderer: `default`
- Priority: `P0`
- Execution: `scripted`
- Score: `1.00`
- Exit code: `71`
- Duration: `2.50s`

## Artifacts

- cast: `examples/artifacts/20260724-152417-148189-pi-help-default/session.cast`
- screenshot: `examples/artifacts/20260724-152417-148189-pi-help-default/final.svg`
- screen_text: `examples/artifacts/20260724-152417-148189-pi-help-default/final.txt`
- exit_code_file: `examples/artifacts/20260724-152417-148189-pi-help-default/session.exitcode`
- step_screenshots: `examples/artifacts/20260724-152417-148189-pi-help-default/steps`
- video: `examples/artifacts/20260724-152417-148189-pi-help-default/session.mp4`

## Assertions

- PASS `output_contains` - contains 'Pi at Meta'
- PASS `output_contains` - contains 'Meta Launcher Options'
- PASS `output_contains` - contains '--doctor'

## Steps

- PASS `1:wait_for_text` - found 'Meta Launcher Options'
