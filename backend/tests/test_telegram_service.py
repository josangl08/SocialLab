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
    # Cuenta sin zonas → UTC
    mock_service_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    
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
    # Cuenta sin zonas → UTC
    mock_service_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    
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


# --- Vista previa de imágenes en la tarjeta de propuesta ---

def _jpeg_bytes(width: int, height: int) -> bytes:
    import io
    from PIL import Image
    out = io.BytesIO()
    Image.new("RGB", (width, height), (120, 80, 40)).save(out, format="JPEG", quality=95)
    return out.getvalue()


def test_prepare_telegram_photo_downscales_large_image():
    import io
    from PIL import Image
    original = _jpeg_bytes(8000, 2400)  # ancho + alto > 10000: sendPhoto lo rechaza

    result = TelegramService._prepare_telegram_photo(original)

    with Image.open(io.BytesIO(result)) as img:
        assert img.format == "JPEG"
        assert max(img.size) == 2560
        assert sum(img.size) <= 10000
    assert len(result) < 10 * 1024 * 1024


def test_prepare_telegram_photo_unreadable_returns_none():
    assert TelegramService._prepare_telegram_photo(b"not an image") is None


@pytest.mark.asyncio
@patch("httpx.AsyncClient.post", new_callable=AsyncMock)
async def test_proposal_card_sends_reduced_copy_and_keeps_original(mock_post, mock_service_supabase):
    import io
    from PIL import Image
    original = _jpeg_bytes(8000, 2400)
    mock_post.return_value = MagicMock(status_code=200, json=MagicMock(return_value={"result": {"message_id": 1}}))
    slots = [{"day": "Thursday", "theme": "Dron", "caption": "Caption", "image_id": "drive-1", "post_type": "post"}]
    service = TelegramService()

    with patch.object(service, "_download_drive_image", new=AsyncMock(return_value=original)):
        await service.send_proposal_card("chat-1", "prop-1", slots, user_id="user-1")

    photo_calls = [c for c in mock_post.call_args_list if "sendPhoto" in c.args[0]]
    assert len(photo_calls) == 1
    sent_bytes = photo_calls[0].kwargs["files"]["photo"][1]
    with Image.open(io.BytesIO(sent_bytes)) as img:
        assert max(img.size) == 2560
    assert slots[0]["image_id"] == "drive-1"  # el slot sigue apuntando al original de Drive
    mock_service_supabase.table.return_value.update.assert_called_once_with({"telegram_message_id": "1"})


@pytest.mark.asyncio
@patch("httpx.AsyncClient.post", new_callable=AsyncMock)
async def test_proposal_card_falls_back_to_text_when_telegram_rejects_photo(mock_post, mock_service_supabase):
    ok = MagicMock(status_code=200, json=MagicMock(return_value={"result": {"message_id": 1}}))
    rejected = MagicMock(status_code=400, text='{"ok":false,"description":"PHOTO_INVALID_DIMENSIONS"}')
    mock_post.side_effect = lambda url, **kw: rejected if "sendPhoto" in url else ok
    slots = [{"day": "Thursday", "theme": "Dron", "caption": "Caption", "image_id": "drive-1", "post_type": "post"}]
    service = TelegramService()

    with patch.object(service, "_download_drive_image", new=AsyncMock(return_value=_jpeg_bytes(100, 100))):
        await service.send_proposal_card("chat-1", "prop-1", slots, user_id="user-1")

    urls = [c.args[0] for c in mock_post.call_args_list]
    assert sum("sendPhoto" in u for u in urls) == 1
    assert sum("sendMessage" in u for u in urls) == 2  # cabecera + slot en texto


# --- Adjuntar foto a un slot de la propuesta ---

PROPOSAL_UUID = "4ab20cfc-18f0-4e06-84bc-886fd9d0647c"


def _swap_message(**extra):
    from models.schemas import TelegramMessage
    return TelegramMessage(**{
        "message_id": 2, "chat": {"id": 555, "type": "private"}, "date": 0,
        "reply_to_message": {
            "message_id": 1, "chat": {"id": 555, "type": "private"}, "date": 0,
            "text": f"📸 Responde con la nueva foto\n#slot_swap_{PROPOSAL_UUID}_0",
        },
        **extra,
    })


