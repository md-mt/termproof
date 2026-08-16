# TUI Verification - PASS

- Recipe: `pi-workflow-cli-capability-map`
- Renderer: `default`
- Priority: `P0`
- Execution: `scripted`
- Score: `1.00`
- Exit code: `0`
- Duration: `2.66s`

## Artifacts

- cast: `examples/artifacts/20260724-180304-090130-pi-workflow-cli-capability-map-default/session.cast`
- screenshot: `examples/artifacts/20260724-180304-090130-pi-workflow-cli-capability-map-default/final.svg`
- screen_text: `examples/artifacts/20260724-180304-090130-pi-workflow-cli-capability-map-default/final.txt`
- exit_code_file: `examples/artifacts/20260724-180304-090130-pi-workflow-cli-capability-map-default/session.exitcode`
- step_screenshots: `examples/artifacts/20260724-180304-090130-pi-workflow-cli-capability-map-default/steps`
- video: `examples/artifacts/20260724-180304-090130-pi-workflow-cli-capability-map-default/session.mp4`

## Assertions

- PASS `output_contains` - contains 'Interactive mode'
- PASS `output_contains` - contains '--print, -p'
- PASS `output_contains` - contains '--continue, -c'
- PASS `output_contains` - contains '--session-dir <dir>'
- PASS `output_contains` - contains '--tools, -t <tools>'
- PASS `output_contains` - contains '--append-system-prompt <text>'
- PASS `output_contains` - contains '--export <file>'
- PASS `output_contains` - contains 'Built-in Tool Names'
- PASS `sandbox failure is absent` - sandbox failure is absent
- PASS `sandbox launcher error is absent` - sandbox launcher error is absent
- PASS `exit_code` - expected 0, got 0

## Steps

- PASS `wait for usage` - found 'Usage:'
