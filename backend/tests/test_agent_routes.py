# ABOUTME: Test suite for agent API routes (approve, reject, slot actions).
# Auth: Antigravity CLI

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from main import app
from auth.dependencies import get_current_user, get_user_supabase_client
from models.schemas import User
from tests.conftest import USER_ID
from datetime import datetime, timezone

# Mock current user
async def mock_get_current_user():
    return User(id=USER_ID, email="test@example.com")

# Apply dependency override
app.dependency_overrides[get_current_user] = mock_get_current_user

# Create TestClient
client = TestClient(app)

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


@patch("services.scheduler.post_scheduler.PostScheduler")
def test_approve_proposal_success(mock_scheduler_cls, mock_agent_supabase, mock_agent_admin_supabase):
    mock_scheduler = MagicMock()
    mock_scheduler_cls.return_value = mock_scheduler

    proposal_id = "prop-123"
    account_id = 456
    
    # 1. Mock content_proposals select response
    mock_proposal_exec = MagicMock()
    mock_proposal_exec.execute.return_value = MagicMock(data=[{
        "id": proposal_id,
        "account_id": account_id,
        "week_start": "2026-06-29",
        "slots": [
            {"day": "Monday", "post_id": 1001, "theme": "match highlight", "caption": "cap 1", "image_id": "file-1", "post_type": "post"},
            {"day": "Wednesday", "post_id": 1002, "theme": "training", "caption": "cap 2", "image_id": "file-2", "post_type": "reel"}
        ],
        "status": "pending_approval"
    }])
    mock_agent_supabase.table.return_value.select.return_value.eq.return_value = mock_proposal_exec

    # 2. Mock account ownership select response
    mock_acc_exec = MagicMock()
    mock_acc_exec.execute.return_value = MagicMock(data=[{"user_id": USER_ID}])
    mock_agent_admin_supabase.table.return_value.select.return_value.eq.return_value = mock_acc_exec

    # 3. Mock posts select response
    mock_posts_exec = MagicMock()
    mock_posts_exec.execute.return_value = MagicMock(data=[
        {"id": 1001, "scheduled_at": "2026-06-29T10:00:00+00:00", "media_url": "https://storage.com/image1.png"},
        {"id": 1002, "scheduled_at": "2026-07-01T15:00:00Z", "media_url": "https://storage.com/reel1.mp4"}
    ])
    
    def mock_table_admin(name):
        mock_t = MagicMock()
        if name == "instagram_accounts":
            mock_t.select.return_value.eq.return_value = mock_acc_exec
        elif name == "posts":
            mock_t.select.return_value.in_.return_value = mock_posts_exec
            mock_t.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        elif name == "content_proposals":
            mock_t.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        return mock_t

    mock_agent_admin_supabase.table.side_effect = mock_table_admin

    response = client.post(f"/api/agent/proposals/{proposal_id}/approve")
    
    assert response.status_code == 200
    assert response.json() == {"updated": True, "scheduled": 2}
    
    assert mock_scheduler.schedule_post.call_count == 2


def test_reject_proposal_success(mock_agent_supabase, mock_agent_admin_supabase):
    proposal_id = "prop-123"
    account_id = 456

    # 1. Mock content_proposals select response
    mock_proposal_exec = MagicMock()
    mock_proposal_exec.execute.return_value = MagicMock(data=[{
        "id": proposal_id,
        "account_id": account_id,
        "week_start": "2026-06-29",
        "slots": [
            {"day": "Monday", "post_id": 1001, "theme": "match highlight", "caption": "cap 1", "image_id": "file-1", "post_type": "post"},
            {"day": "Wednesday", "post_id": 1002, "theme": "training", "caption": "cap 2", "image_id": "file-2", "post_type": "reel"}
        ],
        "status": "pending_approval"
    }])
    mock_agent_supabase.table.return_value.select.return_value.eq.return_value = mock_proposal_exec

    # 2. Mock account ownership select response
    mock_acc_exec = MagicMock()
    mock_acc_exec.execute.return_value = MagicMock(data=[{"user_id": USER_ID}])
    
    mock_delete_exec = MagicMock()
    mock_delete_exec.execute.return_value = MagicMock(data=[])

    def mock_table_admin(name):
        mock_t = MagicMock()
        if name == "instagram_accounts":
            mock_t.select.return_value.eq.return_value = mock_acc_exec
        elif name == "posts":
            mock_t.delete.return_value.eq.return_value.eq.return_value = mock_delete_exec
        elif name == "content_proposals":
            mock_t.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        return mock_t

    mock_agent_admin_supabase.table.side_effect = mock_table_admin

    response = client.post(f"/api/agent/proposals/{proposal_id}/reject")

    assert response.status_code == 200
    assert response.json() == {"updated": True}
    assert mock_delete_exec.execute.call_count == 2


