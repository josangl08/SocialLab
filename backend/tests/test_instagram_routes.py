import pytest
import requests
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from main import app
from auth.dependencies import get_current_user, get_current_user_from_query_token
from models.schemas import User
from tests.conftest import USER_ID
from utils.oauth_state import generate_state_token
from utils.graph_api import graph_base_url

# Mock current user
async def mock_get_current_user():
    return User(id=USER_ID, email="test@example.com")

# Apply dependency override
app.dependency_overrides[get_current_user] = mock_get_current_user
app.dependency_overrides[get_current_user_from_query_token] = mock_get_current_user

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
    # AccountsPage usa este endpoint para el aviso de migración (AD-6)
    assert "login_type" in selected_columns

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

@pytest.fixture
def instagram_login_env(monkeypatch):
    monkeypatch.setenv("INSTAGRAM_LOGIN_APP_ID", "ig-app-id")
    monkeypatch.setenv("INSTAGRAM_LOGIN_APP_SECRET", "ig-app-secret")
    monkeypatch.setenv("INSTAGRAM_REDIRECT_URI", "http://localhost:8000/callback/instagram")


def _instagram_login_responses(ig_user_id="ig-account-1"):
    """Respuestas simuladas: token corto (POST), token largo y /me (GET)."""
    short = MagicMock()
    short.json.return_value = {"access_token": "short-lived-token"}
    gets = [
        MagicMock(json=MagicMock(return_value={"access_token": "long-lived-token", "expires_in": 5184000})),
        MagicMock(json=MagicMock(return_value={"user_id": ig_user_id, "username": "user"})),
    ]
    return short, gets


def _run_callback(mock_admin_supabase, state_token):
    short, gets = _instagram_login_responses()
    with patch("services.instagram_token.requests.post", return_value=short) as mock_post, \
         patch("services.instagram_token.requests.get", side_effect=gets) as mock_get, \
         patch("services.instagram_token.encrypt_token", side_effect=lambda t: f"enc:{t}"), \
         patch("services.instagram_token.get_supabase_admin_client", return_value=mock_admin_supabase):
        response = client.get(f"/callback/instagram?code=auth_code&state={state_token}", follow_redirects=False)
    return response, mock_post, mock_get


def test_callback_instagram_valid_state_succeeds(mock_admin_supabase, instagram_login_env):
    response, mock_post, mock_get = _run_callback(mock_admin_supabase, generate_state_token(USER_ID))

    assert response.status_code in [302, 307]
    assert "instagram_connected=true" in response.headers.get("location", "")
    assert mock_post.call_args[0][0] == "https://api.instagram.com/oauth/access_token"
    urls = [c[0][0] for c in mock_get.call_args_list]
    assert urls[0] == "https://graph.instagram.com/access_token"
    assert mock_get.call_args_list[0][1]["params"]["grant_type"] == "ig_exchange_token"
    assert urls[1].startswith("https://graph.instagram.com/v") and urls[1].endswith("/me")
    assert not any("me/accounts" in url or "facebook.com" in url for url in urls)


def test_callback_instagram_with_account_id_updates_targeted_row_not_upsert(mock_admin_supabase, instagram_login_env):
    # Reconectar una tarjeta concreta (state con account_id) actualiza esa fila exacta, nunca upsert
    response, _, _ = _run_callback(mock_admin_supabase, generate_state_token(USER_ID, account_id="7"))

    assert response.status_code in [302, 307]
    mock_admin_supabase.table.return_value.upsert.assert_not_called()
    mock_admin_supabase.table.return_value.update.assert_called_once()
    update_payload = mock_admin_supabase.table.return_value.update.call_args[0][0]
    assert update_payload["instagram_business_account_id"] == "ig-account-1"
    assert update_payload["token_invalid"] is False
    assert update_payload["login_type"] == "instagram"
    mock_admin_supabase.table.return_value.update.return_value.eq.assert_any_call("id", "7")


def test_callback_instagram_expires_at_from_expires_in(mock_admin_supabase, instagram_login_env):
    """Instagram Login: expires_at = ahora + expires_in (60 días), sin debug_token."""
    response, _, _ = _run_callback(mock_admin_supabase, generate_state_token(USER_ID, account_id="7"))

    assert response.status_code in [302, 307]
    expires_at = datetime.fromisoformat(mock_admin_supabase.table.return_value.update.call_args[0][0]["expires_at"])
    assert abs(expires_at - (datetime.now(timezone.utc) + timedelta(days=60))) < timedelta(minutes=1)