@pytest.mark.asyncio
@patch("httpx.AsyncClient.post", new_callable=AsyncMock)
async def test_proposal_card_has_attach_photo_button(mock_post, mock_service_supabase):
    mock_post.return_value = MagicMock(status_code=200, json=MagicMock(return_value={"result": {}}))
    slots = [{"day": "Thursday", "theme": "t", "caption": "c", "image_id": None, "post_type": "post"}]

    await TelegramService().send_proposal_card("chat-1", PROPOSAL_UUID, slots)

    slot_call = mock_post.call_args_list[-1]
    buttons = [b["callback_data"] for row in slot_call.kwargs["json"]["reply_markup"]["inline_keyboard"] for b in row]
    assert f"slot:{PROPOSAL_UUID}:0:swap" in buttons


@pytest.mark.asyncio
@pytest.mark.parametrize("extra, expected", [
    ({"photo": [{"file_id": "small", "file_unique_id": "s", "width": 90, "height": 90, "file_size": 10},
                {"file_id": "big", "file_unique_id": "b", "width": 1280, "height": 960, "file_size": 900}]},
     ("big", "image/jpeg", True)),
    ({"document": {"file_id": "doc-1", "file_unique_id": "d", "file_name": "IMG.HEIC", "mime_type": "image/heic"}},
     ("doc-1", "image/heic", False)),
])
async def test_swap_reply_with_uuid_proposal_routes_attachment(extra, expected):
    service = TelegramService()
    with patch.object(service, "_verify_proposal_owner", new=AsyncMock(return_value=True)), \
         patch.object(service, "_handle_photo_swap_reply", new=AsyncMock()) as swap:
        await service.handle_message(_swap_message(**extra))

    swap.assert_awaited_once_with("555", PROPOSAL_UUID, 0, *expected)


@pytest.mark.asyncio
async def test_swap_reply_ignores_non_image_document():
    service = TelegramService()
    msg = _swap_message(document={"file_id": "pdf", "file_unique_id": "p", "mime_type": "application/pdf"})
    with patch.object(service, "_verify_proposal_owner", new=AsyncMock(return_value=True)), \
         patch.object(service, "_handle_photo_swap_reply", new=AsyncMock()) as swap:
        await service.handle_message(msg)

    swap.assert_not_called()


@pytest.mark.asyncio
async def test_photo_swap_stores_attachment_and_replaces_drive_image(mock_service_supabase):
    proposal = {"id": PROPOSAL_UUID, "slots": [{"day": "Thursday", "post_id": 53577, "image_id": "drive-1"}]}
    mock_service_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[proposal])
    storage = mock_service_supabase.storage.from_.return_value
    storage.get_public_url.return_value = "https://storage.test/telegram/x.jpg"
    import io
    from PIL import Image
    buf = io.BytesIO(); Image.new("RGB", (40, 30)).save(buf, format="HEIF"); heic = buf.getvalue()

    get_file = MagicMock(status_code=200, json=MagicMock(return_value={"result": {"file_path": "documents/file_1.heic"}}))
    download = MagicMock(status_code=200, content=heic)
    with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=[get_file, download])), \
         patch("httpx.AsyncClient.post", new=AsyncMock()) as mock_post:
        await TelegramService()._handle_photo_swap_reply("555", PROPOSAL_UUID, 0, "doc-1", "image/heic")

    path, data, options = storage.upload.call_args.args
    assert path == f"telegram/{PROPOSAL_UUID}_0.jpg"
    assert options == {"content-type": "image/jpeg", "upsert": "true"}
    assert Image.open(io.BytesIO(data)).format == "JPEG"  # HEIC → JPEG para Instagram
    mock_service_supabase.table.return_value.update.assert_any_call(
        {"media_url": "https://storage.test/telegram/x.jpg", "drive_file_id": None}
    )
    mock_service_supabase.table.return_value.update.assert_any_call(
        {"slots": [{"day": "Thursday", "post_id": 53577, "image_id": None, "media_url": "https://storage.test/telegram/x.jpg"}]}
    )
    assert "actualizada" in mock_post.call_args.kwargs["json"]["text"]