@patch("routes.agent_routes.genai.GenerativeModel")
def test_regenerate_slot_success(mock_model_cls, mock_agent_supabase, mock_agent_admin_supabase):
    proposal_id = "prop-123"
    account_id = 456
    
    mock_model_instance = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "New generated caption by Gemini"
    mock_model_instance.generate_content.return_value = mock_response
    mock_model_cls.return_value = mock_model_instance

    # 1. Mock content_proposals select response
    mock_proposal_exec = MagicMock()
    mock_proposal_exec.execute.return_value = MagicMock(data=[{
        "id": proposal_id,
        "account_id": account_id,
        "week_start": "2026-06-29",
        "slots": [
            {"day": "Monday", "post_id": 1001, "theme": "match highlight", "caption": "cap 1", "image_id": "file-1", "post_type": "post"}
        ],
        "status": "pending_approval"
    }])
    
    # 2. Mock visual_analyses select response
    mock_va_exec = MagicMock()
    mock_va_exec.execute.return_value = MagicMock(data=[{"gemini_description": "stadium with flags"}])

    def mock_table(name):
        mock_t = MagicMock()
        if name == "content_proposals":
            mock_t.select.return_value.eq.return_value = mock_proposal_exec
        elif name == "visual_analyses":
            mock_t.select.return_value.eq.return_value = mock_va_exec
        return mock_t

    mock_agent_supabase.table.side_effect = mock_table

    # 3. Mock account ownership select response
    mock_acc_exec = MagicMock()
    mock_acc_exec.execute.return_value = MagicMock(data=[{"user_id": USER_ID}])

    def mock_table_admin(name):
        mock_t = MagicMock()
        if name == "instagram_accounts":
            mock_t.select.return_value.eq.return_value = mock_acc_exec
        elif name == "posts":
            mock_t.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        elif name == "content_proposals":
            mock_t.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        return mock_t

    mock_agent_admin_supabase.table.side_effect = mock_table_admin

    with patch.dict("os.environ", {"GOOGLE_API_KEY": "dummy-key"}):
        response = client.post(f"/api/agent/proposals/{proposal_id}/slots/0/regenerate")

    assert response.status_code == 200
    assert response.json() == {"caption": "New generated caption by Gemini"}


def test_skip_slot_success(mock_agent_supabase, mock_agent_admin_supabase):
    proposal_id = "prop-123"
    account_id = 456

    # 1. Mock content_proposals select response
    mock_proposal_exec = MagicMock()
    mock_proposal_exec.execute.return_value = MagicMock(data=[{
        "id": proposal_id,
        "account_id": account_id,
        "week_start": "2026-06-29",
        "slots": [
            {"day": "Monday", "post_id": 1001, "theme": "match highlight", "caption": "cap 1", "image_id": "file-1", "post_type": "post"}
        ],
        "status": "pending_approval"
    }])
    mock_agent_supabase.table.return_value.select.return_value.eq.return_value = mock_proposal_exec

    # 2. Mock account ownership select response
    mock_acc_exec = MagicMock()
    mock_acc_exec.execute.return_value = MagicMock(data=[{"user_id": USER_ID}])

    mock_delete_exec = MagicMock()
    mock_delete_exec.execute.return_value = MagicMock(data=[])

    def mock_table_admin(name):
        mock_t = MagicMock()
        if name == "instagram_accounts":
            mock_t.select.return_value.eq.return_value = mock_acc_exec
        elif name == "posts":
            mock_t.delete.return_value.eq.return_value.eq.return_value = mock_delete_exec
        elif name == "content_proposals":
            mock_t.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        return mock_t

    mock_agent_admin_supabase.table.side_effect = mock_table_admin

    response = client.post(f"/api/agent/proposals/{proposal_id}/slots/0/skip")

    assert response.status_code == 200
    assert response.json() == {"skipped": True}
    mock_delete_exec.execute.assert_called_once()


