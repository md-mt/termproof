# AGENTS.md

## Test runner gap: unittest vs pytest for PTY flakes

CI runs `uv run coverage run -m unittest discover -s tests`. The PTY idle-detection
race in `TerminalSession.wait_for_idle()` (fixed in fm/flaky-pty-p4) reproduced at
199/200 iterations under pytest but 0/20 under unittest. The difference is pytest's
additional harness startup overhead, which makes the blank-initial-screen window race
much easier to hit. If a new PTY-related flake is reported locally under pytest but
not seen in CI, check whether CI uses unittest — that gap can mask the failure.
