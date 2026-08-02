# TUI Verification - PASS

- Recipe: `json-all-assertions`
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

- PASS `output contains app name` - contains 'fixture'
- PASS `output does not contain absent marker` - does not contain 'not-present-marker'
- PASS `screen contains status` - contains 'ok'
- PASS `screen does not contain absent marker` - does not contain 'not-present-marker'
- PASS `exit code is zero` - expected 0, got 0
- PASS `artifact file exists` - corpus/apps/fixture-artifact.txt
- PASS `artifact file contains content` - contains 'fixture artifact content'
- PASS `output matches json schema` - matches JSON schema
- PASS `exit_code` - expected 0, got 0

## Steps

- PASS `wait for json output` - found 'fixture'
