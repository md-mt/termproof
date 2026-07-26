import tempfile
import textwrap
from pathlib import Path

from termproof.config import load_config

with tempfile.TemporaryDirectory() as tmp:
    proj = Path(tmp)
    cfg_dir = proj / ".termproof"
    cfg_dir.mkdir()
    (cfg_dir / "config.yaml").write_text(
        textwrap.dedent("""
        steps:
          wait_for_regex: termproof_my_plugin.steps:WaitForRegex
        assertions:
          screen_count: termproof_my_plugin.assertions:ScreenCount
        reporters:
          json_summary: termproof_my_plugin.reporters:JsonSummaryReporter
        """),
        encoding="utf-8",
    )
    cfg = load_config(project_path=proj)
    assert "wait_for_regex" in cfg.steps
    assert "screen_count" in cfg.assertions
    assert "json_summary" in cfg.reporters
    from termproof.runner import VerificationRunner

    runner = VerificationRunner(config=cfg)
    assert "wait_for_regex" in runner.step_registry.names()
    assert "screen_count" in runner.assertion_registry.names()
    assert "json_summary" in runner.reporter_registry.names()
    print("Config wiring verified")
