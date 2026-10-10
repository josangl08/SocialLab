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

        # Incluye hooks (26 fórmulas, priorizando las del modo comercial)
        assert "Fórmulas de Gancho" in prompt
        assert "priorizando las del modo commercial_campaign" in prompt
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

        # Si pasa de una frase, abre con fórmula de curiosidad/anécdota (caption-craft)
        assert "Cuando el caption pase de una frase, abre con una fórmula de curiosidad o anécdota" in prompt
        assert "Fórmulas de Gancho" in prompt
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


def test_hashtag_range_remapped_ad7b():
    with patch("services.hermes.prompts.get_supabase_admin_client") as mock_get_client, \
            patch("services.hermes.prompts.get_active_brand_rules", return_value=[]):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # 1) Minimal: 1-2
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": 10, "caption_voice": "professional", "hashtag_strategy": "minimal"}]
        )
        prompt_min = get_system_prompt(10)
        assert "1-2 hashtags" in prompt_min
        assert "1-3" not in prompt_min

        # 2) Moderate: 3-4
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": 11, "caption_voice": "professional", "hashtag_strategy": "moderate"}]
        )
        prompt_mod = get_system_prompt(11)
        assert "3-4 hashtags" in prompt_mod
        assert "4-7" not in prompt_mod

        # 3) Maximum: exactamente 5 (nunca más de 5 por recomendación de Meta)
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": 12, "caption_voice": "professional", "hashtag_strategy": "maximum"}]
        )
        prompt_max = get_system_prompt(12)
        assert "5 hashtags" in prompt_max
        assert "8-12" not in prompt_max


def test_get_system_prompt_lists_account_banned_phrases():
    with patch("services.hermes.prompts.get_supabase_admin_client") as mock_get_client, \
            patch("services.hermes.prompts.get_active_brand_rules", return_value=[]):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": 13, "caption_voice": "personal", "banned_phrases": ["sinergia", "compra ya"]}]
        )
        prompt = get_system_prompt(13)
        assert "Términos vetados por la cuenta (no los uses nunca): sinergia, compra ya." in prompt

        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": 14, "caption_voice": "personal", "banned_phrases": []}]
        )
        prompt_empty = get_system_prompt(14)
        assert "Términos vetados" not in prompt_empty


def test_get_system_prompt_anti_slop_and_125_chars():
    with patch("services.hermes.prompts.get_supabase_admin_client") as mock_get_client, \
            patch("services.hermes.prompts.get_active_brand_rules", return_value=[]):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": 1, "caption_voice": "professional"}]
        )

        prompt = get_system_prompt(1)
        prompt_lower = prompt.lower()

        # Instrucciones anti-slop
        assert ("anti-slop" in prompt_lower or
                "slop" in prompt_lower or
                "lenguaje sintético" in prompt_lower or
                "game-changer" in prompt_lower or
                "delve into" in prompt_lower)

        # Corte móvil 125 chars
        assert "125" in prompt

        # Límite máximo de 5 hashtags
        assert "5 hashtags" in prompt_lower or "≤ 5" in prompt or "<= 5" in prompt


def test_get_system_prompt_instructs_matrix_role_and_hook_candidates_for_reels():
    with patch("services.hermes.prompts.get_supabase_admin_client") as mock_get_client, \
            patch("services.hermes.prompts.get_active_brand_rules", return_value=[]):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": 1, "caption_voice": "professional"}]
        )

        prompt = get_system_prompt(1)

        # Instrucción de pedir matrix_role en los slots
        assert "matrix_role" in prompt

        # Instrucción de pedir 3 hook_candidates para Reels
        assert "hook_candidates" in prompt
        assert "3" in prompt


def test_get_system_prompt_includes_carousel_structure():
    with patch("services.hermes.prompts.get_supabase_admin_client") as mock_get_client, \
            patch("services.hermes.prompts.get_active_brand_rules", return_value=[]):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": 1, "caption_voice": "professional"}]
        )

        prompt = get_system_prompt(1)
        prompt_lower = prompt.lower()

        # Estructura de carrusel requerida en Fase D (portada ≤ 6 palabras, ideas ≤ 25, recap, CTA)
        assert "carrusel" in prompt_lower or "carousel" in prompt_lower
        assert "portada" in prompt_lower or "cover" in prompt_lower

