# Community plugins

TermProof is extensible via a plugin registry: steps, assertions, session backends, video backends, reporters, execution modes, and agent runners. This directory lists community-provided plugins.

## What counts as a plugin?

A plugin is a Python class referenced in `.termproof/config.yaml` (or `~/.config/termproof/config.yaml`) and installed alongside `termproof`. Example layout:

```yaml
# .termproof/config.yaml
steps:
  wait_for_regex: my_org.termproof_steps:WaitForRegexStep
assertions:
  json_schema: my_org.termproof_assertions:JsonSchemaAssertion
session_backend: my_org.termproof_session:DockerSessionBackend
reporters:
  junit_xml: my_org.termproof_reporters:JunitReporter
```

See [`plugin-protocols.md`](plugin-protocols.md) for the stable protocol contract and `termproof/config.py` for built-ins.

TermProof also ships a built-in Docker session backend:

```yaml
session_backend: docker
docker:
  image: python:3.12-slim
  workdir: /workspace
  volumes:
    - host: .
      container: /workspace
  env:
    PYTHONUNBUFFERED: "1"
```

The backend runs each recipe command with `docker run --rm --interactive --tty`.
Recipe `command.env` values are passed into the container alongside `docker.env`.

There is also a built-in tmux session backend, which takes the screen from a
real terminal emulator's grid rather than reconstructing it from the pty byte
stream with pyte. It needs `tmux` on `PATH`:

```yaml
session_backend: tmux
```

## Built-in screen renderers

| Name | Output | Notes |
| --- | --- | --- |
| `svg` | SVG | Default. Colour and text attributes, one `<text>` per cell. |
| `png_rsvg` | PNG | Rasterizes the same SVG with `rsvg-convert`, so the two cannot drift. Needs `librsvg`. |
| `png` | PNG | Draws text with Pillow. No colour or attributes, but needs no external tool. |

```bash
termproof run .termproof/recipes --screen-renderer png_rsvg
```

## Built-in video backends

| Name | Notes |
| --- | --- |
| `agg_ffmpeg` | Default. Shells out to `agg`, then `ffmpeg`. |
| `attributed_rsvg` | Renders each frame from the same attributed grid the screenshots use, so a video frame and a screenshot of the same moment are the same image. One rasterizer call per frame, so slower. Needs `rsvg-convert` and `ffmpeg`. |

## Listing

| Name | Description | Install | Author |
| --- | --- | --- | --- |
| [termproof-slack-reporter](https://github.com/md-mt/termproof-slack-reporter) | Reporter that posts TermProof run summaries to Slack incoming webhooks | `pip install git+https://github.com/md-mt/termproof-slack-reporter.git` | [@md-mt](https://github.com/md-mt) |
| [termproof-docker-backend](https://github.com/md-mt/termproof-docker-backend) | Session backend that runs recipe commands inside Docker containers | `pip install git+https://github.com/md-mt/termproof-docker-backend.git` | [@md-mt](https://github.com/md-mt) |
| [termproof-png-renderer](https://github.com/md-mt/termproof-png-renderer) | Screen renderer that writes PNG screenshots for visual evidence | `pip install git+https://github.com/md-mt/termproof-png-renderer.git` | [@md-mt](https://github.com/md-mt) |

Search or install from this manual directory with:

```bash
termproof plugins search textual
termproof plugins install termproof-textual
```

To list your plugin here, open a PR editing this file with:

- Name — package or plugin identifier.
- Description — one-line purpose + which registry it targets.
- Install — pip / uv instruction.
- Author — GitHub handle or organization.
- Optional: link to repository and documentation.

### Example entry

```md
| textual-snapshot | `wait_for_textual` step that waits for Textual DOM selectors | `pip install termproof-textual` | [@you](https://github.com/you) |
```

### Sought plugins

From open issues:

- **Framework helpers** for Textual, Bubble Tea, and Ratatui recipes — see [#24](https://github.com/md-mt/termproof/issues/24)

## Publishing

If you publish a plugin repo, follow:

1. Name: `termproof-<integration>` (e.g., `termproof-textual`, `termproof-bubbletea`).
2. Entry points in `pyproject.toml` or documented `module:Class` references.
3. Include a recipe pack under `examples/` or `recipes/` and a CI job that runs `termproof run` with `--video`.
4. Add the **Verified by TermProof** badge (see [`verified-badge.md`](verified-badge.md)).

## Registry roadmap

- Manual list (now, this file) → automated registry when >30 entries (see [#22](https://github.com/md-mt/termproof/issues/22)).
- Protocol stability is documented in [`plugin-protocols.md`](plugin-protocols.md). Recipe format v1.0 remains tracked in [#31](https://github.com/md-mt/termproof/issues/31).
