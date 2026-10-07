import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

from services.hermes.skills import (
    get_skill,
    save_skill,
    run_visual_performance_skill,
    VISUAL_PERFORMANCE_SKILL,
    _is_fresh,
    build_niche_key,
    get_niche_insight,
    save_niche_insight,
    _is_niche_insight_fresh,
    run_niche_research_skill,
    run_niche_research_for_account,
)


def test_get_skill_returns_none_when_no_row():
    with patch("services.hermes.skills.get_supabase_admin_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

        assert get_skill(7, VISUAL_PERFORMANCE_SKILL) is None


def test_save_skill_upserts_on_account_and_name():
    with patch("services.hermes.skills.get_supabase_admin_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.table.return_value.upsert.return_value.execute.return_value = MagicMock(data=[{"id": 1}])

        save_skill(7, VISUAL_PERFORMANCE_SKILL, "print(1)", "resumen")

        upsert_call = mock_client.table.return_value.upsert.call_args
        assert upsert_call[0][0]["account_id"] == 7
        assert upsert_call[0][0]["name"] == VISUAL_PERFORMANCE_SKILL
        assert upsert_call[0][0]["generated_code"] == "print(1)"
        assert upsert_call[0][0]["last_result_summary"] == "resumen"
        assert upsert_call[1]["on_conflict"] == "account_id,name"


def test_is_fresh_true_within_window():
    row = {"updated_at": datetime.now(timezone.utc).isoformat()}
    assert _is_fresh(row, freshness_days=14) is True


def test_is_fresh_false_outside_window():
    row = {"updated_at": (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()}
    assert _is_fresh(row, freshness_days=14) is False


def test_is_fresh_false_when_missing():
    assert _is_fresh({}, freshness_days=14) is False


def test_run_visual_performance_skill_reuses_fresh_result():
    with patch("services.hermes.skills.get_skill") as mock_get_skill,          patch("services.hermes.skills._run_code_execution") as mock_run_exec:
        mock_get_skill.return_value = {
            "last_result_summary": "Resumen guardado",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        result = run_visual_performance_skill(7)

        assert result["summary"] == "Resumen guardado"
        assert result["fresh"] is True
        assert result["regenerated"] is False
        mock_run_exec.assert_not_called()


def test_run_visual_performance_skill_regenerates_when_stale():
    with patch("services.hermes.skills.get_skill") as mock_get_skill,          patch("services.hermes.skills.get_supabase_admin_client"),          patch("services.hermes.skills.AnalyticsService") as mock_analytics_cls,          patch("services.hermes.skills._run_code_execution") as mock_run_exec,          patch("services.hermes.skills.save_skill") as mock_save:
        mock_get_skill.return_value = {
            "last_result_summary": "Viejo",
            "updated_at": (datetime.now(timezone.utc) - timedelta(days=30)).isoformat(),
        }
        mock_analytics_cls.return_value.get_visual_performance_data.return_value = [
            {"theme": "playa", "total_interactions": 100}
        ]
        mock_run_exec.return_value = {
            "generated_code": "print('hola')",
            "execution_result": "hola",
            "summary": "Las fotos de playa rinden mejor.",
        }

        result = run_visual_performance_skill(7)

        assert result["summary"] == "Las fotos de playa rinden mejor."
        assert result["regenerated"] is True
        mock_save.assert_called_once_with(7, VISUAL_PERFORMANCE_SKILL, "print('hola')", "Las fotos de playa rinden mejor.")


def test_run_visual_performance_skill_force_refresh_ignores_freshness():
    with patch("services.hermes.skills.get_skill") as mock_get_skill,          patch("services.hermes.skills.get_supabase_admin_client"),          patch("services.hermes.skills.AnalyticsService") as mock_analytics_cls,          patch("services.hermes.skills._run_code_execution") as mock_run_exec,          patch("services.hermes.skills.save_skill"):
        mock_get_skill.return_value = {
            "last_result_summary": "Fresco pero se pide refrescar",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        mock_analytics_cls.return_value.get_visual_performance_data.return_value = [
            {"theme": "ciudad", "total_interactions": 50}
        ]
        mock_run_exec.return_value = {
            "generated_code": "code",
            "execution_result": "result",
            "summary": "Nuevo resumen.",
        }

        result = run_visual_performance_skill(7, force_refresh=True)

        assert result["summary"] == "Nuevo resumen."
        assert result["regenerated"] is True


def test_run_visual_performance_skill_no_data_skips_gemini_call():
    with patch("services.hermes.skills.get_skill", return_value=None),          patch("services.hermes.skills.get_supabase_admin_client"),          patch("services.hermes.skills.AnalyticsService") as mock_analytics_cls,          patch("services.hermes.skills._run_code_execution") as mock_run_exec:
        mock_analytics_cls.return_value.get_visual_performance_data.return_value = []

        result = run_visual_performance_skill(7)

        assert "suficientes" in result["summary"]
        mock_run_exec.assert_not_called()


def test_run_visual_performance_skill_handles_gemini_error_gracefully():
    with patch("services.hermes.skills.get_skill", return_value=None),          patch("services.hermes.skills.get_supabase_admin_client"),          patch("services.hermes.skills.AnalyticsService") as mock_analytics_cls,          patch("services.hermes.skills._run_code_execution", side_effect=Exception("API error")):
        mock_analytics_cls.return_value.get_visual_performance_data.return_value = [
            {"theme": "playa", "total_interactions": 100}
        ]

        result = run_visual_performance_skill(7)

        assert result["regenerated"] is False
        assert "No pude completar" in result["summary"]


def test_build_niche_key_arbitrary_and_slug():
    # Sector y purpose arbitrarios con acentos
    account1 = {"sector": "Repostería artesanal", "purpose": "Vender tartas"}
    assert build_niche_key(account1) == "reposteria_artesanal_vender_tartas"

    # Con símbolos y caracteres especiales
    account2 = {"sector": "Tech & AI / Data!", "purpose": "B2B #1"}
    assert build_niche_key(account2) == "tech_ai_data_b2b_1"

    # Solo sector
    account3 = {"sector": "Fotografía Submarina", "purpose": ""}
    assert build_niche_key(account3) == "fotografia_submarina"

    # Vacío
    assert build_niche_key({"sector": "", "purpose": ""}) == ""
    assert build_niche_key({}) == ""


def test_is_niche_insight_fresh_direct():
    # Vigente
    future = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
    assert _is_niche_insight_fresh({"expires_at": future}) is True

    # Caducado
    past = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    assert _is_niche_insight_fresh({"expires_at": past}) is False

    # Sin expires_at o inválido
    assert _is_niche_insight_fresh({}) is False
    assert _is_niche_insight_fresh({"expires_at": None}) is False
    assert _is_niche_insight_fresh({"expires_at": "not-a-date"}) is False


def test_run_niche_research_for_account_produces_brief_for_arbitrary_sector():
    with patch("services.hermes.skills.get_supabase_admin_client") as mock_get_client,          patch("services.hermes.skills.run_niche_research_skill") as mock_run_skill:

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"sector": "Repostería artesanal", "purpose": "Vender tartas", "target_audience": "Gourmet"}]
        )
        mock_run_skill.return_value = {"brief": "Tendencias en repostería visual y reels de recetas."}

        result = run_niche_research_for_account(42)

        assert result["niche"] == "reposteria_artesanal_vender_tartas"
        assert result["brief"] == "Tendencias en repostería visual y reels de recetas."
        mock_run_skill.assert_called_once_with(
            "reposteria_artesanal_vender_tartas",
            label="Repostería artesanal Vender tartas Gourmet",
            force_refresh=False,
        )


def test_run_niche_research_for_account_empty_when_no_niche():
    with patch("services.hermes.skills.get_supabase_admin_client") as mock_get_client,          patch("services.hermes.skills.run_niche_research_skill") as mock_run_skill:

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"sector": "", "purpose": "", "target_audience": ""}]
        )

        result = run_niche_research_for_account(99)

        assert result == {"niche": "", "brief": ""}
        mock_run_skill.assert_not_called()


