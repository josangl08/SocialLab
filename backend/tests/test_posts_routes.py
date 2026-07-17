import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
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


def test_delete_post(mock_supabase):
    mock_select_execute = MagicMock()
    mock_select_execute.execute.return_value = MagicMock(data=[{"id": 1, "media_url": "https://mock.storage.test/drafts/test.png"}])

    mock_delete_execute = MagicMock()
    mock_delete_execute.execute.return_value = MagicMock(data=[])

    mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value = mock_select_execute
    mock_supabase.table.return_value.delete.return_value.eq.return_value = mock_delete_execute
    mock_supabase.storage.from_().remove = MagicMock(return_value=None)

    response = client.delete("/api/posts/1")

    assert response.status_code == 204


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
