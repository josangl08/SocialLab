import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
from main import app
from auth.dependencies import get_current_user, get_user_supabase_client
from models.schemas import User
from tests.conftest import USER_ID

# Mock current user
async def mock_get_current_user():
    return User(id=USER_ID, email="test@example.com")

# Apply dependency override
app.dependency_overrides[get_current_user] = mock_get_current_user

# Create TestClient
client = TestClient(app)

@pytest.fixture
def mock_supabase():
    mock_sup = MagicMock()
    app.dependency_overrides[get_user_supabase_client] = lambda: mock_sup
    yield mock_sup
    app.dependency_overrides.pop(get_user_supabase_client, None)

@pytest.fixture
def mock_admin_supabase():
    with patch("routes.posts_routes.admin_supabase") as mock_sup_admin:
        yield mock_sup_admin

@pytest.fixture
def mock_agent_supabase():
    mock_sup = MagicMock()
    app.dependency_overrides[get_user_supabase_client] = lambda: mock_sup
    yield mock_sup
    app.dependency_overrides.pop(get_user_supabase_client, None)

@pytest.fixture
def mock_agent_admin_supabase():
    with patch("routes.agent_routes.admin_supabase") as mock_sup_admin:
        yield mock_sup_admin


# ==============================================================================
# Migrated CRUD endpoints under /api/posts
# ==============================================================================

def test_create_post(mock_supabase, mock_admin_supabase):
    mock_post = {
        "id": 1,
        "user_id": USER_ID,
        "content": "Test post content",
        "media_url": "https://mock.storage.test/drafts/test.png",
        "post_type": "post",
        "status": "draft",
        "scheduled_at": None,
        "instagram_account_id": 123,
        "created_at": "2026-06-27T12:00:00"
    }

    mock_execute = MagicMock()
    mock_execute.execute.return_value = MagicMock(data=[mock_post])
    mock_supabase.table.return_value.insert.return_value = mock_execute

    # Mock instagram_accounts select to return telegram chat info
    mock_account_exec = MagicMock()
    mock_account_exec.execute.return_value = MagicMock(data=[{"telegram_chat_id": None}])
    mock_admin_supabase.table.return_value.select.return_value.eq.return_value = mock_account_exec

    response = client.post(
        "/api/posts",
        data={
            "content": "Test post content",
            "post_type": "post",
            "status": "draft",
            "instagram_account_id": 123
        }
    )

    assert response.status_code == 200
    assert response.json()["id"] == 1
    assert response.json()["content"] == "Test post content"
    assert response.json()["instagram_account_id"] == 123


def test_create_post_with_media_file(mock_supabase, mock_admin_supabase):
    mock_post = {
        "id": 1,
        "user_id": USER_ID,
        "content": "Test post with media",
        "media_url": "https://mock.storage.test/drafts/test.png",
        "post_type": "post",
        "status": "draft",
        "scheduled_at": None,
        "instagram_account_id": None,
        "created_at": "2026-06-27T12:00:00"
    }

    mock_execute = MagicMock()
    mock_execute.execute.return_value = MagicMock(data=[mock_post])
    mock_supabase.table.return_value.insert.return_value = mock_execute

    mock_admin_supabase.storage.from_.return_value.get_public_url.return_value = mock_post["media_url"]

    response = client.post(
        "/api/posts",
        data={
            "content": "Test post with media",
            "post_type": "post",
            "status": "draft"
        },
        files={
            "media_file": ("test.png", b"fake binary data", "image/png")
        }
    )

    assert response.status_code == 200
    assert response.json()["media_url"] == mock_post["media_url"]

    # Assert the raw bytes were passed through to storage upload (media_file.file.read() path)
    upload_call = mock_admin_supabase.storage.from_.return_value.upload.call_args
    assert upload_call.args[1] == b"fake binary data"


def test_create_post_schedules_telegram_notification(mock_supabase, mock_admin_supabase):
    mock_post = {
        "id": 1,
        "user_id": USER_ID,
        "content": "Test post content",
        "media_url": None,
        "post_type": "post",
        "status": "draft",
        "scheduled_at": None,
        "instagram_account_id": 123,
        "created_at": "2026-06-27T12:00:00"
    }

    mock_execute = MagicMock()
    mock_execute.execute.return_value = MagicMock(data=[mock_post])
    mock_supabase.table.return_value.insert.return_value = mock_execute

    # Mock instagram_accounts select to return a linked Telegram chat
    mock_account_exec = MagicMock()
    mock_account_exec.execute.return_value = MagicMock(data=[{"telegram_chat_id": "chat-42"}])
    mock_admin_supabase.table.return_value.select.return_value.eq.return_value = mock_account_exec

    with patch("services.telegram_service.TelegramService") as MockTelegramService:
        mock_service_instance = MockTelegramService.return_value
        mock_service_instance.send_approval_message = AsyncMock(return_value=None)

        response = client.post(
            "/api/posts",
            data={
                "content": "Test post content",
                "post_type": "post",
                "status": "draft",
                "instagram_account_id": 123
            }
        )

    assert response.status_code == 200
    # BackgroundTasks runs the queued task before TestClient returns the response,
    # so by this point send_approval_message must have fired with (post_id, chat_id, post).
    mock_service_instance.send_approval_message.assert_awaited_once_with(1, "chat-42", mock_post)


