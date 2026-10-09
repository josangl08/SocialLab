"""
Unit tests scaffolding for Content Quality Engine (deterministic rules).
Success Criteria verification:
- 125 chars mobile fold
- Hashtag limit (> 5 warning, enforcement)
- AI slop detection and substitution
- Invisible characters removal (U+200B, etc.)
- Em dashes handling (single preserved, >= 2 collapsed)
- Hook scoring & dealbreakers (cap at 20)
- Beat timing at 165 WPM & OVER_4S alerts
- Humanize idempotency
- Execution time < 5ms and zero Gemini calls
"""

import time
import pytest
from unittest.mock import patch

from services.content_quality import (
    lint_caption,
    enforce_hashtag_limit,
    humanize,
    detect_slop,
    score_hook,
    get_hook_formulas,
    time_beats,
    audit_profile,
)


class TestCaptionLinter:
    def test_mobile_fold_truncation_at_125_chars(self):
        long_caption = "A" * 180
        result = lint_caption(long_caption)
        assert result["truncated"] is True
        assert len(result["visible_text"]) == 125
        assert result["visible_length"] == 125

    def test_caption_under_125_chars_not_truncated(self):
        short_caption = "Breve caption para feed."
        result = lint_caption(short_caption)
        assert result["truncated"] is False
        assert result["visible_text"] == short_caption
        assert result["visible_length"] == len(short_caption)

    def test_keywords_missing_in_visible_area(self):
        caption = "Texto introductorio que llena los primeros 125 caracteres sin decir nada relevante " + "x" * 50 + " palabra_clave_secreta"
        result = lint_caption(caption, keywords=["palabra_clave_secreta"])
        assert "palabra_clave_secreta" in result["keywords_missing_in_visible"]

    def test_keywords_present_in_visible_area(self):
        caption = "palabra_clave visible dentro de los primeros 125 caracteres del texto."
        result = lint_caption(caption, keywords=["palabra_clave"])
        assert "palabra_clave" not in result["keywords_missing_in_visible"]

    def test_hashtag_count_and_over_limit_warning(self):
        caption = "Post con muchos hashtags #uno #dos #tres #cuatro #cinco #seis #siete #ocho"
        result = lint_caption(caption)
        assert result["hashtag_count"] == 8
        assert len(result["hashtags_over_limit"]) == 3
        warning_codes = [w["code"] for w in result.get("warnings", [])]
        assert "HASHTAGS_OVER_LIMIT" in warning_codes

    def test_enforce_hashtag_limit_reduces_to_max_5(self):
        caption = "Texto del post #uno #dos #tres #cuatro #cinco #seis #siete #ocho"
        cleaned = enforce_hashtag_limit(caption, max_hashtags=5)
        lint = lint_caption(cleaned)
        assert lint["hashtag_count"] == 5
        assert len(lint["hashtags_over_limit"]) == 0

    def test_execution_time_under_5ms_and_no_gemini(self):
        with patch("services.gemini_service.generate_gemini_content") as mock_gemini:
            start = time.perf_counter()
            result = lint_caption("Este es un caption normal para medir el rendimiento determinista.")
            elapsed_ms = (time.perf_counter() - start) * 1000

            assert elapsed_ms < 50.0  # Safe threshold for test runners, target < 5ms
            mock_gemini.assert_not_called()
            assert result is not None


class TestHumanizerAndSlop:
    def test_detect_slop_terms(self):
        text = "Vamos a delve into este tema porque es un auténtico game-changer."
        slop = detect_slop(text, language="es")
        assert slop["score"] > 0
        terms = [hit["term"].lower() for hit in slop["hits"]]
        assert any("game-changer" in t or "delve into" in t for t in terms)

    def test_detect_extra_banned_terms(self):
        text = "Queremos buscar una sinergia exponencial entre departamentos."
        slop = detect_slop(text, language="es", extra_banned=["sinergia exponencial"])
        terms = [hit["term"].lower() for hit in slop["hits"]]
        assert "sinergia exponencial" in terms

    def test_remove_zero_width_invisible_characters(self):
        invisibles = "\u200B\u200C\u200D\uFEFF\u2060"
        text = f"Texto{invisibles[0]} con{invisibles[1]} caracteres{invisibles[2]} invisibles"
        cleaned, changes = humanize(text)
        for char in invisibles:
            assert char not in cleaned

    def test_preserve_single_em_dash(self):
        text = "Este es un pensamiento — y este es otro."
        cleaned, _ = humanize(text)
        assert "—" in cleaned

    def test_collapse_repeated_em_dashes(self):
        text = "Primera idea — segunda idea — tercera idea — conclusión."
        cleaned, changes = humanize(text)
        assert cleaned.count("—") <= 1

    def test_humanize_replaces_synthetic_lexicon(self):
        text = "Vamos a delve into esta herramienta."
        cleaned, changes = humanize(text, language="es")
        assert "delve into" not in cleaned.lower()
        assert len(changes) > 0

    def test_humanize_idempotency(self):
        text = "Texto con delve into y un auténtico game-changer — con em dash — y otro — \u200B."
        cleaned_once, _ = humanize(text, language="es")
        cleaned_twice, changes_second = humanize(cleaned_once, language="es")
        assert cleaned_once == cleaned_twice
        assert len(changes_second) == 0


