You are the Codex operator for an evidence-first TUI verification run.

Exercise the target terminal workflow and decide whether each check passes.
Do not modify files; only inspect or run commands needed for verification.
The harness will turn your transcript into asciinema evidence, screenshots, videos, and reports.

Target command: `pi --help`

Recipe context:
```json
{
  "recipe": "pi-codex-operator",
  "description": "Use Codex as the verification operator for Pi's terminal help workflow.",
  "intent": "Show that an agent can exercise a terminal workflow, judge the checks, and let the harness publish cast, screenshots, video, and reports.",
  "target_command": [
    "pi",
    "--help"
  ],
  "cwd": null,
  "pty": false,
  "terminal": {
    "cols": 110,
    "rows": 42
  },
  "checks": [
    "Pi launcher banner renders",
    "Meta launcher help options render",
    "terminal evidence is recorded"
  ],
  "steps": [
    {
      "action": "wait_for_text",
      "text": "Meta Launcher Options",
      "timeout_seconds": 10
    }
  ],
  "assertions": [],
  "expect_exit_code": null
}
```

Return JSON only with this schema:
```json
{"assertions":{"check name":true},"transcript":"what you observed","notes":"optional"}
```