def test_create_post_draft_notify_telegram_false_no_card(mock_supabase, mock_admin_supabase):
    mock_post = {
        "id": 1,
        "user_id": USER_ID,
        "content": "Draft without telegram",
        "media_url": None,
        "post_type": "post",
        "status": "draft",
        "scheduled_at": None,
        "instagram_account_id": 123,
        "created_at": "2026-06-27T12:00:00"
    }

    mock_execute = MagicMock()
    mock_execute.execute.return_value = MagicMock(data=[mock_post])
    mock_supabase.table.return_value.insert.return_value = mock_execute

    mock_account_exec = MagicMock()
    mock_account_exec.execute.return_value = MagicMock(data=[{"telegram_chat_id": "chat-42"}])
    mock_admin_supabase.table.return_value.select.return_value.eq.return_value = mock_account_exec

    with patch("services.telegram_service.TelegramService") as MockTelegramService:
        mock_service_instance = MockTelegramService.return_value
        mock_service_instance.send_approval_message = AsyncMock(return_value=None)

        response = client.post(
            "/api/posts",
            data={
                "content": "Draft without telegram",
                "post_type": "post",
                "status": "draft",
                "instagram_account_id": 123,
                "notify_telegram": False
            }
        )

    assert response.status_code == 200
    mock_service_instance.send_approval_message.assert_not_called()


def test_create_post_scheduled_notify_telegram_false_creates_job(mock_supabase, mock_admin_supabase):
    from datetime import datetime, timezone, timedelta
    future_date = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    mock_post = {
        "id": 2,
        "user_id": USER_ID,
        "content": "Scheduled without telegram",
        "media_url": None,
        "post_type": "post",
        "status": "scheduled",
        "scheduled_at": future_date,
        "instagram_account_id": 123,
        "created_at": "2026-06-27T12:00:00"
    }

    mock_execute = MagicMock()
    mock_execute.execute.return_value = MagicMock(data=[mock_post])
    mock_supabase.table.return_value.insert.return_value = mock_execute

    mock_account_exec = MagicMock()
    mock_account_exec.execute.return_value = MagicMock(data=[{"telegram_chat_id": "chat-42"}])
    mock_admin_supabase.table.return_value.select.return_value.eq.return_value = mock_account_exec

    with patch("services.telegram_service.TelegramService") as MockTelegramService, \
         patch("services.scheduler.post_scheduler.PostScheduler") as MockPostScheduler:
        mock_telegram_instance = MockTelegramService.return_value
        mock_telegram_instance.send_approval_message = AsyncMock(return_value=None)
        mock_scheduler_instance = MockPostScheduler.return_value

        response = client.post(
            "/api/posts",
            data={
                "content": "Scheduled without telegram",
                "post_type": "post",
                "status": "scheduled",
                "scheduled_at": future_date,
                "instagram_account_id": 123,
                "notify_telegram": False
            },
            files={"media_file": ("foto.png", b"img", "image/png")}
        )

    assert response.status_code == 200
    mock_telegram_instance.send_approval_message.assert_not_called()
    mock_scheduler_instance.schedule_post.assert_called_once()


def test_create_post_scheduled_notify_telegram_false_missing_or_past_date_422(mock_supabase, mock_admin_supabase):
    from datetime import datetime, timezone, timedelta
    mock_account_exec = MagicMock()
    mock_account_exec.execute.return_value = MagicMock(data=[{"id": 123}])
    mock_admin_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value = mock_account_exec

    # Missing scheduled_at
    res1 = client.post(
        "/api/posts",
        data={
            "content": "Scheduled missing date",
            "post_type": "post",
            "status": "scheduled",
            "instagram_account_id": 123,
            "notify_telegram": False
        }
    )
    assert res1.status_code == 422

    # Past scheduled_at
    past_date = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    res2 = client.post(
        "/api/posts",
        data={
            "content": "Scheduled past date",
            "post_type": "post",
            "status": "scheduled",
            "scheduled_at": past_date,
            "instagram_account_id": 123,
            "notify_telegram": False
        }
    )
    assert res2.status_code == 422