@pytest.mark.asyncio
async def test_photo_swap_too_big_for_bot_api_tells_user(mock_service_supabase):
    proposal = {"id": PROPOSAL_UUID, "slots": [{"day": "Thursday", "post_id": 53577, "image_id": "drive-1"}]}
    mock_service_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[proposal])
    too_big = MagicMock(status_code=400, json=MagicMock(return_value={"ok": False, "description": "file is too big"}))

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=too_big)), \
         patch("httpx.AsyncClient.post", new=AsyncMock()) as mock_post:
        await TelegramService()._handle_photo_swap_reply("555", PROPOSAL_UUID, 0, "doc-1", "image/jpeg")

    mock_service_supabase.storage.from_.return_value.upload.assert_not_called()
    mock_service_supabase.table.return_value.update.assert_not_called()
    assert "20 MB" in mock_post.call_args.kwargs["json"]["text"]


# --- Recorte para el feed ---

def _slot(post_type="post"):
    return [{"day": "Thursday", "theme": "t", "caption": "c", "image_id": "drive-1", "post_type": post_type}]


@pytest.mark.asyncio
@patch("httpx.AsyncClient.post", new_callable=AsyncMock)
async def test_proposal_card_sends_original_and_asks_crop_for_vertical_feed_photo(mock_post, mock_service_supabase):
    mock_post.return_value = MagicMock(status_code=200, json=MagicMock(return_value={"result": {}}))
    original = _jpeg_bytes(3024, 4032)
    service = TelegramService()

    with patch.object(service, "_download_drive_image", new=AsyncMock(return_value=original)):
        await service.send_proposal_card("chat-1", PROPOSAL_UUID, _slot("post"), user_id="user-1")

    doc_calls = [c for c in mock_post.call_args_list if "sendDocument" in c.args[0]]
    assert len(doc_calls) == 1
    caption = doc_calls[0].kwargs["data"]["caption"]
    assert "4:5" in caption and "3024x3780" in caption
    assert f"#slot_swap_{PROPOSAL_UUID}_0" in caption
    assert doc_calls[0].kwargs["files"]["document"][1] is original  # el original, sin tocar


@pytest.mark.asyncio
@pytest.mark.parametrize("post_type, size", [("reel", (3024, 4032)), ("story", (3024, 4032)), ("post", (4032, 3024))])
@patch("httpx.AsyncClient.post", new_callable=AsyncMock)
async def test_proposal_card_no_crop_request_when_not_needed(mock_post, post_type, size, mock_service_supabase):
    mock_post.return_value = MagicMock(status_code=200, json=MagicMock(return_value={"result": {}}))
    service = TelegramService()

    with patch.object(service, "_download_drive_image", new=AsyncMock(return_value=_jpeg_bytes(*size))):
        await service.send_proposal_card("chat-1", PROPOSAL_UUID, _slot(post_type), user_id="user-1")

    assert not any("sendDocument" in c.args[0] for c in mock_post.call_args_list)


@pytest.mark.asyncio
async def test_reply_to_crop_request_document_caption_is_routed():
    from models.schemas import TelegramMessage
    msg = TelegramMessage(**{
        "message_id": 3, "chat": {"id": 555, "type": "private"}, "date": 0,
        "document": {"file_id": "crop-1", "file_unique_id": "c", "mime_type": "image/jpeg"},
        "reply_to_message": {"message_id": 2, "chat": {"id": 555, "type": "private"}, "date": 0,
                             "caption": f"✂️ Recórtala a 4:5\n#slot_swap_{PROPOSAL_UUID}_0"},
    })
    service = TelegramService()
    with patch.object(service, "_verify_proposal_owner", new=AsyncMock(return_value=True)), \
         patch.object(service, "_handle_photo_swap_reply", new=AsyncMock()) as swap:
        await service.handle_message(msg)

    swap.assert_awaited_once_with("555", PROPOSAL_UUID, 0, "crop-1", "image/jpeg", False)


