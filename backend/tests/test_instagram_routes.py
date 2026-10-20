import pytest
import requests
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from main import app
from auth.dependencies import get_current_user
from models.schemas import User
from tests.conftest import USER_ID
from utils.oauth_state import generate_state_token

# Mock current user
async def mock_get_current_user():
    return User(id=USER_ID, email="test@example.com")

# Apply dependency override
app.dependency_overrides[get_current_user] = mock_get_current_user

client = TestClient(app)

@pytest.fixture
def mock_supabase():
    with patch("routes.instagram_routes.supabase") as mock_sup:
        yield mock_sup

@pytest.fixture
def mock_admin_supabase():
    with patch("routes.instagram_routes.admin_supabase") as mock_admin_sup:
        yield mock_admin_sup

def test_get_instagram_accounts(mock_admin_supabase):
    mock_accounts = [
        {
            "id": 1,
            "instagram_business_account_id": "ig-123",
            "username": "test_user_1",
            "account_name": "Test Account 1",
            "followers_count": 100,
            "profile_picture_url": "http://img.url/1.png",
            "expires_at": "2026-12-31T23:59:59Z",
            "is_active": True,
            "telegram_chat_id": "11111",
            "drive_folder_id": "folder-111"
        }
    ]

    mock_execute = MagicMock()
    mock_execute.execute.return_value = MagicMock(data=mock_accounts)
    mock_admin_supabase.table.return_value.select.return_value.eq.return_value = mock_execute

    response = client.get("/instagram/accounts")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["username"] == "test_user_1"
    assert response.json()[0]["telegram_chat_id"] == "11111"
    assert response.json()[0]["drive_folder_id"] == "folder-111"
    selected_columns = mock_admin_supabase.table.return_value.select.call_args[0][0]
    assert "sector" in selected_columns

def test_update_account_config_success(mock_admin_supabase):
    mock_select = MagicMock()
    mock_select.execute.return_value = MagicMock(data=[{"id": 1}])
    mock_admin_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value = mock_select

    mock_update = MagicMock()
    mock_update.execute.return_value = MagicMock(data=[])
    mock_admin_supabase.table.return_value.update.return_value.eq.return_value = mock_update

    response = client.put(
        "/instagram/accounts/1/config",
        json={
            "telegram_chat_id": "22222",
            "drive_folder_id": "folder-222"
        }
    )

    assert response.status_code == 200
    assert response.json() == {"success": True}
    mock_admin_supabase.table.return_value.update.assert_called_once_with({
        "telegram_chat_id": "22222",
        "drive_folder_id": "folder-222"
    })

