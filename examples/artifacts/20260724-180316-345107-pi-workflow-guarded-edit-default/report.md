# TUI Verification - PASS

- Recipe: `pi-workflow-guarded-edit`
- Renderer: `default`
- Priority: `P1`
- Execution: `scripted`
- Score: `1.00`
- Exit code: `0`
- Duration: `7.38s`

## Artifacts

- cast: `examples/artifacts/20260724-180316-345107-pi-workflow-guarded-edit-default/session.cast`
- screenshot: `examples/artifacts/20260724-180316-345107-pi-workflow-guarded-edit-default/final.svg`
- screen_text: `examples/artifacts/20260724-180316-345107-pi-workflow-guarded-edit-default/final.txt`
- exit_code_file: `examples/artifacts/20260724-180316-345107-pi-workflow-guarded-edit-default/session.exitcode`
- step_screenshots: `examples/artifacts/20260724-180316-345107-pi-workflow-guarded-edit-default/steps`
- video: `examples/artifacts/20260724-180316-345107-pi-workflow-guarded-edit-default/session.mp4`

## Assertions

- PASS `output_contains` - contains 'tool allowlist: read,bash,edit,write'
- PASS `output_contains` - contains 'patch applied'
- PASS `output_contains` - contains '12 tests passed'
- PASS `output_contains` - contains 'diff reviewed'
- PASS `output_contains` - contains 'GUARDED EDIT COMPLETE'
- PASS `exit_code` - expected 0, got 0

## Steps

- PASS `wait for prompt` - found 'pi>'
- PASS `propose change` - sent line
- PASS `wait for plan` - found 'GUARDED EDIT PLAN READY'
- PASS `apply patch` - sent line
- PASS `wait for patch` - found 'GUARDED PATCH APPLIED'
- PASS `validate tests` - sent line
- PASS `wait for validation` - found 'GUARDED VALIDATION COMPLETE'
- PASS `summarize diff` - sent line
- PASS `wait for summary` - found 'GUARDED EDIT COMPLETE'
- PASS `close session` - sent line
- PASS `wait for close` - found 'WORKFLOW SESSION COMPLETE'
