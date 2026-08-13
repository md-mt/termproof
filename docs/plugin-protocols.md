# Plugin protocol stability

TermProof exposes stable plugin protocols from `termproof.protocols`.

## Stable protocols

| Protocol | Required method |
| --- | --- |
| `StepAction` | `execute(session, step, index) -> StepResult` |
| `AssertionType` | `evaluate(recipe, assertion, screen, raw_output, exit_code) -> AssertionResult` |
| `StepAwareAssertionType` | `evaluate(recipe, assertion, screen, raw_output, exit_code, *, steps=None) -> AssertionResult` |
| `ExecutionMode` | `execute(runner, recipe, run_dir) -> tuple[list[StepResult], list[AssertionResult], str, int | None, str]` |
| `Reporter` | `generate(results, build_info=None, before_after=None) -> str` |
| `ScreenRenderer` | `render(text, output_path, cols, rows) -> None` |
| `VideoBackend` | `render(cast_path, output_path, fps) -> None` |
| `AgentRunner` | `run(recipe, prompt, run_dir) -> AgentOutcome` |
| `SessionBackend` | `create_session(argv, cast_path, cwd, env, cols, rows) -> TerminalSession` |
| `ArtifactPublisher` | `publish(source, key) -> PublishedArtifact` |

`StepAction`, `AssertionType`, `StepAwareAssertionType`, `ExecutionMode`, `Reporter`, `ScreenRenderer`, `VideoBackend`, and `ArtifactPublisher` also require a `name: str` class attribute. `AgentRunner` and `SessionBackend` are selected by config keys and do not require a `name`.

`ScreenRenderer` plugins can optionally set `extension = "png"` (or another file extension) so evidence artifacts use that screenshot filename suffix.

### Optional: `render_attributed`

`render` receives the screen as a string, which cannot express colour, bold or
reverse video. A `ScreenRenderer` may additionally define:

```python
def render_attributed(
    self,
    screen: AttributedScreen,
    output_path: Path,
    cols: int,
    rows: int,
) -> None: ...
```

`AttributedScreen` (from `termproof.attributed`) is a per-cell grid: every
`AttributedCell` carries its glyph plus `fg`, `bg`, `bold`, `dim`, `italic`,
`underline`, `strikethrough`, `reverse` and `width`. Colours are either the
literal `"default"`, a pyte colour name such as `"red"`, or a bare `RRGGBB`
hex string; `attributed.cell_colors(cell, style)` resolves one to concrete CSS
colours, applying reverse video.

`dim` is the one field that depends on where the grid came from. A grid parsed
from SGR text sets it; one read from a `pyte.Screen` — which is how `final.svg`
and the video are produced — never does, because pyte 0.8.2 models no dim/faint
attribute. Treat `cell.dim` as authoritative when set and absent otherwise; do
not infer that a cell is not dim.

When the method is present and the pipeline has a grid to offer, TermProof calls
it in preference to `render`, so nothing is lost re-parsing text that the
terminal emulator already parsed. This is additive: a renderer that defines only
`render` keeps working unchanged and keeps receiving the screen as text. Both
builtin `svg` and `png_rsvg` implement it; `png` does not.

`ScreenRenderer` and `VideoBackend` plugins can optionally define a
`from_config(cls, evidence: EvidenceConfig) -> Self` classmethod. When it is
present TermProof calls it instead of the zero-argument constructor, so the
plugin can read the `evidence` config block (see the Configuration section of
the README). Plugins without it keep being constructed with no arguments.
`EvidenceConfig`, and the narrower `SvgRenderConfig`, `PngRenderConfig`, and
`VideoConfig` its sections hold, are exported from `termproof.protocols`
alongside the protocols themselves.

## Assertions and per-step screens

`AssertionType` sees the final screen only, which makes an assertion about a
state the run passes through and then leaves inexpressible. `StepAwareAssertionType`
extends it with `steps`: the `StepResult` list for the steps that ran, in order,
each carrying the screen captured after that step.

`StepResult.screen` is plain text — pyte's already-flattened `display` — not an
`AttributedScreen`. Colour, bold and reverse video are gone by the time an
assertion sees a per-step screen, so a step-aware assertion can match glyphs and
layout but not styling. The `render_attributed` grid described above is built
for the final screen and the video, not for these; see
[`docs/evidence-quality.md`](evidence-quality.md) for why per-step screens are
still flat.

The two protocols are one opt-in apart. TermProof passes `steps` only to an
`evaluate` that declares a parameter of that name, so an assertion written
against `AssertionType` is called with the original five arguments and needs no
source change. A bare `**kwargs` does not count as declaring it — an assertion
that forwards unrecognised arguments to another assertion would otherwise pass
`steps` into one that cannot accept it. Keeping `steps` keyword-only with a
default of `None`, as the protocol declares it, also lets a step-aware assertion
run unchanged on a TermProof that never passes it.

