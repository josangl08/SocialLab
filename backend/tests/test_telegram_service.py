# ABOUTME: Test suite for TelegramService functionalities including daily briefings.
# Auth: Antigravity CLI

import pytest
import os
from unittest.mock import patch, MagicMock, AsyncMock
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


def _mock_response(message_id: int = 555):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"result": {"message_id": message_id}}
    return resp


@pytest.mark.asyncio
@patch("services.telegram_service.run_edit_session", new_callable=AsyncMock)
@patch("httpx.AsyncClient.post", new_callable=AsyncMock)
async def test_run_edit_session_with_progress_sends_placeholder_and_edits(mock_post, mock_run_edit):
    from services.hermes.orchestrator import EditSessionResult

    async def fake_run_edit_session(**kwargs):
        import asyncio
        on_progress = kwargs["on_progress"]
        await on_progress({"type": "tool_call", "tool": "drive_list_files"})
        # Real gap so the debounce (~700ms) doesn't swallow the tool_result edit —
        # in production a real tool call always takes some time between the two events.
        await asyncio.sleep(0.75)
        await on_progress({"type": "tool_result", "tool": "drive_list_files", "ok": True})
        return EditSessionResult(resolved=True, message="Listo")

    mock_run_edit.side_effect = fake_run_edit_session
    mock_post.return_value = _mock_response()

    service = TelegramService()
    result = await service._run_edit_session_with_progress(
        chat_id="999", account_id=7, edit_type="IMAGE_SELECT",
        context={"proposal_id": "p1", "slot_index": 0}, user_message="la segunda"
    )

    assert result.resolved is True

    calls = mock_post.call_args_list
    # First call is the placeholder sendMessage
    assert "sendMessage" in calls[0][0][0]
    assert calls[0][1]["json"]["text"] == "🤖 Procesando…"

    edit_calls = [c for c in calls if "editMessageText" in c[0][0]]
    assert any("Buscando imágenes en Drive…" in c[1]["json"]["text"] for c in edit_calls)
    assert any("Buscando imágenes en Drive" in c[1]["json"]["text"] and "✅" in c[1]["json"]["text"] for c in edit_calls)
    # Final collapse message
    assert edit_calls[-1][1]["json"]["text"] == "✅ Listo"
    assert all(c[1]["json"]["message_id"] == 555 for c in edit_calls)


@pytest.mark.asyncio
@patch("services.telegram_service.run_edit_session", new_callable=AsyncMock)
@patch("httpx.AsyncClient.post", new_callable=AsyncMock)
async def test_run_edit_session_with_progress_debounces_duplicate_text(mock_post, mock_run_edit):
    from services.hermes.orchestrator import EditSessionResult

    async def fake_run_edit_session(**kwargs):
        on_progress = kwargs["on_progress"]
        # Two tool_call events for the *same* tool produce identical accumulated
        # text ("🔎 Buscando imágenes en Drive…") — the second must be suppressed.
        await on_progress({"type": "tool_call", "tool": "drive_list_files"})
        await on_progress({"type": "tool_call", "tool": "drive_list_files"})
        return EditSessionResult(resolved=False, message="No se pudo completar")

    mock_run_edit.side_effect = fake_run_edit_session
    mock_post.return_value = _mock_response()

    service = TelegramService()
    await service._run_edit_session_with_progress(
        chat_id="999", account_id=7, edit_type="TIME",
        context={"proposal_id": "p1", "slot_index": 0}, user_message="mañana"
    )

    edit_calls = [c for c in mock_post.call_args_list if "editMessageText" in c[0][0]]
    progress_edits = [c for c in edit_calls if c[1]["json"]["text"] != "⚠️ No pude completarlo"]
    assert len(progress_edits) == 1


@pytest.mark.asyncio
@patch("services.telegram_service.run_edit_session", new_callable=AsyncMock)
@patch("httpx.AsyncClient.post", new_callable=AsyncMock)
async def test_run_edit_session_with_progress_skips_edits_if_placeholder_failed(mock_post, mock_run_edit):
    from services.hermes.orchestrator import EditSessionResult

    async def fake_run_edit_session(**kwargs):
        on_progress = kwargs["on_progress"]
        await on_progress({"type": "tool_call", "tool": "drive_list_files"})
        return EditSessionResult(resolved=True, message="Listo")

    mock_run_edit.side_effect = fake_run_edit_session
    failed_resp = MagicMock()
    failed_resp.status_code = 400
    mock_post.return_value = failed_resp

    service = TelegramService()
    result = await service._run_edit_session_with_progress(
        chat_id="999", account_id=7, edit_type="CAMPAIGN_CHAT",
        context={"campaign_id": "c1"}, user_message="ajusta esto"
    )

    assert result.resolved is True
    edit_calls = [c for c in mock_post.call_args_list if "editMessageText" in c[0][0]]
    assert edit_calls == []