def test_callback_instagram_missing_credentials_returns_500(monkeypatch):
    monkeypatch.setenv("INSTAGRAM_LOGIN_APP_ID", "")
    response = client.get(f"/callback/instagram?code=c&state={generate_state_token(USER_ID)}", follow_redirects=False)
    assert response.status_code == 500


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
        {"id": 7, "long_lived_access_token": "encrypted-token", "instagram_business_account_id": "ig-7", "login_type": "facebook"}
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
        "is_active": True,
        "login_type": "instagram"
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
    mock_quota.assert_called_once_with("ig-123", "valid-token", graph_base_url("instagram"))
    mock_post_req.assert_not_called()


# --- Tests de migración a Instagram Login (AD-3, AD-6) ---


def test_instagram_login_redirects_to_instagram_oauth_with_scopes(instagram_login_env):
    """AD-3: /instagram/login redirige a www.instagram.com/oauth/authorize con los 4 scopes."""
    response = client.get("/instagram/login?token=valid_token", follow_redirects=False)
    assert response.status_code in [302, 307]
    location = response.headers.get("location", "")

    assert location.startswith("https://www.instagram.com/oauth/authorize")
    assert "response_type=code" in location
    assert "instagram_business_basic" in location
    assert "instagram_business_content_publish" in location
    assert "instagram_business_manage_insights" in location
    assert "instagram_business_manage_comments" in location
    assert "state=" in location


def test_instagram_login_method_facebook_redirects_to_facebook_dialog(monkeypatch):
    """Facebook Login: diálogo de Facebook con los scopes de Página e Instagram, incluido comentarios."""
    monkeypatch.setenv("INSTAGRAM_APP_ID", "fb-app-id")
    monkeypatch.setenv("INSTAGRAM_REDIRECT_URI", "http://localhost:8000/callback/instagram")
    response = client.get("/instagram/login?token=valid_token&method=facebook", follow_redirects=False)
    assert response.status_code in [302, 307]
    location = response.headers.get("location", "")

    assert location.startswith("https://www.facebook.com/v") and "/dialog/oauth?client_id=fb-app-id" in location
    for scope in ("pages_show_list", "instagram_basic", "instagram_manage_insights", "instagram_manage_comments"):
        assert scope in location


def test_instagram_login_rejects_unknown_method(instagram_login_env):
    response = client.get("/instagram/login?token=valid_token&method=twitter", follow_redirects=False)
    assert response.status_code == 422


@pytest.fixture
def facebook_login_env(monkeypatch):
    monkeypatch.setenv("INSTAGRAM_APP_ID", "fb-app-id")
    monkeypatch.setenv("INSTAGRAM_APP_SECRET", "fb-app-secret")
    monkeypatch.setenv("INSTAGRAM_REDIRECT_URI", "http://localhost:8000/callback/instagram")


def _run_facebook_callback(mock_admin_supabase, state_token, pages):
    short = MagicMock(json=MagicMock(return_value={"access_token": "short-lived-token"}))
    gets = [
        MagicMock(json=MagicMock(return_value={"access_token": "long-lived-token", "expires_in": 5184000})),
        MagicMock(json=MagicMock(return_value={"data": pages})),
    ]
    reconnect_by = datetime(2027, 1, 20, tzinfo=timezone.utc)
    with patch("services.instagram_token.requests.post", return_value=short) as mock_post, \
         patch("services.instagram_token.requests.get", side_effect=gets) as mock_get, \
         patch("services.instagram_token.get_reconnect_deadline",
               return_value={"is_valid": True, "reconnect_by": reconnect_by}), \
         patch("services.instagram_token.encrypt_token", side_effect=lambda t: f"enc:{t}"), \
         patch("services.instagram_token.get_supabase_admin_client", return_value=mock_admin_supabase):
        response = client.get(f"/callback/instagram?code=auth_code&state={state_token}", follow_redirects=False)
    return response, mock_post, mock_get


def test_callback_facebook_saves_account_of_first_page_with_instagram(mock_admin_supabase, facebook_login_env):
    pages = [{"id": "page-1"}, {"id": "page-2", "instagram_business_account": {"id": "ig-fb-2"}}]
    state = generate_state_token(USER_ID, login_type="facebook")
    response, mock_post, mock_get = _run_facebook_callback(mock_admin_supabase, state, pages)

    assert response.status_code in [302, 307]
    assert "instagram_connected=true" in response.headers.get("location", "")
    assert "graph.facebook.com" in mock_post.call_args[0][0]
    assert mock_get.call_args_list[0][1]["params"]["grant_type"] == "fb_exchange_token"
    assert mock_get.call_args_list[1][0][0].endswith("/me/accounts")
    payload = mock_admin_supabase.table.return_value.upsert.call_args[0][0]
    assert payload["instagram_business_account_id"] == "ig-fb-2"
    assert payload["login_type"] == "facebook"
    assert payload["expires_at"] == "2027-01-20T00:00:00+00:00"  # fecha de reconexión de debug_token


