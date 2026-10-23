"""
Content Quality Engine
Pure Python synchronous quality inspection, linting, anti-slop humanizer,
hook scoring, beat timing, profile auditing and strategy linting.
"""

from .caption_linter import lint_caption, enforce_hashtag_limit
from .humanizer import humanize, detect_slop
from .hook_scorer import score_hook, get_hook_formulas
from .beat_timer import time_beats
from .profile_auditor import audit_profile
from .schedule_disagreement import schedule_disagreement
from .strategy_linter import lint_strategy, StrategyIssue

__all__ = [
    "lint_caption",
    "enforce_hashtag_limit",
    "humanize",
    "detect_slop",
    "score_hook",
    "get_hook_formulas",
    "time_beats",
    "audit_profile",
    "schedule_disagreement",
    "lint_strategy",
    "StrategyIssue",
]