def test_run_niche_research_skill_reuses_fresh_insight():
    with patch("services.hermes.skills.get_niche_insight") as mock_get_insight,          patch("services.hermes.skills._run_search_grounding") as mock_search:

        mock_get_insight.return_value = {
            "brief": "Brief en cache",
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=15)).isoformat(),
        }

        result = run_niche_research_skill("reposteria_artesanal", label="Repostería artesanal")

        assert result["brief"] == "Brief en cache"
        assert result["fresh"] is True
        assert result["regenerated"] is False
        mock_search.assert_not_called()


def test_run_niche_research_skill_regenerates_when_expired():
    with patch("services.hermes.skills.get_niche_insight") as mock_get_insight,          patch("services.hermes.skills._run_search_grounding") as mock_search,          patch("services.hermes.skills.save_niche_insight") as mock_save:

        mock_get_insight.return_value = {
            "brief": "Viejo brief",
            "expires_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
        }
        mock_search.return_value = {
            "brief": "Nuevo brief de búsqueda",
            "sources": [{"title": "Web", "uri": "https://example.com"}],
        }

        result = run_niche_research_skill("reposteria_artesanal", label="Repostería artesanal")

        assert result["brief"] == "Nuevo brief de búsqueda"
        assert result["regenerated"] is True
        mock_save.assert_called_once_with(
            "reposteria_artesanal",
            "Nuevo brief de búsqueda",
            [{"title": "Web", "uri": "https://example.com"}],
        )


def test_run_niche_research_skill_handles_search_error_gracefully():
    with patch("services.hermes.skills.get_niche_insight", return_value=None),          patch("services.hermes.skills._run_search_grounding", side_effect=Exception("search error")):

        result = run_niche_research_skill("nicho_x")

        assert result["regenerated"] is False
        assert "No pude completar" in result["brief"]