def test_update_slot_type_success(mock_agent_supabase, mock_agent_admin_supabase):
    proposal_id = "prop-123"
    account_id = 456

    # 1. Mock content_proposals select response
    mock_proposal_exec = MagicMock()
    mock_proposal_exec.execute.return_value = MagicMock(data=[{
        "id": proposal_id,
        "account_id": account_id,
        "week_start": "2026-06-29",
        "slots": [
            {"day": "Monday", "post_id": 1001, "theme": "match highlight", "caption": "cap 1", "image_id": "file-1", "post_type": "post"}
        ],
        "status": "pending_approval"
    }])
    mock_agent_supabase.table.return_value.select.return_value.eq.return_value = mock_proposal_exec

    # 2. Mock account ownership select response
    mock_acc_exec = MagicMock()
    mock_acc_exec.execute.return_value = MagicMock(data=[{"user_id": USER_ID}])

    def mock_table_admin(name):
        mock_t = MagicMock()
        if name == "instagram_accounts":
            mock_t.select.return_value.eq.return_value = mock_acc_exec
        elif name == "posts":
            mock_t.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        elif name == "content_proposals":
            mock_t.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        return mock_t

    mock_agent_admin_supabase.table.side_effect = mock_table_admin

    response = client.post(
        f"/api/agent/proposals/{proposal_id}/slots/0/type",
        json={"post_type": "reel"}
    )

    assert response.status_code == 200
    assert response.json() == {"updated": True}


# ── /trigger endpoint tests ─────────────────────────────────────────────────

def test_trigger_agent_account_not_found(mock_agent_admin_supabase):
    mock_agent_admin_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

    response = client.post('/api/agent/trigger', json={'account_id': 9999})

    assert response.status_code == 404
    assert 'Cuenta de Instagram no encontrada' in response.json()['detail']


def test_trigger_agent_no_drive_folder(mock_agent_admin_supabase):
    mock_agent_admin_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[{
        'user_id': USER_ID, 'drive_folder_id': None
    }])

    response = client.post('/api/agent/trigger', json={'account_id': 1})

    assert response.status_code == 400
    assert 'carpeta de Drive' in response.json()['detail']


def test_trigger_agent_drive_not_connected(mock_agent_admin_supabase):
    mock_agent_admin_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[{
        'user_id': USER_ID, 'drive_folder_id': 'folder-123'
    }])

    with patch('services.google_drive_connector.get_drive_connector', side_effect=RuntimeError("No tokens")):
        response = client.post('/api/agent/trigger', json={'account_id': 1})

    assert response.status_code == 503
    assert 'Google Drive' in response.json()['detail']


@patch('services.google_drive_connector.get_drive_connector')
@patch('services.agent_service.run_agent')
def test_trigger_agent_success(mock_run_agent, mock_get_connector, mock_agent_admin_supabase):
    mock_agent_admin_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[{
        'user_id': USER_ID, 'drive_folder_id': 'folder-123'
    }])
    mock_get_connector.return_value = MagicMock()

    response = client.post('/api/agent/trigger', json={'account_id': 1})

    assert response.status_code == 200
    body = response.json()
    assert body['status'] == 'started'
    assert 'run_id' in body
