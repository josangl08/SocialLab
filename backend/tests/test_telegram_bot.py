import pytest
import os
import json
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from main import app
from auth.dependencies import get_current_user
from models.schemas import User
from tests.conftest import USER_ID
from services.telegram_service import TelegramService

# Set dummy env vars for testing
os.environ["TELEGRAM_BOT_TOKEN"] = "mock-bot-token"
os.environ["TELEGRAM_WEBHOOK_URL"] = "https://mock.webhook.url"

# Mock current user for testing routes
async def mock_get_current_user():
    return User(id=USER_ID, email="test@example.com")

app.dependency_overrides[get_current_user] = mock_get_current_user

client = TestClient(app)

@pytest.fixture
def mock_supabase():
    with patch("routes.telegram_routes.admin_supabase") as mock_sup:
        yield mock_sup

@pytest.fixture
def mock_service_supabase():
    with patch("services.telegram_service.get_supabase_admin_client") as mock_get_sup:
        mock_sup = MagicMock()
        mock_get_sup.return_value = mock_sup

        # Cache mock table instances
        mock_tables = {}

        def table_side_effect(table_name):
            if table_name in mock_tables:
                return mock_tables[table_name]

            mock_table = MagicMock()
            
            # Setup method chaining: table().select().eq().execute()
            mock_select = MagicMock()
            mock_table.select.return_value = mock_select
            
            mock_eq = MagicMock()
            mock_select.eq.return_value = mock_eq
            
            mock_in = MagicMock()
            mock_select.in_.return_value = mock_in
            
            mock_execute = MagicMock()
            
            # Allow update() chaining
            mock_update = MagicMock()
            mock_table.update.return_value = mock_update
            mock_update_eq = MagicMock()
            mock_update.eq.return_value = mock_update_eq
            mock_update_eq.execute.return_value = MagicMock(data=[])
            mock_update.execute.return_value = MagicMock(data=[])
            
            # Allow delete() chaining
            mock_delete = MagicMock()
            mock_table.delete.return_value = mock_delete
            mock_delete_eq = MagicMock()
            mock_table.delete.return_value.eq.return_value = mock_delete_eq
            mock_delete_eq.eq.return_value = mock_delete_eq
            mock_delete_eq.execute.return_value = MagicMock(data=[])

            # Return defaults based on table
            if table_name == 'posts':
                mock_execute.execute.return_value = MagicMock(data=[{
                    "id": 1,
                    "instagram_account_id": "mock-account-id",
                    "scheduled_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
                    "content": "Original text"
                }])
            elif table_name == 'content_proposals':
                mock_execute.execute.return_value = MagicMock(data=[{
                    "id": "mock-proposal-id",
                    "account_id": "mock-account-id",
                    "slots": []
                }])
            elif table_name == 'instagram_accounts':
                mock_execute.execute.return_value = MagicMock(data=[{
                    "id": "mock-account-id",
                    "telegram_chat_id": "999"
                }])
            else:
                mock_execute.execute.return_value = MagicMock(data=[])

            mock_eq.execute = mock_execute.execute
            mock_in.execute = mock_execute.execute
            mock_select.execute = mock_execute.execute
            
            mock_tables[table_name] = mock_table
            return mock_table

        mock_sup.table.side_effect = table_side_effect
        yield mock_sup


# ==============================================================================
# ROUTE TESTS
# ==============================================================================

def test_telegram_webhook_invalid_token():
    payload = {
        "update_id": 12345,
        "message": {
            "message_id": 1,
            "chat": {"id": 999, "type": "private"},
            "date": 1600000000,
            "text": "hello"
        }
    }
    response = client.post("/api/telegram/webhook/wrong-token", json=payload)
    assert response.status_code == 401
    assert response.json()["detail"] == "Unauthorized"


@patch.object(TelegramService, "handle_message", new_callable=AsyncMock)
def test_telegram_webhook_message(mock_handle_message):
    payload = {
        "update_id": 12345,
        "message": {
            "message_id": 1,
            "chat": {"id": 999, "type": "private"},
            "date": 1600000000,
            "text": "hello"
        }
    }
    response = client.post("/api/telegram/webhook/mock-bot-token", json=payload)
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    mock_handle_message.assert_called_once()


@patch.object(TelegramService, "handle_callback_query", new_callable=AsyncMock)
def test_telegram_webhook_callback(mock_handle_callback):
    payload = {
        "update_id": 12345,
        "callback_query": {
            "id": "cb123",
            "from": {"id": 999, "is_bot": False, "first_name": "Test"},
            "data": "approve:1"
        }
    }
    response = client.post("/api/telegram/webhook/mock-bot-token", json=payload)
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    mock_handle_callback.assert_called_once()


