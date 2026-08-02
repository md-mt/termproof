# TUI Verification - PASS

- Recipe: `stage-timing`
- Renderer: `default`
- Priority: `P3`
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

- PASS `stage output present` - contains 'stage two complete'
- PASS `exit_code` - expected 0, got 0

## Steps

- PASS `wait for stage one` - found 'stage one'
- PASS `wait for stage two` - found 'stage two complete'
- PASS `capture completion via regex` - matched 'stage (two) complete' -> groups=('two',) (full: 'stage two complete')
