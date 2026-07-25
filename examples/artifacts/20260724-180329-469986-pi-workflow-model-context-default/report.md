# TUI Verification - PASS

- Recipe: `pi-workflow-model-context`
- Renderer: `default`
- Priority: `P1`
- Execution: `scripted`
- Score: `1.00`
- Exit code: `0`
- Duration: `6.17s`

## Artifacts

- cast: `examples/artifacts/20260724-180329-469986-pi-workflow-model-context-default/session.cast`
- screenshot: `examples/artifacts/20260724-180329-469986-pi-workflow-model-context-default/final.svg`
- screen_text: `examples/artifacts/20260724-180329-469986-pi-workflow-model-context-default/final.txt`
- exit_code_file: `examples/artifacts/20260724-180329-469986-pi-workflow-model-context-default/session.exitcode`
- step_screenshots: `examples/artifacts/20260724-180329-469986-pi-workflow-model-context-default/steps`
- video: `examples/artifacts/20260724-180329-469986-pi-workflow-model-context-default/session.mp4`

## Assertions

- PASS `output_contains` - contains '--provider openai --model gpt-4o-mini'
- PASS `output_contains` - contains '--model sonnet:high --thinking high'
- PASS `output_contains` - contains '--append-system-prompt project-rules.md'
- PASS `output_contains` - contains '--skill ./skills/reviewer'
- PASS `output_contains` - contains '--prompt-template ./prompts/fix-bug.md'
- PASS `output_contains` - contains '--offline --no-context-files --no-extensions --no-skills'
- PASS `output_contains` - contains 'MODEL CONTEXT WORKFLOW COMPLETE'
- PASS `exit_code` - expected 0, got 0

## Steps

- PASS `wait for prompt` - found 'pi>'
- PASS `choose model` - sent line
- PASS `wait for model` - found 'MODEL ROUTING READY'
- PASS `load context` - sent line
- PASS `wait for context` - found 'CONTEXT RESOURCES LOADED'
- PASS `configure startup` - sent line
- PASS `wait for startup` - found 'MODEL CONTEXT WORKFLOW COMPLETE'
- PASS `close session` - sent line
- PASS `wait for close` - found 'WORKFLOW SESSION COMPLETE'