def test_create_post_scheduled_notify_telegram_false_without_media_422(mock_supabase, mock_admin_supabase):
    from datetime import datetime, timezone, timedelta
    future_date = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()

    response = client.post(
        "/api/posts",
        data={
            "content": "Scheduled without media",
            "post_type": "post",
            "status": "scheduled",
            "scheduled_at": future_date,
            "notify_telegram": False
        }
    )

    assert response.status_code == 422
    mock_supabase.table.return_value.insert.assert_not_called()


def test_list_posts(mock_supabase):
    mock_posts = [
        {
            "id": 1,
            "user_id": USER_ID,
            "content": "Post 1",
            "media_url": "https://mock.storage.test/drafts/test1.png",
            "post_type": "post",
            "status": "draft",
            "scheduled_at": None,
            "instagram_account_id": 123,
            "created_at": "2026-06-27T12:00:00"
        }
    ]

    mock_execute = MagicMock()
    mock_execute.execute.return_value = MagicMock(data=mock_posts)
    mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value.order.return_value = mock_execute

    response = client.get("/api/posts")

    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) == 1
    assert response.json()[0]["content"] == "Post 1"


def test_update_post(mock_supabase, mock_admin_supabase):
    mock_post = {
        "id": 1,
        "user_id": USER_ID,
        "content": "Updated content",
        "media_url": "https://mock.storage.test/drafts/test.png",
        "post_type": "post",
        "status": "draft",
        "scheduled_at": None,
        "instagram_account_id": 123,
        "created_at": "2026-06-27T12:00:00"
    }

    mock_select_execute = MagicMock()
    mock_select_execute.execute.return_value = MagicMock(data=[{"id": 1, "media_url": "https://mock.storage.test/drafts/test.png"}])

    mock_update_execute = MagicMock()
    mock_update_execute.execute.return_value = MagicMock(data=[mock_post])

    mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value = mock_select_execute
    mock_supabase.table.return_value.update.return_value.eq.return_value = mock_update_execute

    response = client.put(
        "/api/posts/1",
        data={
            "content": "Updated content",
            "post_type": "post",
            "status": "draft",
            "instagram_account_id": 123
        }
    )

    assert response.status_code == 200
    assert response.json()["content"] == "Updated content"


def test_delete_post(mock_supabase, mock_admin_supabase):
    mock_select_execute = MagicMock()
    mock_select_execute.execute.return_value = MagicMock(data=[{"id": 1, "media_url": "https://mock.storage.test/drafts/test.png"}])

    mock_delete_execute = MagicMock()
    mock_delete_execute.execute.return_value = MagicMock(data=[])

    mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value = mock_select_execute
    mock_supabase.table.return_value.delete.return_value.eq.return_value = mock_delete_execute

    response = client.delete("/api/posts/1")

    assert response.status_code == 204
    mock_admin_supabase.storage.from_.return_value.remove.assert_called_once()