def test_generate_link_token_success(mock_supabase):
    # Mocking supabase behavior
    mock_select = MagicMock()
    mock_select.execute.return_value = MagicMock(data=[{"id": 42}])
    mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value = mock_select

    mock_update = MagicMock()
    mock_update.execute.return_value = MagicMock(data=[])
    mock_supabase.table.return_value.update.return_value.eq.return_value = mock_update

    response = client.post("/api/telegram/generate-link-token")
    assert response.status_code == 200
    res_data = response.json()
    assert "token" in res_data
    assert "expires_at" in res_data
    assert mock_supabase.table.call_count >= 2


def test_generate_link_token_no_accounts(mock_supabase):
    # Mock no accounts found
    mock_select = MagicMock()
    mock_select.execute.return_value = MagicMock(data=[])
    mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value = mock_select
    mock_supabase.table.return_value.select.return_value.eq.return_value.limit.return_value = mock_select

    response = client.post("/api/telegram/generate-link-token")
    assert response.status_code == 404
    assert "No se encontró ninguna cuenta de Instagram" in response.json()["detail"]


def test_link_account_success(mock_supabase):
    # Token valid for 10 minutes in the future
    future_expiry = (datetime.utcnow() + timedelta(minutes=5)).isoformat() + "Z"
    
    mock_select = MagicMock()
    mock_select.execute.return_value = MagicMock(data=[{"id": 42, "telegram_link_token_expires_at": future_expiry}])
    mock_supabase.table.return_value.select.return_value.eq.return_value = mock_select

    mock_update = MagicMock()
    mock_update.execute.return_value = MagicMock(data=[])
    mock_supabase.table.return_value.update.return_value.eq.return_value = mock_update

    response = client.post("/api/telegram/link-account", json={"link_token": "token-123", "telegram_chat_id": "chat-456"})
    assert response.status_code == 200
    assert response.json()["success"] is True

    # Check update clears token and sets telegram_chat_id
    mock_supabase.table.return_value.update.assert_called_once_with({
        "telegram_chat_id": "chat-456",
        "telegram_link_token": None,
        "telegram_link_token_expires_at": None
    })


def test_link_account_expired(mock_supabase):
    # Token expired 5 minutes ago
    past_expiry = (datetime.utcnow() - timedelta(minutes=5)).isoformat() + "Z"
    
    mock_select = MagicMock()
    mock_select.execute.return_value = MagicMock(data=[{"id": 42, "telegram_link_token_expires_at": past_expiry}])
    mock_supabase.table.return_value.select.return_value.eq.return_value = mock_select

    response = client.post("/api/telegram/link-account", json={"link_token": "token-123", "telegram_chat_id": "chat-456"})
    assert response.status_code == 400
    assert "ha expirado" in response.json()["detail"]


def test_link_account_invalid_token(mock_supabase):
    mock_select = MagicMock()
    mock_select.execute.return_value = MagicMock(data=[])
    mock_supabase.table.return_value.select.return_value.eq.return_value = mock_select

    response = client.post("/api/telegram/link-account", json={"link_token": "invalid-token", "telegram_chat_id": "chat-456"})
    assert response.status_code == 404
    assert "no encontrado" in response.json()["detail"]


# ==============================================================================
# TELEGRAM SERVICE TESTS
# ==============================================================================

@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
async def test_send_approval_message_photo(mock_post):
    # Setup mock httpx success response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"ok": True}
    mock_post.return_value = mock_response

    service = TelegramService()
    post_data = {
        "content": "Contenido del post de prueba",
        "media_url": "https://images.unsplash.com/photo-12345"
    }

    await service.send_approval_message(post_id=1, chat_id="chat-123", post_data=post_data)
    
    # Assert sendPhoto was called
    args, kwargs = mock_post.call_args
    assert "sendPhoto" in args[0]
    payload = kwargs["json"]
    assert payload["chat_id"] == "chat-123"
    assert "Contenido del post" in payload["caption"]
    assert "reply_markup" in payload


