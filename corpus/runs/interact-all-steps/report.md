# TUI Verification - PASS

- Recipe: `interact-all-steps`
- Renderer: `default`
- Priority: `P0`
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

- PASS `interaction output present` - contains 'STATUS: ok'
- PASS `help text on screen` - contains 'HELP: available'
- PASS `clean exit` - expected 0, got 0
- PASS `exit_code` - expected 0, got 0

## Steps

- PASS `wait for version banner` - found 'version: 1.2.3'
- PASS `wait for idle prompt` - stable for 0.3s
- PASS `type status without newline` - sent text
- PASS `press enter to submit` - pressed enter
- PASS `wait for status result` - found 'STATUS: ok'
- PASS `capture status via regex` - matched 'STATUS: (?P<state>\\w+)' -> state='ok'; groups=('ok',) (full: 'STATUS: ok')
- PASS `send help line` - sent line
- PASS `wait for help result` - found 'HELP: available'
- PASS `brief sleep` - slept
- PASS `quit cleanly` - sent line
- PASS `wait for bye` - found 'bye'
