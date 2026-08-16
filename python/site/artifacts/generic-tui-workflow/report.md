# TUI Verification - PASS

- Recipe: `generic-tui-workflow`
- Renderer: `default`
- Priority: `P1`
- Execution: `scripted`
- Score: `1.00`
- Exit code: `0`
- Duration: `3.14s`

## Artifacts

- cast: `.termproof/ci/20260725-222654-423229-generic-tui-workflow-default/session.cast`
- screenshot: `.termproof/ci/20260725-222654-423229-generic-tui-workflow-default/final.svg`
- screen_text: `.termproof/ci/20260725-222654-423229-generic-tui-workflow-default/final.txt`
- exit_code_file: `.termproof/ci/20260725-222654-423229-generic-tui-workflow-default/session.exitcode`
- step_screenshots: `.termproof/ci/20260725-222654-423229-generic-tui-workflow-default/steps`

## Assertions

- PASS `output_contains` - contains 'DASHBOARD READY'
- PASS `output_contains` - contains 'FILTER READY'
- PASS `output_contains` - contains 'EXPORT READY'
- PASS `output_contains` - contains 'GENERIC TUI COMPLETE'
- PASS `exit_code` - expected 0, got 0

## Steps

- PASS `wait for prompt` - found 'demo>'
- PASS `open dashboard` - sent line
- PASS `wait for dashboard` - found 'DASHBOARD READY'
- PASS `filter errors` - sent line
- PASS `wait for filter` - found 'FILTER READY'
- PASS `export report` - sent line
- PASS `wait for export` - found 'EXPORT READY'
- PASS `close session` - sent line
- PASS `wait for close` - found 'GENERIC TUI COMPLETE'