@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
async def test_send_approval_message_text_fallback(mock_post):
    # Setup mock httpx failure response for sendPhoto, success for sendMessage
    mock_response_fail = MagicMock()
    mock_response_fail.status_code = 400
    mock_response_success = MagicMock()
    mock_response_success.status_code = 200
    mock_response_success.json.return_value = {"ok": True}

    mock_post.side_effect = [mock_response_fail, mock_response_success]

    service = TelegramService()
    post_data = {
        "content": "Contenido del post sin media",
        "media_url": None
    }

    await service.send_approval_message(post_id=1, chat_id="chat-123", post_data=post_data)
    
    # Assert it called sendMessage (due to missing media_url or photo failure)
    args, kwargs = mock_post.call_args
    assert "sendMessage" in args[0]
    payload = kwargs["json"]
    assert payload["chat_id"] == "chat-123"
    assert "Contenido del post" in payload["text"]
    assert "reply_markup" in payload


@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
@patch("services.telegram_service.PostScheduler")
async def test_handle_callback_query_approve(mock_scheduler_cls, mock_post, mock_service_supabase):
    # Mock scheduler
    mock_scheduler = MagicMock()
    mock_scheduler_cls.return_value = mock_scheduler

    # Mock HTTP response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"ok": True}
    mock_post.return_value = mock_response

    from models.schemas import TelegramCallbackQuery
    cb_data = {
        "id": "cb-1",
        "from": {"id": 999, "is_bot": False, "first_name": "Test"},
        "message": {
            "message_id": 100,
            "chat": {"id": 999, "type": "private"},
            "date": 1600000000,
            "text": "Original text"
        },
        "data": "approve:1"
    }
    callback_query = TelegramCallbackQuery(**cb_data)

    service = TelegramService()
    await service.handle_callback_query(callback_query)

    # Verify post scheduler scheduled the post
    mock_scheduler.schedule_post.assert_called_once()
    # Verify we answered callback query and edited message text
    assert mock_post.call_count >= 2


@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
async def test_handle_callback_query_reject(mock_post, mock_service_supabase):
    # Mock HTTP response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"ok": True}
    mock_post.return_value = mock_response

    from models.schemas import TelegramCallbackQuery
    cb_data = {
        "id": "cb-2",
        "from": {"id": 999, "is_bot": False, "first_name": "Test"},
        "message": {
            "message_id": 100,
            "chat": {"id": 999, "type": "private"},
            "date": 1600000000,
            "text": "Original text"
        },
        "data": "reject:1"
    }
    callback_query = TelegramCallbackQuery(**cb_data)

    service = TelegramService()
    await service.handle_callback_query(callback_query)

    # Verify DB update status to failed
    mock_service_supabase.table('posts').update.assert_called_once_with({"status": "failed"})
    assert mock_post.call_count >= 2


@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
async def test_handle_callback_query_edit(mock_post, mock_service_supabase):
    # Mock HTTP response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"ok": True}
    mock_post.return_value = mock_response

    from models.schemas import TelegramCallbackQuery
    cb_data = {
        "id": "cb-3",
        "from": {"id": 999, "is_bot": False, "first_name": "Test"},
        "message": {
            "message_id": 100,
            "chat": {"id": 999, "type": "private"},
            "date": 1600000000,
            "text": "Original text"
        },
        "data": "edit:1"
    }
    callback_query = TelegramCallbackQuery(**cb_data)

    service = TelegramService()
    await service.handle_callback_query(callback_query)

    # Verify sub-menu with edit options sent
    args, kwargs = mock_post.call_args
    assert "sendMessage" in args[0]
    payload = kwargs["json"]
    assert "inline_keyboard" in str(payload.get("reply_markup"))
    assert "edit_text:1" in str(payload.get("reply_markup"))
    assert "edit_date:1" in str(payload.get("reply_markup"))


@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
@patch.object(TelegramService, "send_approval_message", new_callable=AsyncMock)
async def test_handle_message_edit_reply(mock_send_approval, mock_post, mock_service_supabase):
    # Mock select response
    mock_posts_table = mock_service_supabase.table('posts')
    mock_select = MagicMock()
    mock_select.execute.return_value = MagicMock(data=[{"id": 1, "instagram_account_id": "mock-account-id", "content": "Updated content"}])
    mock_posts_table.select.return_value.eq.return_value = mock_select

    from models.schemas import TelegramMessage
    msg_data = {
        "message_id": 101,
        "chat": {"id": 999, "type": "private"},
        "date": 1600000000,
        "text": "Este es el contenido nuevo del post",
        "reply_to_message": {
            "message_id": 100,
            "chat": {"id": 999, "type": "private"},
            "date": 1600000000,
            "text": "Envía el nuevo texto para #post_1:"
        }
    }
    message = TelegramMessage(**msg_data)

    service = TelegramService()
    await service.handle_message(message)

    # Verify database content update
    mock_posts_table.update.assert_called_once_with({"content": "Este es el contenido nuevo del post", "status": "draft"})
    # Verify send_approval_message called for the updated post
    mock_send_approval.assert_called_once_with(1, "999", {"id": 1, "instagram_account_id": "mock-account-id", "content": "Updated content"})