`steps` is `None` when the execution mode supplied no per-step screens, which is
distinct from a run in which no step ran. Both built-in scripted modes supply
them; the agent-driven mode derives its assertions from the agent's own report
and does not go through the assertion registry. The built-in
`step_screen_contains` assertion is the reference implementation.

## ArtifactPublisher

An `ArtifactPublisher` decides where evidence goes once a run has produced it.
It is registered under the `artifact_publishers` config key and selected by
name; `s3` (`termproof.evidence_publish:S3ArtifactPublisher`) ships as the
built-in implementation and publishes to any S3-compatible bucket.

```python
from pathlib import Path

from termproof.protocols import ArtifactPublisher, PublishedArtifact


class MyPublisher:
    name = "my_store"

    def publish(self, source: Path, key: str) -> PublishedArtifact:
        url = upload_somehow(source, key)
        return PublishedArtifact(source=source, key=key, url=url)
```

`key` is the destination-relative identifier the caller has chosen. The layout
of published evidence is the caller's policy, so a publisher should map a key
onto its own namespace rather than invent one.

`PublishedArtifact` carries `source`, `key`, `url`, `published` and `detail`.
The result is a record rather than a bare URL string because publishing is not
the last step: reports reference evidence by local path, so rewriting those
links needs `source` and `url` together. `termproof.evidence_publish` exposes
`url_map_from_published(published)` to turn a batch of results into the
local-path-to-URL map that `rewrite_report_video_links` consumes.

The two failure shapes are distinct and both are reportable without raising:

- `published=False` — the bytes were not transferred (a dry run, an artifact
  the store does not accept). `detail` says why.
- `url=""` — the bytes were transferred but the publisher cannot name a public
  address for them, so a report link should keep pointing at the local file.

Only an artifact that is both published and addressable is rewritten into a
report, so neither failure shape can replace a working local path with a link
that does not resolve. `publish-videos` reports every declined artifact with its
`detail`, records only what was stored in `video-manifest.json`, and exits
non-zero when a batch was offered and nothing was stored — a store that declines
without raising must not read as a successful publish. A dry run is not a
decline: it names URLs without moving bytes and still succeeds.

A publisher may define a `from_target(cls, target: PublishTarget) -> Self`
classmethod to receive the bucket, endpoint, public base URL and dry-run flag
supplied at publish time — the same opt-in pattern `from_config` uses for
renderers. Deployment credentials are passed this way rather than read from
`.termproof/config.yaml`, which is checked in. Publishers without it are
constructed with no arguments.

Because a publisher is an ordinary object returning ordinary results, publishers
compose: a wrapper that tries one publisher, falls back to a second, and records
the degradation in `detail` is a plain implementation of the same protocol.
TermProof does not ship one.

## ExecutionMode runner surface

An `ExecutionMode.execute` implementation receives a `VerificationRunner` and
should only call its stable public methods rather than any underscore-prefixed
internals:

| Method | Purpose |
| --- | --- |
| `run_pty(recipe, run_dir) -> tuple[list[StepResult], str, int | None, str]` | Run scripted steps interactively over a PTY session. |
| `run_process(recipe, run_dir) -> tuple[list[StepResult], str, int | None, str]` | Run the command to completion, then replay the cast. |
| `run_agent_driven(recipe, run_dir) -> tuple[list[StepResult], list[AssertionResult], str, int | None, str]` | Delegate execution to the configured agent runner. |
| `evaluate_assertions(recipe, screen, raw_output, exit_code, *, steps=None) -> list[AssertionResult]` | Evaluate a recipe's assertions against captured output. Pass `steps` so step-aware assertions can read per-step screens. |

The former private methods (`_run_pty`, `_run_process`, `_run_agent_driven`,
`_evaluate_assertions`) remain as deprecated aliases that delegate to the public
methods, but new execution modes should use the public surface above.

## Import policy

New plugins should import protocols from `termproof.protocols`:

```python
from termproof.protocols import StepAction, AssertionType, Reporter
```

The older import locations, such as `termproof.builtin_steps.StepAction`, remain compatibility re-exports.

## Version and deprecation policy

- The signatures above are stable for TermProof `0.x` and `1.x`.
- Additive changes are allowed when existing plugins keep working without source changes.
- Breaking protocol changes require a major version bump and a migration guide.
- Deprecated protocol behavior must stay available for at least one minor release after the deprecation is documented.
- Legacy `tui_verifier.*:Class` config references are still remapped to `termproof.*:Class`.
