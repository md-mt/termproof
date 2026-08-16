"""Evidence-first verification for terminal and TUI applications."""

from .attributed import (
    AttributedCell,
    AttributedScreen,
    SvgStyle,
    attributed_screen_from_ansi_text,
    attributed_screen_from_pyte,
    attributed_screen_from_text,
    screen_svg,
)
from .build_info import BuildInfo
from .config import (
    EvidenceConfig,
    PngRenderConfig,
    SvgRenderConfig,
    VerifierConfig,
    VideoConfig,
    load_config,
)
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
from .selection import select_names, select_recipes

__all__ = [
    "AgentRunner",
    "AssertionResult",
    "AssertionType",
    "AttributedCell",
    "AttributedScreen",
    "BuildInfo",
    "EvidenceConfig",
    "ExecutionMode",
    "PngRenderConfig",
    "Recipe",
    "Registry",
    "Reporter",
    "ReportGenerator",
    "RunResult",
    "ScreenRenderer",
    "SessionBackend",
    "StepAction",
    "StepResult",
    "SvgRenderConfig",
    "SvgStyle",
    "VideoBackend",
    "VideoConfig",
    "VerificationRunner",
    "VerifierConfig",
    "attributed_screen_from_ansi_text",
    "attributed_screen_from_pyte",
    "attributed_screen_from_text",
    "load_config",
    "load_recipe",
    "screen_svg",
    "select_names",
    "select_recipes",
]
