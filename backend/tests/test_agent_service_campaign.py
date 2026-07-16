from datetime import date
from unittest.mock import patch, MagicMock
from services.agent_service import (
    _build_campaign_context,
    _build_strategy_context,
    _ai_schedule,
)
from models.schemas import VisualAnalysis


# ── _build_campaign_context ────────────────────────────────────────────────

def test_build_campaign_context_no_campaign_returns_empty():
    assert _build_campaign_context(None, date(2026, 7, 6)) == ''


def test_build_campaign_context_no_focus_no_milestone_returns_empty():
    campaign = {
        'strategy_mode': 'commercial_campaign',
        'title': 'Colección de Verano',
        'weekly_focus': {'1': '', '2': 'Ofertas'},
        'milestones': [],
    }
    # week_start day 6 -> week_of_month 1, whose focus is empty, no milestones
    assert _build_campaign_context(campaign, date(2026, 7, 6)) == ''


def test_build_campaign_context_commercial_includes_weekly_focus():
    campaign = {
        'strategy_mode': 'commercial_campaign',
        'title': 'Colección de Verano',
        'weekly_focus': {'1': 'Awareness', '2': 'Conversión'},
        'milestones': [],
    }
    context = _build_campaign_context(campaign, date(2026, 7, 13))  # day 13 -> week 2
    assert 'Colección de Verano' in context
    assert 'Conversión' in context


def test_build_campaign_context_personal_storyline_framing():
    campaign = {
        'strategy_mode': 'personal_storyline',
        'title': 'Viaje a Japón',
        'weekly_focus': {'1': 'Preparativos', '2': 'Aventuras en Tokio'},
        'milestones': [],
    }
    context = _build_campaign_context(campaign, date(2026, 7, 6))  # week 1
    assert 'Viaje a Japón' in context
    assert 'Preparativos' in context
    assert 'primera persona' in context.lower()


def test_build_campaign_context_includes_milestone_in_range():
    campaign = {
        'strategy_mode': 'personal_storyline',
        'title': 'Viaje a Japón',
        'weekly_focus': {'3': 'Gastronomía'},
        'milestones': [{'date': '2026-07-16', 'event': 'Llegada a Tokio'}],
    }
    # week_start Monday 2026-07-13 (week 2 of month) covers 2026-07-13..2026-07-19
    context = _build_campaign_context(campaign, date(2026, 7, 13))
    assert 'Llegada a Tokio' in context
    assert '2026-07-16' in context


def test_build_campaign_context_excludes_milestone_out_of_range():
    campaign = {
        'strategy_mode': 'personal_storyline',
        'title': 'Viaje a Japón',
        'weekly_focus': {'2': 'Aventuras en Tokio'},
        'milestones': [{'date': '2026-07-30', 'event': 'Vuelta a casa'}],
    }
    context = _build_campaign_context(campaign, date(2026, 7, 13))
    assert 'Vuelta a casa' not in context
    assert 'Aventuras en Tokio' in context


def test_build_campaign_context_caps_week_of_month_at_four():
    campaign = {
        'strategy_mode': 'commercial_campaign',
        'title': 'Rebajas',
        'weekly_focus': {'4': 'Cierre'},
        'milestones': [],
    }
    # day 29 -> ((29-1)//7)+1 = 5, capped to 4
    context = _build_campaign_context(campaign, date(2026, 7, 29))
    assert 'Cierre' in context


# ── Threading into _build_strategy_context ─────────────────────────────────

def test_build_strategy_context_unchanged_without_campaign():
    account = {'account_type': 'personal', 'default_tone': 'energetic'}
    assert _build_strategy_context(account) == _build_strategy_context(account, '')


def test_build_strategy_context_appends_campaign_context():
    account = {'account_type': 'professional', 'default_tone': 'professional'}
    base = _build_strategy_context(account)
    with_campaign = _build_strategy_context(account, "ENFOQUE DE CAMPAÑA DEL MES: 'Lanzamiento X'.")
    assert with_campaign.startswith(base)
    assert 'Lanzamiento X' in with_campaign


# ── Threading into _ai_schedule prompt ──────────────────────────────────────

@patch("google.generativeai.GenerativeModel")
@patch("os.getenv")
def test_ai_schedule_includes_campaign_context_in_prompt(mock_getenv, mock_gen_model):
    mock_getenv.return_value = "fake-api-key"
    mock_model_instance = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '{"slots": [{"day": "Tuesday", "image_index": 0, "post_type": "reel"}]}'
    mock_model_instance.generate_content.return_value = mock_response
    mock_gen_model.return_value = mock_model_instance

    analyses = [VisualAnalysis(drive_file_id="file-1", gemini_description={"theme": "sport"}, suggested_caption="caption")]
    account = {'account_type': 'personal', 'posting_frequency': 'few_times_week'}

    _ai_schedule(analyses, account, 1, 3, campaign_context="Foco de esta semana: Aventuras en Tokio.")

    sent_prompt = mock_model_instance.generate_content.call_args[0][0]
    assert 'Aventuras en Tokio' in sent_prompt
