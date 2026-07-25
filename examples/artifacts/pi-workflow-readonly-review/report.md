# TUI Verification - PASS

- Recipe: `pi-workflow-readonly-review`
- Renderer: `default`
- Priority: `P1`
- Execution: `scripted`
- Score: `1.00`
- Exit code: `0`
- Duration: `7.78s`

## Artifacts

- cast: `examples/artifacts/pi-workflow-readonly-review/session.cast`
- screenshot: `examples/artifacts/pi-workflow-readonly-review/final.svg`
- screen_text: `examples/artifacts/pi-workflow-readonly-review/final.txt`
- exit_code_file: `examples/artifacts/pi-workflow-readonly-review/session.exitcode`
- step_screenshots: `examples/artifacts/pi-workflow-readonly-review/steps`
- video: `examples/artifacts/pi-workflow-readonly-review/session.mp4`

## Assertions

- PASS `output_contains` - contains '--tools read,grep,find,ls'
- PASS `output_contains` - contains 'no write/edit tools were enabled'
- PASS `output_contains` - contains 'READONLY REVIEW COMPLETE'
- PASS `output_contains` - contains 'WORKFLOW SESSION COMPLETE'
- PASS `exit_code` - expected 0, got 0

## Steps

- PASS `wait for prompt` - found 'pi>'
- PASS `scope repository` - sent line
- PASS `wait for scope` - found 'READONLY SCOPE READY'
- PASS `inspect files` - sent line
- PASS `wait for inspection` - found 'READONLY INSPECTION COMPLETE'
- PASS `run validation` - sent line
- PASS `wait for validation` - found 'READONLY VALIDATION COMPLETE'
- PASS `report findings` - sent line
- PASS `wait for review` - found 'READONLY REVIEW COMPLETE'
- PASS `close session` - sent line
- PASS `wait for close` - found 'WORKFLOW SESSION COMPLETE'
