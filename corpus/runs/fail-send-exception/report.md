# TUI Verification - FAIL

- Recipe: `fail-send-exception`
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

- PASS `exit_code` - expected 0, got 0

## Steps

- PASS `wait banner` - found 'TermProof Fixture App'
- PASS `let process exit` - slept
- FAIL `send after exit` - [Errno N] I/O error
