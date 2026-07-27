# Bubble Tea

Bubble Tea applications work well with recipes that wait for prompt text, send key presses, and assert final screen state.

```bash
termproof init .termproof/recipes --name bubbletea-smoke --command "./my-tui"
termproof run .termproof/recipes --video
```

See the repository guide at `docs/guides/bubbletea.md` for detailed patterns.
