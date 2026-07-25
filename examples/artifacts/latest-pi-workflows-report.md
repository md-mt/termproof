# TUI Verification - 6/6 Passed

## Build Provenance

- Mode: `installed`
- Command: `python3 examples/apps/pi_cli_help_matrix.py overview`
- Binary: `/Users/mengwei/tui-verifier/.venv/bin/python3`
- Version: `Python 3.13.2`
- Git commit: `397920e31be55e19957aaac598110e399e8b2f0d`
- Verified: `yes`

| Recipe | Renderer | Priority | Execution | Result | Score | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| `pi-workflow-cli-capability-map` | `default` | `P0` | `scripted` | PASS | 1.00 | [screenshot](examples/artifacts/20260724-180304-090130-pi-workflow-cli-capability-map-default/final.svg) / [video](examples/artifacts/20260724-180304-090130-pi-workflow-cli-capability-map-default/session.mp4) / [cast](examples/artifacts/20260724-180304-090130-pi-workflow-cli-capability-map-default/session.cast) / [screen_text](examples/artifacts/20260724-180304-090130-pi-workflow-cli-capability-map-default/final.txt) / [step_screenshots](examples/artifacts/20260724-180304-090130-pi-workflow-cli-capability-map-default/steps) |
| `pi-workflow-package-lifecycle` | `default` | `P0` | `scripted` | PASS | 1.00 | [screenshot](examples/artifacts/20260724-180306-746994-pi-workflow-package-lifecycle-default/final.svg) / [video](examples/artifacts/20260724-180306-746994-pi-workflow-package-lifecycle-default/session.mp4) / [cast](examples/artifacts/20260724-180306-746994-pi-workflow-package-lifecycle-default/session.cast) / [screen_text](examples/artifacts/20260724-180306-746994-pi-workflow-package-lifecycle-default/final.txt) / [step_screenshots](examples/artifacts/20260724-180306-746994-pi-workflow-package-lifecycle-default/steps) |
| `pi-workflow-readonly-review` | `default` | `P1` | `scripted` | PASS | 1.00 | [screenshot](examples/artifacts/20260724-180308-558779-pi-workflow-readonly-review-default/final.svg) / [video](examples/artifacts/20260724-180308-558779-pi-workflow-readonly-review-default/session.mp4) / [cast](examples/artifacts/20260724-180308-558779-pi-workflow-readonly-review-default/session.cast) / [screen_text](examples/artifacts/20260724-180308-558779-pi-workflow-readonly-review-default/final.txt) / [step_screenshots](examples/artifacts/20260724-180308-558779-pi-workflow-readonly-review-default/steps) |
| `pi-workflow-guarded-edit` | `default` | `P1` | `scripted` | PASS | 1.00 | [screenshot](examples/artifacts/20260724-180316-345107-pi-workflow-guarded-edit-default/final.svg) / [video](examples/artifacts/20260724-180316-345107-pi-workflow-guarded-edit-default/session.mp4) / [cast](examples/artifacts/20260724-180316-345107-pi-workflow-guarded-edit-default/session.cast) / [screen_text](examples/artifacts/20260724-180316-345107-pi-workflow-guarded-edit-default/final.txt) / [step_screenshots](examples/artifacts/20260724-180316-345107-pi-workflow-guarded-edit-default/steps) |
| `pi-workflow-session-resume-export` | `default` | `P1` | `scripted` | PASS | 1.00 | [screenshot](examples/artifacts/20260724-180323-723793-pi-workflow-session-resume-export-default/final.svg) / [video](examples/artifacts/20260724-180323-723793-pi-workflow-session-resume-export-default/session.mp4) / [cast](examples/artifacts/20260724-180323-723793-pi-workflow-session-resume-export-default/session.cast) / [screen_text](examples/artifacts/20260724-180323-723793-pi-workflow-session-resume-export-default/final.txt) / [step_screenshots](examples/artifacts/20260724-180323-723793-pi-workflow-session-resume-export-default/steps) |
| `pi-workflow-model-context` | `default` | `P1` | `scripted` | PASS | 1.00 | [screenshot](examples/artifacts/20260724-180329-469986-pi-workflow-model-context-default/final.svg) / [video](examples/artifacts/20260724-180329-469986-pi-workflow-model-context-default/session.mp4) / [cast](examples/artifacts/20260724-180329-469986-pi-workflow-model-context-default/session.cast) / [screen_text](examples/artifacts/20260724-180329-469986-pi-workflow-model-context-default/final.txt) / [step_screenshots](examples/artifacts/20260724-180329-469986-pi-workflow-model-context-default/steps) |

