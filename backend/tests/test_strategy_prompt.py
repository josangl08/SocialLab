"""Perfil de estrategia → contexto del agente (AD-1, AD-3, AD-4)."""
import pytest
from unittest.mock import MagicMock, patch

from services.hermes.prompts import _build_strategy_context, get_monthly_strategy_prompt


@pytest.mark.parametrize("voice", ["personal", "professional"])
def test_type_language_and_audience_present_in_both_voices(voice):
    ctx = _build_strategy_context({
        "account_type": voice, "default_language": "en", "target_audience": "corredores de montaña",
    })
    assert f"Tipo de cuenta: {'profesional' if voice == 'professional' else 'personal'}." in ctx
    assert "Idioma de los captions: inglés." in ctx
    assert "Audiencia: corredores de montaña." in ctx


def test_voice_different_from_type_is_explained():
    ctx = _build_strategy_context({"account_type": "professional", "caption_voice": "personal"})
    assert "Tipo de cuenta: profesional." in ctx
    assert "Voz de los captions: personal (elegida por el usuario aunque la cuenta sea profesional)." in ctx


def test_no_posting_frequency_and_target_is_mix_sum():
    ctx = _build_strategy_context({
        "posting_frequency": "few_times_week", "posts_per_week": 5,
        "content_type_mix": {"reel": 2, "carousel": 1, "post": 0},
    })
    assert "Frecuencia de publicación objetivo" not in ctx
    assert "Publicaciones por semana objetivo: 3." in ctx


def test_posts_per_week_used_only_when_mix_empty():
    ctx = _build_strategy_context({"posts_per_week": 4, "content_type_mix": {}})
    assert "Publicaciones por semana objetivo: 4." in ctx


def test_fixed_days_are_strict():
    ctx = _build_strategy_context({"scheduling_mode": "fixed", "preferred_days": ["Tuesday", "Thursday"]})
    assert "Publica SOLO en estos días: Tuesday, Thursday. Nunca programes un post en otro día." in ctx
    assert "Días preferidos" not in ctx
    assert "cadencia" not in ctx


def test_flexible_days_are_a_preference():
    ctx = _build_strategy_context({"scheduling_mode": "flexible", "preferred_days": ["Tuesday"]})
    assert "Días preferidos por la cuenta: Tuesday." in ctx
    assert "Publica SOLO" not in ctx


def test_empty_best_times_asks_for_empirical_data():
    ctx = _build_strategy_context({"best_times": []})
    assert "analytics_get_empirical_scheduling_data" in ctx
    assert "09:00 y 19:00" in ctx


def test_configured_best_times_are_used():
    ctx = _build_strategy_context({"best_times": ["20:00", "21:00"]})
    assert "20:00, 21:00" in ctx
    assert "Sin horarios fijos" not in ctx


def test_empty_account_has_no_empty_fragments():
    ctx = _build_strategy_context({})
    assert "Tipo de cuenta: personal." in ctx
    assert "Audiencia: comunidad general." in ctx
    for empty in (": .", ":  ", "Pilares de contenido: .", "Sector: .", "Mix de tipos de contenido preferido: ."):
        assert empty not in ctx


def test_monthly_prompt_no_longer_says_type_should_suffice():
    with patch("services.hermes.prompts.get_supabase_admin_client") as mock_get_client, \
            patch("services.hermes.prompts.get_active_brand_rules", return_value=[]):
        mock_get_client.return_value.table.return_value.select.return_value.eq.return_value.execute.return_value = (
            MagicMock(data=[{"id": 7, "account_type": "professional"}])
        )
        prompt = get_monthly_strategy_prompt(7, "2026-11-01")
    assert "deberían bastar" not in prompt
    assert "Tipo de cuenta: profesional." in prompt


def test_weekly_prompt_includes_references_summary():
    from services.hermes.prompts import get_system_prompt
    with patch("services.hermes.prompts.get_supabase_admin_client") as mock_get_client, \
            patch("services.hermes.prompts.get_active_brand_rules", return_value=[]):
        mock_get_client.return_value.table.return_value.select.return_value.eq.return_value.execute.return_value = (
            MagicMock(data=[{"id": 7}])
        )
        with_refs = get_system_prompt(7, references_summary="- @chef_pro: 1000 seguidores")
        without = get_system_prompt(7)
    assert "Cuentas de referencia (qué publican y qué les funciona):\n- @chef_pro" in with_refs
    assert "Cuentas de referencia (qué publican" not in without
