# TUI Verification - PASS

- Recipe: `multi-turn-conversation`
- Renderer: `default`
- Priority: `P1`
- Execution: `scripted`
- Score: `1.00`
- Exit code: `0`
- Duration: `17.25s`

## Artifacts

- cast: `examples/artifacts/20260724-171258-638194-multi-turn-conversation-default/session.cast`
- screenshot: `examples/artifacts/20260724-171258-638194-multi-turn-conversation-default/final.svg`
- screen_text: `examples/artifacts/20260724-171258-638194-multi-turn-conversation-default/final.txt`
- exit_code_file: `examples/artifacts/20260724-171258-638194-multi-turn-conversation-default/session.exitcode`
- step_screenshots: `examples/artifacts/20260724-171258-638194-multi-turn-conversation-default/steps`
- video: `examples/artifacts/20260724-171258-638194-multi-turn-conversation-default/session.mp4`

## Assertions

- PASS `output_contains` - contains 'Repository inspection complete.'
- PASS `output_contains` - contains 'Rendering MP4 with agg plus ffmpeg.'
- PASS `output_contains` - contains 'Multi-turn verification passed.'
- PASS `output_contains` - contains 'SESSION COMPLETE'
- PASS `exit_code` - expected 0, got 0

## Steps

- PASS `wait for prompt` - found 'you>'
- PASS `inspect repository` - sent line
- PASS `wait for inspection` - found 'Repository inspection complete.'
- PASS `pause after inspection` - slept
- PASS `run pipeline` - sent line
- PASS `wait for pipeline` - found 'Pipeline completed.'
- PASS `pause after render` - slept
- PASS `summarize evidence` - sent line
- PASS `wait for summary` - found 'Multi-turn verification passed.'
- PASS `pause before exit` - slept
- PASS `close session` - sent line
- PASS `wait for completion` - found 'SESSION COMPLETE'
