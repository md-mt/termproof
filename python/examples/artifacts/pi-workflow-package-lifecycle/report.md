# TUI Verification - PASS

- Recipe: `pi-workflow-package-lifecycle`
- Renderer: `default`
- Priority: `P0`
- Execution: `scripted`
- Score: `1.00`
- Exit code: `0`
- Duration: `1.81s`

## Artifacts

- cast: `examples/artifacts/pi-workflow-package-lifecycle/session.cast`
- screenshot: `examples/artifacts/pi-workflow-package-lifecycle/final.svg`
- screen_text: `examples/artifacts/pi-workflow-package-lifecycle/final.txt`
- exit_code_file: `examples/artifacts/pi-workflow-package-lifecycle/session.exitcode`
- step_screenshots: `examples/artifacts/pi-workflow-package-lifecycle/steps`
- video: `examples/artifacts/pi-workflow-package-lifecycle/session.mp4`

## Assertions

- PASS `output_contains` - contains 'pi install <source>'
- PASS `output_contains` - contains 'pi remove <source>'
- PASS `output_contains` - contains 'pi update [source|self|pi]'
- PASS `output_contains` - contains 'pi list [--approve|--no-approve]'
- PASS `output_contains` - contains 'Open the resource configuration TUI'
- PASS `output_contains` - contains 'Press Tab in the TUI'
- PASS `sandbox failure is absent` - sandbox failure is absent
- PASS `sandbox launcher error is absent` - sandbox launcher error is absent
- PASS `exit_code` - expected 0, got 0

## Steps

- PASS `wait for install help` - found 'pi install <source>'