def test_callback_facebook_reconnect_switches_login_type_on_same_row(mock_admin_supabase, facebook_login_env):
    """Cambiar de Instagram a Facebook Login reconectando la tarjeta conserva la fila (y sus posts)."""
    pages = [{"id": "page-1", "instagram_business_account": {"id": "ig-fb-1"}}]
    state = generate_state_token(USER_ID, account_id="7", login_type="facebook")
    response, _, _ = _run_facebook_callback(mock_admin_supabase, state, pages)

    assert response.status_code in [302, 307]
    mock_admin_supabase.table.return_value.upsert.assert_not_called()
    assert mock_admin_supabase.table.return_value.update.call_args[0][0]["login_type"] == "facebook"
    mock_admin_supabase.table.return_value.update.return_value.eq.assert_any_call("id", "7")


def test_callback_facebook_without_linked_instagram_redirects_to_accounts(mock_admin_supabase, facebook_login_env):
    """Sin Página con Instagram vinculado: vuelve a Cuentas con el motivo, sin guardar nada."""
    state = generate_state_token(USER_ID, login_type="facebook")
    response, _, _ = _run_facebook_callback(mock_admin_supabase, state, [{"id": "page-1"}])

    assert response.status_code in [302, 307]
    assert response.headers["location"].endswith("/accounts?instagram_error=no_linked_page")
    mock_admin_supabase.table.return_value.upsert.assert_not_called()


def test_callback_cancelled_authorization_returns_400_without_saving(mock_admin_supabase):
    """El usuario cancela en Meta: llega ?error=access_denied, no se crea ni modifica ninguna cuenta."""
    with patch("services.instagram_token.requests.post") as mock_post, \
         patch("services.instagram_token.get_supabase_admin_client", return_value=mock_admin_supabase):
        response = client.get(
            f"/callback/instagram?error=access_denied&state={generate_state_token(USER_ID)}", follow_redirects=False
        )

    assert response.status_code == 400
    assert "access_denied" in response.json()["detail"]
    mock_post.assert_not_called()
    mock_admin_supabase.table.assert_not_called()


def test_callback_instagram_missing_params_returns_400():
    """AD-3: /callback/instagram sin code o sin state devuelve 400."""
    res_no_code = client.get("/callback/instagram?state=some-state", follow_redirects=False)
    assert res_no_code.status_code == 400

    res_no_state = client.get("/callback/instagram?code=some-code", follow_redirects=False)
    assert res_no_state.status_code == 400


def test_callback_instagram_stores_login_type_instagram(mock_admin_supabase, instagram_login_env):
    """AD-3: El callback de Instagram Login guarda login_type='instagram' y token cifrado."""
    response, _, _ = _run_callback(mock_admin_supabase, generate_state_token(USER_ID))

    assert response.status_code in [302, 307]
    upsert = mock_admin_supabase.table.return_value.upsert
    upsert_data = upsert.call_args[0][0]
    assert upsert_data["user_id"] == USER_ID
    assert upsert_data["instagram_business_account_id"] == "ig-account-1"
    assert upsert_data["login_type"] == "instagram"
    assert upsert_data["long_lived_access_token"] == "enc:long-lived-token"
    assert upsert_data["token_invalid"] is False
    assert upsert.call_args[1]["on_conflict"] == "user_id,instagram_business_account_id"


def test_instagram_status_includes_login_type(mock_admin_supabase):
    """AD-6: /instagram/status devuelve login_type ('facebook' o 'instagram') para cada cuenta."""
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
            "login_type": "facebook",
        }
    ]
    mock_execute = MagicMock()
    mock_execute.execute.return_value = MagicMock(data=mock_accounts)
    mock_admin_supabase.table.return_value.select.return_value.eq.return_value = mock_execute

    with patch("routes.instagram_routes.get_supabase_admin_client", return_value=mock_admin_supabase):
        response = client.get("/instagram/status")

    assert response.status_code == 200
    accounts = response.json()
    assert len(accounts) == 1
    assert accounts[0]["login_type"] == "facebook"