def test_update_account_config_not_found(mock_admin_supabase):
    mock_select = MagicMock()
    mock_select.execute.return_value = MagicMock(data=[])
    mock_admin_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value = mock_select

    response = client.put(
        "/instagram/accounts/999/config",
        json={
            "telegram_chat_id": "22222"
        }
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Cuenta no encontrada"

def test_disconnect_account_success(mock_admin_supabase):
    mock_select = MagicMock()
    mock_select.execute.return_value = MagicMock(data=[{"id": 1}])
    mock_admin_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value = mock_select

    mock_delete = MagicMock()
    mock_delete.execute.return_value = MagicMock(data=[])
    mock_admin_supabase.table.return_value.delete.return_value.eq.return_value = mock_delete

    response = client.delete("/instagram/accounts/1")

    assert response.status_code == 200
    assert response.json() == {"success": True}
    mock_admin_supabase.table.return_value.delete.assert_called_once()

def test_disconnect_account_not_found(mock_admin_supabase):
    mock_select = MagicMock()
    mock_select.execute.return_value = MagicMock(data=[])
    mock_admin_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value = mock_select

    response = client.delete("/instagram/accounts/999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Cuenta no encontrada"

def test_get_instagram_status_active_and_expired():
    future_date = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
    past_date = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()

    mock_accounts = [
        {
            "id": 1,
            "instagram_business_account_id": "ig-1",
            "username": "active_user",
            "account_name": "Active Account",
            "expires_at": future_date,
            "is_active": True
        },
        {
            "id": 2,
            "instagram_business_account_id": "ig-2",
            "username": "expired_user",
            "account_name": "Expired Account",
            "expires_at": past_date,
            "is_active": True
        }
    ]

    mock_admin_db = MagicMock()
    mock_select = MagicMock()
    mock_select.execute.return_value = MagicMock(data=mock_accounts)
    mock_admin_db.table.return_value.select.return_value.eq.return_value = mock_select

    with patch("routes.instagram_routes.get_supabase_admin_client", return_value=mock_admin_db):
        response = client.get("/instagram/status")

    assert response.status_code == 200
    status_list = response.json()
    assert len(status_list) == 2

    assert status_list[0]["username"] == "active_user"
    assert status_list[0]["connected"] is True
    assert status_list[0]["expired"] is False

    assert status_list[1]["username"] == "expired_user"
    assert status_list[1]["connected"] is False
    assert status_list[1]["expired"] is True

def test_publish_to_instagram_expired_token(mock_supabase, mock_admin_supabase):
    mock_post = {
        "id": 10,
        "user_id": USER_ID,
        "content": "Test content",
        "media_url": "https://img.url/photo.png",
        "post_type": "image",
        "status": "draft",
        "instagram_account_id": 1,
        "instagram_post_id": None
    }

    mock_post_execute = MagicMock()
    mock_post_execute.execute.return_value = MagicMock(data=mock_post)
    mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value = mock_post_execute

    past_date = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
    mock_account = {
        "id": 1,
        "instagram_business_account_id": "ig-1",
        "long_lived_access_token": "expired-token",
        "expires_at": past_date,
        "is_active": True
    }

    mock_acc_execute = MagicMock()
    mock_acc_execute.execute.return_value = MagicMock(data=[mock_account])
    mock_query = MagicMock()
    mock_query.eq.return_value = mock_query
    mock_query.limit.return_value = mock_acc_execute
    mock_admin_supabase.table.return_value.select.return_value.eq.return_value = mock_query

    response = client.post("/instagram/publish/10")

    assert response.status_code == 401
    assert "El token de Instagram ha expirado" in response.json()["detail"]

def test_callback_instagram_valid_state_succeeds(mock_admin_supabase):
    state_token = generate_state_token(USER_ID)

    mock_post_response = MagicMock()
    mock_post_response.json.return_value = {"access_token": "short-lived-token"}

    mock_get_responses = [
        MagicMock(json=MagicMock(return_value={"access_token": "long-lived-token", "expires_in": 5184000})),
        MagicMock(json=MagicMock(return_value={"data": [{"id": "fb-page-1"}]})),
        MagicMock(json=MagicMock(return_value={"instagram_business_account": {"id": "ig-account-1"}})),
    ]

    mock_upsert_execute = MagicMock()
    mock_admin_supabase.table.return_value.upsert.return_value.execute.return_value = mock_upsert_execute

    with patch("routes.instagram_routes.requests.post", return_value=mock_post_response), \
         patch("routes.instagram_routes.requests.get", side_effect=mock_get_responses), \
         patch("routes.instagram_routes.get_supabase_admin_client", return_value=mock_admin_supabase):
        response = client.get(
            f"/callback/instagram?code=auth_code&state={state_token}",
            follow_redirects=False
        )

    assert response.status_code in [302, 307]
    assert "instagram_connected=true" in response.headers.get("location", "")

def test_callback_instagram_with_account_id_updates_targeted_row_not_upsert(mock_admin_supabase):
    # Regression test: reconnecting a specific card (state carries account_id)
    # must UPDATE that exact row, never upsert-by-instagram_business_account_id
    # — otherwise picking a different Facebook Page in Meta's popup while
    # reconnecting account #7 could silently create/touch a different account.
    state_token = generate_state_token(USER_ID, account_id="7")

    mock_post_response = MagicMock()
    mock_post_response.json.return_value = {"access_token": "short-lived-token"}

    mock_get_responses = [
        MagicMock(json=MagicMock(return_value={"access_token": "long-lived-token", "expires_in": 5184000})),
        MagicMock(json=MagicMock(return_value={"data": [{"id": "fb-page-1"}]})),
        MagicMock(json=MagicMock(return_value={"instagram_business_account": {"id": "ig-account-1"}})),
    ]

    with patch("routes.instagram_routes.requests.post", return_value=mock_post_response), \
         patch("routes.instagram_routes.requests.get", side_effect=mock_get_responses), \
         patch("routes.instagram_routes.get_supabase_admin_client", return_value=mock_admin_supabase):
        response = client.get(
            f"/callback/instagram?code=auth_code&state={state_token}",
            follow_redirects=False
        )

    assert response.status_code in [302, 307]
    mock_admin_supabase.table.return_value.upsert.assert_not_called()
    mock_admin_supabase.table.return_value.update.assert_called_once()
    update_payload = mock_admin_supabase.table.return_value.update.call_args[0][0]
    assert update_payload["instagram_business_account_id"] == "ig-account-1"
    assert update_payload["token_invalid"] is False
    mock_admin_supabase.table.return_value.update.return_value.eq.assert_any_call("id", "7")

def test_callback_instagram_invalid_state_returns_400():
    response = client.get(
        "/callback/instagram?code=auth_code&state=not-a-valid-token",
        follow_redirects=False
    )
    assert response.status_code == 400

def test_instagram_sync_expired_token_returns_401_not_500():
    # Regression test: requests.Response.__bool__() reflects HTTP success (ok),
    # not "is this object None" — `if e.response:` was always False for error
    # responses, so an expired/invalid token always fell through to a generic
    # 500 instead of the intended 401 "reconecta tu cuenta" message.
    mock_admin_supabase = MagicMock()
    mock_admin_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
        {"id": 7, "long_lived_access_token": "encrypted-token", "instagram_business_account_id": "ig-7"}
    ]

    error_response = MagicMock()
    error_response.status_code = 400
    error_response.text = '{"error": {"message": "Error validating access token"}}'
    http_error = requests.exceptions.HTTPError(response=error_response)

    mock_get_response = MagicMock()
    mock_get_response.raise_for_status.side_effect = http_error

    with patch("routes.instagram_routes.get_supabase_admin_client", return_value=mock_admin_supabase), \
         patch("routes.instagram_routes.decrypt_token", return_value="plain-token"), \
         patch("routes.instagram_routes.requests.get", return_value=mock_get_response):
        response = client.get("/instagram/sync?instagram_account_id=7")

    assert response.status_code == 401
    assert "reconectar" in response.json()["detail"].lower() or "expirado" in response.json()["detail"].lower()
    mock_admin_supabase.table.return_value.update.assert_called_once_with({"token_invalid": True})
    mock_admin_supabase.table.return_value.update.return_value.eq.assert_called_once_with("id", 7)


def test_publish_to_instagram_quota_exceeded_returns_429(mock_supabase, mock_admin_supabase):
    """Publicación directa con cuota agotada devuelve 429 PUBLISH_QUOTA_EXCEEDED sin publicar."""
    mock_post = {
        "id": 11,
        "user_id": USER_ID,
        "content": "Post sin cuota",
        "media_url": "https://img.url/photo.png",
        "post_type": "image",
        "status": "draft",
        "instagram_account_id": 1,
        "instagram_post_id": None
    }
    mock_post_execute = MagicMock()
    mock_post_execute.execute.return_value = MagicMock(data=mock_post)
    mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value = mock_post_execute

    mock_account = {
        "id": 1,
        "instagram_business_account_id": "ig-123",
        "long_lived_access_token": "valid-token",
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        "is_active": True
    }
    mock_acc_execute = MagicMock()
    mock_acc_execute.execute.return_value = MagicMock(data=[mock_account])
    mock_query = MagicMock()
    mock_query.eq.return_value = mock_query
    mock_query.limit.return_value = mock_acc_execute
    mock_admin_supabase.table.return_value.select.return_value.eq.return_value = mock_query

    with patch("routes.instagram_routes.fetch_publishing_quota", return_value={"quota_usage": 100, "quota_total": 100}) as mock_quota, \
         patch("routes.instagram_routes.decrypt_token", return_value="valid-token"), \
         patch("routes.instagram_routes.requests.post") as mock_post_req:
        response = client.post("/instagram/publish/11")

    assert response.status_code == 429
    assert response.json()["code"] == "PUBLISH_QUOTA_EXCEEDED"
    mock_quota.assert_called_once_with("ig-123", "valid-token")
    mock_post_req.assert_not_called()
