# Plugins

TermProof plugins extend recipe steps, assertions, execution modes, reporters, renderers, video backends, agent runners, and session backends.

Use the plugin CLI to inspect configured plugins:

```bash
termproof plugins list
termproof plugins search textual
termproof plugins install termproof-textual --dry-run
```

Community plugin entries live in `docs/plugins.md` until the registry needs automation.

## First-Party Examples

- [termproof-slack-reporter](https://github.com/md-mt/termproof-slack-reporter) posts run summaries to Slack incoming webhooks.
- [termproof-docker-backend](https://github.com/md-mt/termproof-docker-backend) runs recipe commands inside Docker containers.
- [termproof-png-renderer](https://github.com/md-mt/termproof-png-renderer) writes PNG screenshots for visual evidence.
