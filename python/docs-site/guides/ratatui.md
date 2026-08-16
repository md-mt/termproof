# Ratatui

Ratatui applications should expose deterministic startup text or test-mode fixtures so recipes can wait for stable states.

```bash
termproof init .termproof/recipes --name ratatui-smoke --command "cargo run --bin my-tui"
termproof run .termproof/recipes --video
```

See the repository guide at `docs/guides/ratatui.md` for detailed patterns.
