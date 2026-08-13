# TUI Verification - 1/1 Passed

## Build Provenance

- Mode: `installed`
- Command: `python3 examples/apps/multi_turn_conversation.py`
- Binary: `/Users/mengwei/termproof/.venv/bin/python3`
- Version: `Python 3.13.2`
- Git commit: `a737b42a1f9327fa9fc656cb4bb67cb29f11f497`
- Verified: `yes`

| Recipe | Renderer | Priority | Execution | Result | Score | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| `multi-turn-conversation` | `default` | `P1` | `scripted` | PASS | 1.00 | [screenshot](examples/artifacts/20260724-171258-638194-multi-turn-conversation-default/final.svg) / [video](examples/artifacts/20260724-171258-638194-multi-turn-conversation-default/session.mp4) / [cast](examples/artifacts/20260724-171258-638194-multi-turn-conversation-default/session.cast) / [screen_text](examples/artifacts/20260724-171258-638194-multi-turn-conversation-default/final.txt) / [step_screenshots](examples/artifacts/20260724-171258-638194-multi-turn-conversation-default/steps) |

<details><summary>PASS multi-turn-conversation [default]</summary>

### Assertions

- PASS `output_contains` - contains 'Repository inspection complete.'
- PASS `output_contains` - contains 'Rendering MP4 with agg plus ffmpeg.'
- PASS `output_contains` - contains 'Multi-turn verification passed.'
- PASS `output_contains` - contains 'SESSION COMPLETE'
- PASS `exit_code` - expected 0, got 0

### Steps

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

</details>
