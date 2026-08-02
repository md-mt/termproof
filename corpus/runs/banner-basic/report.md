# TUI Verification - PASS

- Recipe: `banner-basic`
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

- PASS `output has fixture title` - contains 'TermProof Fixture App'
- PASS `screen has menu` - contains 'menu:'
- PASS `exit_code` - expected 0, got 0

## Steps

- PASS `wait for banner title` - found 'TermProof Fixture App'
- PASS `wait for ready status` - found 'status: ready'
