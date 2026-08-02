# TUI Verification - FAIL

- Recipe: `fail-step-timeout`
- Renderer: `default`
- Priority: `P2`
- Execution: `scripted`
- Score: `1.00`
- Exit code: `0`
- Duration: `0.00s`

## Artifacts

- cast: `session.cast`
- screenshot: `final.svg`
- screen_text: `final.txt`
- exit_code_file: `session.exitcode`
- step_screenshots: `steps`

## Assertions

- PASS `banner` - contains 'TermProof'
- PASS `exit_code` - expected 0, got 0

## Steps

- FAIL `wait never` - timed out waiting for 'NEVER-PRESENT-12345'