@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
async def test_handle_message_start_linking(mock_post):
    # Mock link token API call (local/internal API)
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True}
    mock_post.return_value = mock_response

    from models.schemas import TelegramMessage
    msg_data = {
        "message_id": 102,
        "chat": {"id": 999, "type": "private"},
        "date": 1600000000,
        "text": "/start token-uuid-xyz-123"
    }
    message = TelegramMessage(**msg_data)

    service = TelegramService()
    await service.handle_message(message)

    # Verify it posted to /api/telegram/link-account
    assert mock_post.call_count >= 2
    post_calls = [call for call in mock_post.call_args_list if "/link-account" in call[0][0]]
    assert len(post_calls) == 1
    _, kwargs = post_calls[0]
    assert kwargs["json"]["link_token"] == "token-uuid-xyz-123"
    assert kwargs["json"]["telegram_chat_id"] == "999"


# ==============================================================================
# OWNERSHIP VERIFICATION TESTS
# ==============================================================================

@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
@patch("services.telegram_service.PostScheduler")
async def test_unauthorized_post_callback(mock_scheduler_cls, mock_post, mock_service_supabase):
    from models.schemas import TelegramCallbackQuery
    cb_data = {
        "id": "cb-unauth",
        "from": {"id": 12345, "is_bot": False, "first_name": "Unauth"},  # chat_id is "12345"
        "message": {
            "message_id": 100,
            "chat": {"id": 12345, "type": "private"},
            "date": 1600000000,
            "text": "Original text"
        },
        "data": "approve:1"
    }
    callback_query = TelegramCallbackQuery(**cb_data)

    service = TelegramService()
    await service.handle_callback_query(callback_query)

    mock_scheduler = mock_scheduler_cls.return_value
    mock_scheduler.schedule_post.assert_not_called()
    
    # Callback query should still be acknowledged (answerCallbackQuery) but editMessageText should not be called
    post_calls = [call for call in mock_post.call_args_list if "editMessageText" in call[0][0]]
    assert len(post_calls) == 0


@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
async def test_unauthorized_proposal_callback(mock_post, mock_service_supabase):
    from models.schemas import TelegramCallbackQuery
    cb_data = {
        "id": "cb-unauth-prop",
        "from": {"id": 12345, "is_bot": False, "first_name": "Unauth"},
        "message": {
            "message_id": 100,
            "chat": {"id": 12345, "type": "private"},
            "date": 1600000000,
            "text": "Original text"
        },
        "data": "proposal:approve:mock-proposal-id"
    }
    callback_query = TelegramCallbackQuery(**cb_data)

    service = TelegramService()
    await service.handle_callback_query(callback_query)

    # Table content_proposals should not be updated/mutated
    mock_prop_table = mock_service_supabase.table('content_proposals')
    mock_prop_table.update.assert_not_called()


@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
async def test_unauthorized_message_reply(mock_post, mock_service_supabase):
    from models.schemas import TelegramMessage
    msg_data = {
        "message_id": 101,
        "chat": {"id": 12345, "type": "private"},  # unauthorized chat
        "date": 1600000000,
        "text": "Este es el contenido nuevo del post",
        "reply_to_message": {
            "message_id": 100,
            "chat": {"id": 12345, "type": "private"},
            "date": 1600000000,
            "text": "Envía el nuevo texto para #post_1:"
        }
    }
    message = TelegramMessage(**msg_data)

    service = TelegramService()
    await service.handle_message(message)

    # DB update for posts should not be called
    mock_posts_table = mock_service_supabase.table('posts')
    mock_posts_table.update.assert_not_called()


# ==============================================================================
# WEBHOOK REGISTRATION LOGGING TESTS
# ==============================================================================

@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
async def test_register_webhook_failure_redacts_token_in_log(mock_post, caplog):
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = "Bad Request: bad webhook: mock-bot-token is not a valid token"
    mock_post.return_value = mock_response

    service = TelegramService()
    with caplog.at_level("ERROR"):
        await service.register_webhook("https://example.com")

    assert "mock-bot-token" not in caplog.text
    assert "<REDACTED>" in caplog.text