def test_create_post_with_foreign_instagram_account_forbidden(mock_supabase, mock_admin_supabase):
    # Mock admin_supabase instagram_accounts ownership query to return empty list (not owned)
    mock_ownership_exec = MagicMock()
    mock_ownership_exec.execute.return_value = MagicMock(data=[])
    mock_admin_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value = mock_ownership_exec

    response = client.post(
        "/api/posts",
        data={
            "content": "Test content",
            "post_type": "post",
            "status": "draft",
            "instagram_account_id": 999
        },
        files={
            "media_file": ("test.png", b"fake binary data", "image/png")
        }
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "No tienes permiso para usar esta cuenta de Instagram."

    # Assert that insert was never called on supabase table posts
    mock_supabase.table.assert_not_called()
    # Assert that storage upload was never called
    mock_admin_supabase.storage.from_.assert_not_called()


def test_update_post_with_foreign_instagram_account_forbidden(mock_supabase, mock_admin_supabase):
    # Mock post lookup select to return the existing post (so it passes the 404 check)
    mock_select_exec = MagicMock()
    mock_select_exec.execute.return_value = MagicMock(data=[{"id": 1, "media_url": "https://mock.storage.test/drafts/test.png"}])
    mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value = mock_select_exec

    # Mock admin_supabase instagram_accounts ownership query to return empty list (not owned)
    mock_ownership_exec = MagicMock()
    mock_ownership_exec.execute.return_value = MagicMock(data=[])
    mock_admin_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value = mock_ownership_exec

    response = client.put(
        "/api/posts/1",
        data={
            "content": "Updated content",
            "post_type": "post",
            "status": "draft",
            "instagram_account_id": 999
        },
        files={
            "media_file": ("new_test.png", b"new fake binary data", "image/png")
        }
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "No tienes permiso para usar esta cuenta de Instagram."

    # Assert that update was never called
    mock_supabase.table.return_value.update.assert_not_called()
    # Assert that existing media was not removed
    mock_admin_supabase.storage.from_.return_value.remove.assert_not_called()
    # Assert that new media was not uploaded
    mock_admin_supabase.storage.from_.return_value.upload.assert_not_called()


# ==============================================================================
# Agent proposal approval/rejection endpoints under /api/agent/proposals
# ==============================================================================

def test_approve_proposal_success(mock_agent_supabase, mock_agent_admin_supabase):
    proposal_id = "9cb68b1a-8280-496a-a2ef-97b77ab4671b"
    account_id = 123

    # 1. Fetch proposal mock
    mock_proposal_exec = MagicMock()
    mock_proposal_exec.execute.return_value = MagicMock(data=[{
        "id": proposal_id,
        "account_id": account_id,
        "week_start": "2026-06-29",
        "slots": [],
        "status": "pending"
    }])
    mock_agent_supabase.table.return_value.select.return_value.eq.return_value = mock_proposal_exec

    # 2. Check ownership mock
    mock_acc_exec = MagicMock()
    mock_acc_exec.execute.return_value = MagicMock(data=[{"user_id": USER_ID}])
    mock_agent_admin_supabase.table.return_value.select.return_value.eq.return_value = mock_acc_exec

    # 3. Update status mock
    mock_update_exec = MagicMock()
    mock_update_exec.execute.return_value = MagicMock(data=[{"id": proposal_id, "status": "approved"}])
    mock_agent_supabase.table.return_value.update.return_value.eq.return_value = mock_update_exec

    response = client.post(f"/api/agent/proposals/{proposal_id}/approve")

    assert response.status_code == 200
    assert response.json() == {"updated": True, "scheduled": 0}


def test_approve_proposal_not_found(mock_agent_supabase):
    proposal_id = "9cb68b1a-8280-496a-a2ef-97b77ab4671b"

    mock_proposal_exec = MagicMock()
    mock_proposal_exec.execute.return_value = MagicMock(data=[])
    mock_agent_supabase.table.return_value.select.return_value.eq.return_value = mock_proposal_exec

    response = client.post(f"/api/agent/proposals/{proposal_id}/approve")

    assert response.status_code == 404


def test_approve_proposal_forbidden(mock_agent_supabase, mock_agent_admin_supabase):
    proposal_id = "9cb68b1a-8280-496a-a2ef-97b77ab4671b"
    account_id = 123

    # 1. Fetch proposal mock
    mock_proposal_exec = MagicMock()
    mock_proposal_exec.execute.return_value = MagicMock(data=[{
        "id": proposal_id,
        "account_id": account_id,
        "week_start": "2026-06-29",
        "slots": [],
        "status": "pending"
    }])
    mock_agent_supabase.table.return_value.select.return_value.eq.return_value = mock_proposal_exec

    # 2. Check ownership mock (returns different user_id)
    mock_acc_exec = MagicMock()
    mock_acc_exec.execute.return_value = MagicMock(data=[{"user_id": "someone-else-uuid"}])
    mock_agent_admin_supabase.table.return_value.select.return_value.eq.return_value = mock_acc_exec

    response = client.post(f"/api/agent/proposals/{proposal_id}/approve")

    assert response.status_code == 403


def test_reject_proposal_success(mock_agent_supabase, mock_agent_admin_supabase):
    proposal_id = "9cb68b1a-8280-496a-a2ef-97b77ab4671b"
    account_id = 123

    # 1. Fetch proposal mock
    mock_proposal_exec = MagicMock()
    mock_proposal_exec.execute.return_value = MagicMock(data=[{
        "id": proposal_id,
        "account_id": account_id,
        "week_start": "2026-06-29",
        "slots": [],
        "status": "pending"
    }])
    mock_agent_supabase.table.return_value.select.return_value.eq.return_value = mock_proposal_exec

    # 2. Check ownership mock
    mock_acc_exec = MagicMock()
    mock_acc_exec.execute.return_value = MagicMock(data=[{"user_id": USER_ID}])
    mock_agent_admin_supabase.table.return_value.select.return_value.eq.return_value = mock_acc_exec

    # 3. Update status mock
    mock_update_exec = MagicMock()
    mock_update_exec.execute.return_value = MagicMock(data=[{"id": proposal_id, "status": "rejected"}])
    mock_agent_supabase.table.return_value.update.return_value.eq.return_value = mock_update_exec

    response = client.post(f"/api/agent/proposals/{proposal_id}/reject")

    assert response.status_code == 200
    assert response.json() == {"updated": True}
