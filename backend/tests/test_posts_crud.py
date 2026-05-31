import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from main import app
from auth.dependencies import get_current_user
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
    with patch("routes.posts_crud_routes.supabase") as mock_sup:
        yield mock_sup

def test_create_post_with_account(mock_supabase):
    # Setup mock supabase response
    mock_post = {
        "id": 1,
        "user_id": USER_ID,
        "content": "Test post with account",
        "media_url": "https://mock.storage.test/drafts/test.png",
        "post_type": "post",
        "status": "draft",
        "scheduled_at": None,
        "instagram_account_id": 123,
        "created_at": "2026-05-29T18:00:00"
    }
    
    mock_execute = MagicMock()
    mock_execute.execute.return_value = MagicMock(data=[mock_post])

    # Mock insert chain
    mock_supabase.table.return_value.insert.return_value = mock_execute

    # Mock instagram_accounts select (no telegram_chat_id → skip Telegram task)
    mock_account_exec = MagicMock()
    mock_account_exec.execute.return_value = MagicMock(data=[{"telegram_chat_id": None}])
    mock_supabase.table.return_value.select.return_value.eq.return_value = mock_account_exec

    # Send request to create post with instagram_account_id
    response = client.post(
        "/posts",
        data={
            "content": "Test post with account",
            "post_type": "post",
            "status": "draft",
            "instagram_account_id": 123
        }
    )

    assert response.status_code == 200
    assert response.json()["instagram_account_id"] == 123

    # Verify insert call included instagram_account_id
    mock_supabase.table.assert_any_call("posts")
    mock_supabase.table().insert.assert_called_once()
    inserted_data = mock_supabase.table().insert.call_args[0][0]
    assert inserted_data["instagram_account_id"] == 123

def test_create_post_without_account(mock_supabase):
    # Setup mock supabase response
    mock_post = {
        "id": 2,
        "user_id": USER_ID,
        "content": "Test post without account",
        "media_url": "https://mock.storage.test/drafts/test.png",
        "post_type": "post",
        "status": "draft",
        "scheduled_at": None,
        "instagram_account_id": None,
        "created_at": "2026-05-29T18:00:00"
    }
    
    mock_execute = MagicMock()
    mock_execute.execute.return_value = MagicMock(data=[mock_post])
    
    # Mock insert and execute chain
    mock_supabase.table.return_value.insert.return_value = mock_execute
    
    # Send request to create post without instagram_account_id
    response = client.post(
        "/posts",
        data={
            "content": "Test post without account",
            "post_type": "post",
            "status": "draft"
        }
    )
    
    assert response.status_code == 200
    assert response.json()["instagram_account_id"] is None
    
    # Verify insert call had instagram_account_id as None or omitted
    inserted_data = mock_supabase.table().insert.call_args[0][0]
    assert inserted_data.get("instagram_account_id") is None

def test_update_post_with_account(mock_supabase):
    # Setup mock supabase response for select and update
    mock_post = {
        "id": 1,
        "user_id": USER_ID,
        "content": "Updated content",
        "media_url": "https://mock.storage.test/drafts/test.png",
        "post_type": "post",
        "status": "draft",
        "scheduled_at": None,
        "instagram_account_id": 456,
        "created_at": "2026-05-29T18:00:00"
    }
    
    # For checking if post exists and user owns it
    mock_select_execute = MagicMock()
    mock_select_execute.execute.return_value = MagicMock(data=[{"id": 1, "media_url": "https://mock.storage.test/drafts/test.png"}])
    
    mock_update_execute = MagicMock()
    mock_update_execute.execute.return_value = MagicMock(data=[mock_post])
    
    mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value = mock_select_execute
    mock_supabase.table.return_value.update.return_value.eq.return_value = mock_update_execute
    
    # Send request to update post
    response = client.put(
        "/posts/1",
        data={
            "content": "Updated content",
            "post_type": "post",
            "status": "draft",
            "instagram_account_id": 456
        }
    )
    
    assert response.status_code == 200
    assert response.json()["instagram_account_id"] == 456
    
    # Verify update data included instagram_account_id
    updated_data = mock_supabase.table().update.call_args[0][0]
    assert updated_data["instagram_account_id"] == 456

def test_get_posts_includes_account_id(mock_supabase):
    mock_post = {
        "id": 1,
        "user_id": USER_ID,
        "content": "Stored post",
        "media_url": "https://mock.storage.test/drafts/test.png",
        "post_type": "post",
        "status": "draft",
        "scheduled_at": None,
        "instagram_account_id": 789,
        "created_at": "2026-05-29T18:00:00"
    }
    
    mock_execute = MagicMock()
    mock_execute.execute.return_value = MagicMock(data=[mock_post])
    
    # Mock chain: table('posts').select('*').eq(...).order(...).order(...).execute()
    mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value.order.return_value = mock_execute
    
    response = client.get("/posts")
    
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["instagram_account_id"] == 789