@pytest.mark.asyncio
async def test_photo_swap_with_wrong_ratio_asks_crop_again(mock_service_supabase):
    proposal = {"id": PROPOSAL_UUID, "slots": [{"day": "Thursday", "post_id": 53577, "image_id": "drive-1", "post_type": "post"}]}
    mock_service_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[proposal])
    get_file = MagicMock(status_code=200, json=MagicMock(return_value={"result": {"file_path": "documents/f.jpg"}}))
    download = MagicMock(status_code=200, content=_jpeg_bytes(300, 400))

    with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=[get_file, download])), \
         patch("httpx.AsyncClient.post", new=AsyncMock()) as mock_post:
        await TelegramService()._handle_photo_swap_reply("555", PROPOSAL_UUID, 0, "doc-1", "image/jpeg")

    mock_service_supabase.storage.from_.return_value.upload.assert_not_called()
    mock_service_supabase.table.return_value.update.assert_not_called()
    text = mock_post.call_args.kwargs["json"]["text"]
    assert "4:5" in text and "300x375" in text and f"#slot_swap_{PROPOSAL_UUID}_0" in text


@pytest.mark.asyncio
async def test_photo_swap_compressed_photo_warns_about_resolution(mock_service_supabase):
    proposal = {"id": PROPOSAL_UUID, "slots": [{"day": "Thursday", "post_id": 53577, "image_id": "drive-1", "post_type": "post"}]}
    mock_service_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[proposal])
    mock_service_supabase.storage.from_.return_value.get_public_url.return_value = "https://storage.test/x.jpg"
    get_file = MagicMock(status_code=200, json=MagicMock(return_value={"result": {"file_path": "photos/f.jpg"}}))
    download = MagicMock(status_code=200, content=_jpeg_bytes(1280, 1024))

    with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=[get_file, download])), \
         patch("httpx.AsyncClient.post", new=AsyncMock()) as mock_post:
        await TelegramService()._handle_photo_swap_reply("555", PROPOSAL_UUID, 0, "ph-1", "image/jpeg", True)

    mock_service_supabase.storage.from_.return_value.upload.assert_called_once()
    assert "1280x1024" in mock_post.call_args.kwargs["json"]["text"]


@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
async def test_send_daily_briefing_formats_in_account_timezone(mock_post_client, mock_service_supabase):
    # Mock account con primary_timezone y secondary_timezone
    mock_acc_exec = MagicMock()
    mock_acc_exec.execute.return_value = MagicMock(data=[{
        "id": 123,
        "primary_timezone": "Europe/Madrid",
        "secondary_timezone": "Asia/Kuching",
    }])

    # Post a las 18:00 UTC (20:00 en Madrid CEST, 02:00 en Kuching el día siguiente)
    mock_posts_exec = MagicMock()
    mock_posts_exec.execute.return_value = MagicMock(data=[{
        "id": 53946,
        "content": "Publicación de la tarde",
        "post_type": "post",
        "scheduled_at": "2026-10-14T18:00:00Z",
    }])

    def table_router(name):
        t = MagicMock()
        if name == "instagram_accounts":
            t.select.return_value.eq.return_value = mock_acc_exec
        elif name == "posts":
            t.select.return_value.eq.return_value.eq.return_value.gte.return_value.lte.return_value.order.return_value = mock_posts_exec
        return t

    mock_service_supabase.table.side_effect = table_router

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"ok": True}
    mock_post_client.return_value = mock_response

    service = TelegramService()
    await service.send_daily_briefing(account_id=123, chat_id="chat-999")

    args, kwargs = mock_post_client.call_args
    text = kwargs["json"]["text"]
    # AD-12: hora en la zona efectiva (20:00 Madrid) y equivalencia en la secundaria
    assert "20:00" in text
    assert "(02:00 Kuching)" in text

