"""strategy_linter: catálogo de AD-5."""
import time

import pytest

from services.content_quality import lint_strategy

CLEAN = {
    "account_type": "professional",
    "caption_voice": None,
    "scheduling_mode": "fixed",
    "preferred_days": ["Tuesday", "Thursday", "Saturday"],
    "content_type_mix": {"reel": 2, "carousel": 1},
    "content_pillars": ["recetas", "técnica"],
    "target_audience": "cocineros caseros",
    "style_guide": "directo",
    "banned_phrases": ["oferta"],
    "best_times": ["20:00"],
    "reference_accounts": ["a", "b"],
    "hashtag_strategy": "moderate",
}


def _codes(account, empirical=None):
    return {i["code"] for i in lint_strategy(account, empirical)}


def test_clean_profile_has_no_issues():
    assert lint_strategy(CLEAN) == []


@pytest.mark.parametrize("override, code, severity, tab", [
    ({"preferred_days": []}, "FIXED_NO_DAYS", "error", "publicacion"),
    ({"content_type_mix": {"reel": 0}}, "MIX_EMPTY", "error", "publicacion"),
    ({"content_type_mix": {"reel": 3, "post": 1}}, "MIX_EXCEEDS_DAYS", "warning", "publicacion"),
    ({"caption_voice": "personal"}, "VOICE_TYPE_MISMATCH", "info", "marca"),
    ({"content_pillars": []}, "NO_PILLARS", "warning", "marca"),
    ({"target_audience": "  "}, "NO_AUDIENCE", "warning", "marca"),
    ({"style_guide": "Nada de Oferta agresiva"}, "BANNED_IN_PILLARS", "warning", "marca"),
    ({"best_times": ["09:00", "18:00"]}, "DEFAULT_BEST_TIMES", "info", "publicacion"),
    ({"reference_accounts": list("abcdef")}, "TOO_MANY_REFERENCES", "error", "referentes"),
    ({"account_type": "personal", "hashtag_strategy": "maximum"}, "PERSONAL_MAX_HASHTAGS", "info", "publicacion"),
])
def test_each_code(override, code, severity, tab):
    issues = lint_strategy({**CLEAN, **override})
    issue = next(i for i in issues if i["code"] == code)
    assert issue["severity"] == severity
    assert issue["tab"] == tab
    assert issue["message"]


def test_best_times_disagree_uses_empirical():
    empirical = {"has_data": True, "top_times": ["08:00"], "summary_text": "Lun 08:00"}
    assert "BEST_TIMES_DISAGREE" in _codes(CLEAN, empirical)
    assert "BEST_TIMES_DISAGREE" not in _codes(CLEAN, {"has_data": False, "top_times": []})


def test_fast_and_pure():
    start = time.perf_counter()
    for _ in range(100):
        lint_strategy({**CLEAN, "preferred_days": []})
    assert (time.perf_counter() - start) / 100 < 0.005
