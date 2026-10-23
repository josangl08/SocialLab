"""Contexto de rendimiento del borrador mensual (AD-6)."""
from unittest.mock import MagicMock, patch

from services.hermes import monthly_strategy
from services.hermes.prompts import get_monthly_strategy_prompt


def _prompt(**context) -> str:
    with patch("services.hermes.prompts.get_supabase_admin_client") as mock_get_client, \
            patch("services.hermes.prompts.get_active_brand_rules", return_value=[]):
        mock_get_client.return_value.table.return_value.select.return_value.eq.return_value.execute.return_value = (
            MagicMock(data=[{"id": 7}])
        )
        return get_monthly_strategy_prompt(7, "2026-11-01", **context)


def test_prompt_with_all_sources():
    prompt = _prompt(niche_brief="Reels cortos", outliers_summary="- \"Hook\"", audit_summary="- Bio sin CTA")
    assert "Tendencias del nicho:\nReels cortos" in prompt
    assert "Publicaciones que más destacaron el último mes:" in prompt
    assert "Puntos pendientes de la auditoría del perfil:\n- Bio sin CTA" in prompt


def test_prompt_without_sources_has_no_empty_blocks():
    prompt = _prompt()
    assert "Contexto de rendimiento" not in prompt
    assert "Tendencias del nicho" not in prompt


def test_gather_context_survives_failing_source():
    with patch.object(monthly_strategy, "run_niche_research_for_account", side_effect=RuntimeError("boom")), \
            patch.object(monthly_strategy, "_monthly_outliers_summary", return_value="- \"Hook\" (x, 3.2x la mediana)"), \
            patch.object(monthly_strategy, "_monthly_audit_summary", return_value=""):
        context = monthly_strategy._gather_monthly_context(7)
    assert context == {
        "niche_brief": None,
        "outliers_summary": "- \"Hook\" (x, 3.2x la mediana)",
        "audit_summary": None,
    }


def test_outliers_summary_top5_with_multiple():
    items = [{"hook_text": f"Hook {i}", "formula_name": "Curiosidad", "outlier_multiple": 5 - i} for i in range(6)]
    items.append({"hook_text": "Sin datos", "formula_name": None, "outlier_multiple": None})
    with patch.object(monthly_strategy, "get_supabase_admin_client"), \
            patch.object(monthly_strategy, "AnalyticsService") as mock_service:
        mock_service.return_value.get_swipe_file.return_value = {"items": items}
        summary = monthly_strategy._monthly_outliers_summary(7)
        mock_service.return_value.get_swipe_file.assert_called_once_with(7, days=30)
    assert summary.count("\n") == 4
    assert "Hook 0" in summary and "Hook 5" not in summary and "Sin datos" not in summary


def test_audit_summary_lists_failed_items_only():
    with patch.object(monthly_strategy, "get_supabase_admin_client") as mock_get_client, \
            patch.object(monthly_strategy, "audit_profile", return_value={"score": 50, "items": [
                {"label": "Bio con CTA", "weight": 10, "tip": "Añade un CTA", "passed": False},
                {"label": "Foto", "weight": 5, "tip": "x", "passed": True},
            ]}):
        mock_get_client.return_value.table.return_value.select.return_value.eq.return_value.execute.return_value = (
            MagicMock(data=[{"id": 7}])
        )
        summary = monthly_strategy._monthly_audit_summary(7)
    assert summary == "- Bio con CTA (peso 10): Añade un CTA"
