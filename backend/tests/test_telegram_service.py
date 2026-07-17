# ABOUTME: Test suite for TelegramService functionalities including daily briefings.
# Auth: Antigravity CLI

import pytest
import os
from unittest.mock import patch, MagicMock
from datetime import date, datetime, timezone
from services.telegram_service import TelegramService

# Set dummy env vars for testing
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "mock-bot-token")
os.environ.setdefault("TELEGRAM_WEBHOOK_URL", "https://mock.webhook.url")

@pytest.fixture
def mock_service_supabase():
    with patch("services.telegram_service.get_supabase_admin_client") as mock_get_sup:
        mock_sup = MagicMock()
        mock_get_sup.return_value = mock_sup
        yield mock_sup

@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
async def test_send_daily_briefing_no_posts(mock_post_client, mock_service_supabase):
    # Mock empty select response
    mock_select = MagicMock()
    mock_select.execute.return_value = MagicMock(data=[])
    
    mock_service_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.gte.return_value.lte.return_value.order.return_value = mock_select
    
    # Mock HTTP response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"ok": True}
    mock_post_client.return_value = mock_response

    service = TelegramService()
    await service.send_daily_briefing(account_id=123, chat_id="chat-999")

    # Assert sendMessage was called once
    args, kwargs = mock_post_client.call_args
    assert "sendMessage" in args[0]
    payload = kwargs["json"]
    assert payload["chat_id"] == "chat-999"
    assert "Sin publicaciones programadas" in payload["text"]


@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
async def test_send_daily_briefing_with_posts(mock_post_client, mock_service_supabase):
    today_str = date.today().isoformat()
    mock_posts = [
        {
            "id": 10,
            "content": "Contenido del post programado para la mañana",
            "post_type": "post",
            "scheduled_at": f"{today_str}T09:30:00+00:00"
        },
        {
            "id": 11,
            "content": "Reel de la tarde",
            "post_type": "reel",
            "scheduled_at": f"{today_str}T18:45:00Z"
        }
    ]

    # Mock select response with posts
    mock_select = MagicMock()
    mock_select.execute.return_value = MagicMock(data=mock_posts)
    
    mock_service_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.gte.return_value.lte.return_value.order.return_value = mock_select
    
    # Mock HTTP response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"ok": True}
    mock_post_client.return_value = mock_response

    service = TelegramService()
    await service.send_daily_briefing(account_id=123, chat_id="chat-999")

    # Assert sendMessage was called once
    args, kwargs = mock_post_client.call_args
    assert "sendMessage" in args[0]
    payload = kwargs["json"]
    assert payload["chat_id"] == "chat-999"
    assert f"Publicaciones de hoy ({today_str})" in payload["text"]
    assert "09:30" in payload["text"]
    assert "18:45" in payload["text"]
    assert "[post]" in payload["text"]
    assert "[reel]" in payload["text"]
    assert "Contenido del post" in payload["text"]
    assert "Reel de la tarde" in payload["text"]