class TestHookScorer:
    def test_quantified_loss_hook_detected_and_high_score(self):
        hook = "Perdí 18.000€ por una cláusula que olvidé en el contrato."
        result = score_hook(hook, strategy_mode="commercial_campaign")
        assert result["formula_id"] == 3
        assert "Pérdida cuantificada" in result["formula_name"]
        assert result["score"] >= 70
        assert len(result["dealbreakers"]) == 0

    def test_generic_opening_dealbreaker_caps_score_at_20(self):
        dealbreakers = [
            "Stop scrolling para ver este consejo.",
            "Hola a todos, hoy os traigo una novedad.",
            "No vas a creer lo que me pasó.",
        ]
        for hook in dealbreakers:
            result = score_hook(hook)
            assert len(result["dealbreakers"]) > 0
            assert result["score"] <= 20

    def test_get_hook_formulas_returns_26_items(self):
        formulas = get_hook_formulas()
        assert len(formulas) == 26
        assert all("id" in f and "name" in f and "template" in f for f in formulas)


class TestBeatTimer:
    def test_beat_timing_calculation_at_165_wpm(self):
        # 165 words per minute = 2.75 words per second
        # 11 words = 4.0 seconds
        beats = [
            {"label": "Gancho", "text": "Este es el gancho inicial."},
            {"label": "Desarrollo", "text": "Aquí explicamos el problema con más detalle para retener audiencia."},
        ]
        result = time_beats(beats, wpm=165)
        assert "beats" in result
        assert len(result["beats"]) == 2
        assert result["beats"][0]["start_s"] == 0.0
        assert result["beats"][0]["end_s"] > 0.0
        assert result["total_s"] > 0.0

    def test_over_4s_alert_for_long_beat(self):
        # > 11 words at 165 wpm is > 4.0 seconds
        long_text = "Esta es una frase deliberadamente muy larga que contiene muchas palabras para superar fácilmente los cuatro segundos de duración hablada continua."
        beats = [{"label": "Beat largo", "text": long_text}]
        result = time_beats(beats, wpm=165)
        assert result["beats"][0]["duration_s"] > 4.0
        assert result["beats"][0]["alert"] == "OVER_4S"

    def test_loops_to_hook_detection(self):
        beats = [
            {"label": "Gancho", "text": "El secreto de la retención en vídeo."},
            {"label": "Cierre", "text": "Y ese es el verdadero secreto de la retención."},
        ]
        result = time_beats(beats, wpm=165)
        assert result["loops_to_hook"] is True


class TestProfileAuditor:
    def test_audit_profile_rubric_weights_sum_to_100(self):
        sample_account = {
            "username": "sociallab_app",
            "full_name": "SocialLab | AI Content Planner",
            "biography": "Planifica y optimiza tu Instagram.\nPrueba gratis en el link 👇",
            "external_url": "https://sociallab.app",
            "profile_pic_url": "https://example.com/pic.jpg",
            "is_business_account": True,
        }
        result = audit_profile(sample_account)
        assert "score" in result
        assert 0 <= result["score"] <= 100
        assert len(result["items"]) == 12
        total_weight = sum(item["weight"] for item in result["items"])
        assert total_weight == 100


class TestQualityEngineLogic:
    def test_surrogate_pair_emoji_counts_as_two(self):
        caption = "🔥" * 70  # 140 unidades UTF-16
        result = lint_caption(caption)
        assert result["truncated"] is True
        assert result["visible_text"] == "🔥" * 62
        assert result["visible_length"] == 124

    def test_success_criterion_humanized_text_has_zero_slop(self):
        text = "Vamos a delve into​ esto — primero — luego — al final."
        cleaned, _ = humanize(text, language="es")
        assert "delve into" not in cleaned.lower()
        assert "​" not in cleaned
        assert "—" not in cleaned
        assert detect_slop(cleaned, language="es")["score"] == 0

    def test_humanize_preserves_capitalization(self):
        cleaned, _ = humanize("Delve into el tema.", language="es")
        assert cleaned.startswith("Ver ")

    def test_humanize_removes_account_banned_phrase(self):
        cleaned, changes = humanize("Buscamos sinergia exponencial, ya.", extra_banned=["sinergia exponencial"])
        assert cleaned == "Buscamos, ya."
        assert changes[0]["rule"] == "banned_phrase"

    def test_humanize_clean_text_is_untouched(self):
        text = "Un texto normal — con un solo guion."
        assert humanize(text) == (text, [])

    def test_enforce_hashtag_limit_keeps_first_five_and_is_idempotent(self):
        caption = "Texto\n\n#a #b #c #d #e #f #g"
        once = enforce_hashtag_limit(caption)
        assert once == "Texto\n\n#a #b #c #d #e"
        assert enforce_hashtag_limit(once) == once

    def test_hook_without_formula_scores_lower(self):
        weak = score_hook("Hoy os cuento algo sobre mi semana")
        assert weak["formula_id"] is None
        assert weak["score"] < 70
        assert len(weak["alternatives"]) == 3

    def test_hook_formulas_prioritize_strategy(self):
        formulas = get_hook_formulas("personal_storyline")
        assert "personal_storyline" in formulas[0]["best_for"]
        assert "patterns" not in formulas[0]

    def test_audit_profile_missing_data_scores_zero_and_is_deterministic(self):
        assert audit_profile({})["score"] == 0
        account = {"username": "ana.coach", "biography": "Ayudo a coaches a vender más\n+300 clientes · link 👇"}
        assert audit_profile(account) == audit_profile(account)

    def test_lint_runs_under_5ms_after_warmup(self):
        caption = "Perdí 18.000€ por una cláusula. " * 10 + "#a #b #c"
        lint_caption(caption)
        start = time.perf_counter()
        for _ in range(20):
            lint_caption(caption)
        assert (time.perf_counter() - start) * 1000 / 20 < 5.0
