# TUI Verification - 1/1 Passed

## Build Provenance

- Mode: `installed`
- Command: `python3 banner.py`
- Binary: `python3`
- Version: `Python 3.x`
- Git commit: `<oracle-commit>`
- Verified: `yes`

| Recipe | Renderer | Priority | Execution | Result | Score | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| `banner-basic` | `default` | `P2` | `scripted` | PASS | 1.00 | [screenshot](final.svg) / [cast](session.cast) / [screen_text](final.txt) / [step_screenshots](steps) |

<details><summary>PASS banner-basic [default]</summary>

### Assertions

- PASS `output has fixture title` - contains 'TermProof Fixture App'
- PASS `screen has menu` - contains 'menu:'
- PASS `exit_code` - expected 0, got 0

### Steps

- PASS `wait for banner title` - found 'TermProof Fixture App'
- PASS `wait for ready status` - found 'status: ready'

</details>
