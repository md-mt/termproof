# TUI Verification - PASS

- Recipe: `pi-workflow-session-resume-export`
- Renderer: `default`
- Priority: `P1`
- Execution: `scripted`
- Score: `1.00`
- Exit code: `0`
- Duration: `5.74s`

## Artifacts

- cast: `examples/artifacts/pi-workflow-session-resume-export/session.cast`
- screenshot: `examples/artifacts/pi-workflow-session-resume-export/final.svg`
- screen_text: `examples/artifacts/pi-workflow-session-resume-export/final.txt`
- exit_code_file: `examples/artifacts/pi-workflow-session-resume-export/session.exitcode`
- step_screenshots: `examples/artifacts/pi-workflow-session-resume-export/steps`
- video: `examples/artifacts/pi-workflow-session-resume-export/session.mp4`

## Assertions

- PASS `output_contains` - contains '--name "Verifier workflow audit"'
- PASS `output_contains` - contains '--continue'
- PASS `output_contains` - contains '--session workflow-001'
- PASS `output_contains` - contains '--fork workflow-001'
- PASS `output_contains` - contains '--export session.jsonl output.html'
- PASS `output_contains` - contains 'SESSION RESUME EXPORT COMPLETE'
- PASS `exit_code` - expected 0, got 0

## Steps

- PASS `wait for prompt` - found 'pi>'
- PASS `start session` - sent line
- PASS `wait for start` - found 'SESSION STARTED'
- PASS `continue session` - sent line
- PASS `wait for resume` - found 'SESSION RESUMED'
- PASS `fork export` - sent line
- PASS `wait for export` - found 'SESSION RESUME EXPORT COMPLETE'
- PASS `close session` - sent line
- PASS `wait for close` - found 'WORKFLOW SESSION COMPLETE'
