# TUI Verification - PASS

- Recipe: `pi-list`
- Renderer: `default`
- Priority: `P0`
- Execution: `scripted`
- Score: `1.00`
- Exit code: `71`
- Duration: `2.21s`

## Artifacts

- cast: `examples/artifacts/20260724-152419-653835-pi-list-default/session.cast`
- screenshot: `examples/artifacts/20260724-152419-653835-pi-list-default/final.svg`
- screen_text: `examples/artifacts/20260724-152419-653835-pi-list-default/final.txt`
- exit_code_file: `examples/artifacts/20260724-152419-653835-pi-list-default/session.exitcode`
- step_screenshots: `examples/artifacts/20260724-152419-653835-pi-list-default/steps`
- video: `examples/artifacts/20260724-152419-653835-pi-list-default/session.mp4`

## Assertions

- PASS `output_contains` - contains 'Pi at Meta'
- PASS `output_contains` - contains 'Using AI Gateway'

## Steps

- PASS `1:wait_for_text` - found 'Pi at Meta'
