import pytest
from unittest.mock import patch, MagicMock

from services.hermes.prompts import get_system_prompt, get_monthly_strategy_prompt


def test_get_system_prompt_professional_voice_includes_hooks_and_hashtags():
    with patch("services.hermes.prompts.get_supabase_admin_client") as mock_get_client,          patch("services.hermes.prompts.get_active_brand_rules", return_value=[]):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{
                "id": 1,
                "caption_voice": "professional",
                "default_tone": "professional",
                "sector": "Marketing",
                "purpose": "Leads",
            }]
        )

        prompt = get_system_prompt(1)

        # Incluye hooks (arquetipos de gancho)
        assert "Arquetipos de Gancho" in prompt or "Dato / Estadística" in prompt or "abre con un gancho" in prompt
        # Incluye hashtag layering
        assert "Estrategia de Hashtags por Capas" in prompt or "Capa 1" in prompt or "Capa 2" in prompt


def test_get_system_prompt_personal_voice_includes_soft_hook_and_hashtags():
    with patch("services.hermes.prompts.get_supabase_admin_client") as mock_get_client,          patch("services.hermes.prompts.get_active_brand_rules", return_value=[]):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{
                "id": 2,
                "caption_voice": "personal",
                "default_tone": "energetic",
                "sector": "Deportes",
                "purpose": "Comunidad",
            }]
        )

        prompt = get_system_prompt(2)

        # Incluye línea suave de ganchos
        assert "cuando el caption pase de una frase" in prompt or "gancho" in prompt
        # Incluye hashtag layering
        assert "Estrategia de Hashtags por Capas" in prompt or "Capa 1" in prompt or "Capa 2" in prompt


def test_get_system_prompt_niche_and_visual_kwargs_presence():
    with patch("services.hermes.prompts.get_supabase_admin_client") as mock_get_client,          patch("services.hermes.prompts.get_active_brand_rules", return_value=[]):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": 3, "caption_voice": "personal"}]
        )

        # Sin kwargs -> no debe contener el bloque
        prompt_without = get_system_prompt(3)
        assert "Tendencias del nicho:" not in prompt_without
        assert "Rendimiento de contenido visual histórico:" not in prompt_without

        # Con kwargs -> debe contener el bloque
        niche_brief = "Tendencias: reels de 7 segundos funcionan mejor."
        visual_summary = "Las fotos de primeros planos rinden +40%."
        prompt_with = get_system_prompt(3, niche_brief=niche_brief, visual_perf_summary=visual_summary)

        assert "Tendencias: reels de 7 segundos funcionan mejor." in prompt_with
        assert "Las fotos de primeros planos rinden +40%." in prompt_with


def test_get_monthly_strategy_prompt_mentions_progression_and_storyline():
    with patch("services.hermes.prompts.get_supabase_admin_client") as mock_get_client,          patch("services.hermes.prompts.get_active_brand_rules", return_value=[]):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": 4, "caption_voice": "professional"}]
        )

        prompt = get_monthly_strategy_prompt(4, "2026-10-01")

        # Menciona progresión / matriz de contenido
        assert "Matriz de Contenidos" in prompt or "Semana 1" in prompt or "guía adaptable" in prompt
        # Menciona personal_storyline
        assert "personal_storyline" in prompt
        assert "arco narrativo" in prompt
        # Referencia campañas pendientes
        assert "include_pending" in prompt


def test_get_system_prompt_instructs_include_pending_campaign():
    with patch("services.hermes.prompts.get_supabase_admin_client") as mock_get_client, \
            patch("services.hermes.prompts.get_active_brand_rules", return_value=[]):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": 1, "caption_voice": "professional"}]
        )
        prompt = get_system_prompt(1)
        assert "include_pending=True" in prompt
