"""Evidence-first verification for terminal and TUI applications."""

from .config import VerifierConfig, load_config
from .models import AssertionResult, Recipe, RunResult, StepResult, load_recipe
from .protocols import (
    AgentRunner,
    AssertionType,
    ExecutionMode,
    Reporter,
    ScreenRenderer,
    SessionBackend,
    StepAction,
    VideoBackend,
)
from .registry import Registry
from .report import ReportGenerator
from .runner import VerificationRunner

__all__ = [
    "AgentRunner",
    "AssertionResult",
    "AssertionType",
    "ExecutionMode",
    "Recipe",
    "Registry",
    "Reporter",
    "ReportGenerator",
    "RunResult",
    "ScreenRenderer",
    "SessionBackend",
    "StepAction",
    "StepResult",
    "VideoBackend",
    "VerificationRunner",
    "VerifierConfig",
    "load_config",
    "load_recipe",
]