<details><summary>PASS pi-workflow-cli-capability-map [default]</summary>

### Assertions

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

### Steps

- PASS `wait for usage` - found 'Usage:'

</details>

<details><summary>PASS pi-workflow-package-lifecycle [default]</summary>

### Assertions

- PASS `output_contains` - contains 'pi install <source>'
- PASS `output_contains` - contains 'pi remove <source>'
- PASS `output_contains` - contains 'pi update [source|self|pi]'
- PASS `output_contains` - contains 'pi list [--approve|--no-approve]'
- PASS `output_contains` - contains 'Open the resource configuration TUI'
- PASS `output_contains` - contains 'Press Tab in the TUI'
- PASS `sandbox failure is absent` - sandbox failure is absent
- PASS `sandbox launcher error is absent` - sandbox launcher error is absent
- PASS `exit_code` - expected 0, got 0

### Steps

- PASS `wait for install help` - found 'pi install <source>'

</details>

<details><summary>PASS pi-workflow-readonly-review [default]</summary>

### Assertions

- PASS `output_contains` - contains '--tools read,grep,find,ls'
- PASS `output_contains` - contains 'no write/edit tools were enabled'
- PASS `output_contains` - contains 'READONLY REVIEW COMPLETE'
- PASS `output_contains` - contains 'WORKFLOW SESSION COMPLETE'
- PASS `exit_code` - expected 0, got 0

### Steps

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

</details>

<details><summary>PASS pi-workflow-guarded-edit [default]</summary>

### Assertions

- PASS `output_contains` - contains 'tool allowlist: read,bash,edit,write'
- PASS `output_contains` - contains 'patch applied'
- PASS `output_contains` - contains '12 tests passed'
- PASS `output_contains` - contains 'diff reviewed'
- PASS `output_contains` - contains 'GUARDED EDIT COMPLETE'
- PASS `exit_code` - expected 0, got 0

### Steps

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

</details>

<details><summary>PASS pi-workflow-session-resume-export [default]</summary>

### Assertions

- PASS `output_contains` - contains '--name "Verifier workflow audit"'
- PASS `output_contains` - contains '--continue'
- PASS `output_contains` - contains '--session workflow-001'
- PASS `output_contains` - contains '--fork workflow-001'
- PASS `output_contains` - contains '--export session.jsonl output.html'
- PASS `output_contains` - contains 'SESSION RESUME EXPORT COMPLETE'
- PASS `exit_code` - expected 0, got 0

### Steps

- PASS `wait for prompt` - found 'pi>'
- PASS `start session` - sent line
- PASS `wait for start` - found 'SESSION STARTED'
- PASS `continue session` - sent line
- PASS `wait for resume` - found 'SESSION RESUMED'
- PASS `fork export` - sent line
- PASS `wait for export` - found 'SESSION RESUME EXPORT COMPLETE'
- PASS `close session` - sent line
- PASS `wait for close` - found 'WORKFLOW SESSION COMPLETE'

</details>

<details><summary>PASS pi-workflow-model-context [default]</summary>

### Assertions

- PASS `output_contains` - contains '--provider openai --model gpt-4o-mini'
- PASS `output_contains` - contains '--model sonnet:high --thinking high'
- PASS `output_contains` - contains '--append-system-prompt project-rules.md'
- PASS `output_contains` - contains '--skill ./skills/reviewer'
- PASS `output_contains` - contains '--prompt-template ./prompts/fix-bug.md'
- PASS `output_contains` - contains '--offline --no-context-files --no-extensions --no-skills'
- PASS `output_contains` - contains 'MODEL CONTEXT WORKFLOW COMPLETE'
- PASS `exit_code` - expected 0, got 0

### Steps

- PASS `wait for prompt` - found 'pi>'
- PASS `choose model` - sent line
- PASS `wait for model` - found 'MODEL ROUTING READY'
- PASS `load context` - sent line
- PASS `wait for context` - found 'CONTEXT RESOURCES LOADED'
- PASS `configure startup` - sent line
- PASS `wait for startup` - found 'MODEL CONTEXT WORKFLOW COMPLETE'
- PASS `close session` - sent line
- PASS `wait for close` - found 'WORKFLOW SESSION COMPLETE'

</details>
