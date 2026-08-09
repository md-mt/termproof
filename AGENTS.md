# AGENTS.md

## PTY tests must not depend on how fast the child starts

`wait_for_idle` must not arm its stable window before the child's first byte:
until something has been emitted, a blank screen is a session that has not
started, not a session that has settled.

The test-side corollary is that a PTY test must never depend on first output
arriving within `stable_seconds`. Time-to-first-PTY-byte is environment-bound —
a cold interpreter (for example the ephemeral overlay `uv run --with <pkg>`
builds per invocation) or a loaded machine measures ~0.35 s against a warm
~0.10 s, which is enough to cross a 0.3 s window. Gate on observed output with
`wait_for_text` before measuring quiescence, rather than assuming the child is
already talking.
