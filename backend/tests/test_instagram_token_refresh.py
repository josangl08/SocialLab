"""
Tests para renovación diaria de tokens de Instagram Login (AD-5).
Cubre:
- renueva y actualiza expires_at
- error OAuth 190 -> token_invalid=True
- error de red -> sin cambios en la fila
- fallo en una cuenta no corta las demás
- segunda ejecución no realiza llamadas (idempotencia)
- cuentas facebook ignoradas
- solo se seleccionan tokens que caducan en < 15 días
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from services.instagram_token import refresh_expiring_tokens


def test_refresh_expiring_tokens_success():
    """AD-5: Una cuenta 'instagram' que vence en < 15 días renueva su token y actualiza expires_at."""
    expiring_account = {
        "id": 1,
        "login_type": "instagram",
        "long_lived_access_token": "enc-old-token",
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=5)).isoformat(),
        "is_active": True,
        "token_invalid": False,
    }
    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.lt.return_value.execute.return_value.data = [
        expiring_account
    ]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"access_token": "new-long-token", "expires_in": 5184000}

    with patch("services.instagram_token.get_supabase_admin_client", return_value=mock_db), \
         patch("services.instagram_token.decrypt_token", return_value="plain-old-token"), \
         patch("services.instagram_token.encrypt_token", return_value="enc-new-token"), \
         patch("services.instagram_token.requests.get", return_value=mock_resp) as mock_get:
        
        result = refresh_expiring_tokens()

    assert result.get("refreshed") == 1
    assert mock_get.called
    assert "graph.instagram.com/refresh_access_token" in mock_get.call_args[0][0]
    assert mock_db.table.return_value.update.called


def test_refresh_expiring_tokens_oauth_190_marks_invalid():
    """AD-5: Error 190 marca la cuenta como token_invalid=True."""
    expiring_account = {
        "id": 2,
        "login_type": "instagram",
        "long_lived_access_token": "enc-revoked-token",
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=5)).isoformat(),
        "is_active": True,
        "token_invalid": False,
    }
    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.lt.return_value.execute.return_value.data = [
        expiring_account
    ]

    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.json.return_value = {"error": {"code": 190, "message": "Error validating access token"}}

    with patch("services.instagram_token.get_supabase_admin_client", return_value=mock_db), \
         patch("services.instagram_token.decrypt_token", return_value="plain-token"), \
         patch("services.instagram_token.requests.get", return_value=mock_resp):
        
        result = refresh_expiring_tokens()

    assert result.get("invalidated") == 1
    mock_db.table.return_value.update.assert_called_with({"token_invalid": True})


def test_refresh_expiring_tokens_network_error_leaves_row_untouched():
    """AD-5: Error de red o 5xx no toca la fila de la cuenta."""
    import requests
    expiring_account = {
        "id": 3,
        "login_type": "instagram",
        "long_lived_access_token": "enc-token",
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=5)).isoformat(),
        "is_active": True,
        "token_invalid": False,
    }
    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.lt.return_value.execute.return_value.data = [
        expiring_account
    ]

    with patch("services.instagram_token.get_supabase_admin_client", return_value=mock_db), \
         patch("services.instagram_token.decrypt_token", return_value="plain-token"), \
         patch("services.instagram_token.requests.get", side_effect=requests.RequestException("Network down")):
        
        result = refresh_expiring_tokens()

    assert result.get("refreshed", 0) == 0
    assert result.get("invalidated", 0) == 0
    mock_db.table.return_value.update.assert_not_called()


def test_refresh_expiring_tokens_error_isolation():
    """AD-5: Un fallo en una cuenta no interrumpe el procesamiento de las siguientes."""
    accounts = [
        {
            "id": 10,
            "login_type": "instagram",
            "long_lived_access_token": "enc-1",
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
            "is_active": True,
            "token_invalid": False,
        },
        {
            "id": 11,
            "login_type": "instagram",
            "long_lived_access_token": "enc-2",
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
            "is_active": True,
            "token_invalid": False,
        },
    ]
    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.lt.return_value.execute.return_value.data = accounts

    import requests
    mock_resp_ok = MagicMock()
    mock_resp_ok.status_code = 200
    mock_resp_ok.json.return_value = {"access_token": "new-2", "expires_in": 5184000}

    with patch("services.instagram_token.get_supabase_admin_client", return_value=mock_db), \
         patch("services.instagram_token.decrypt_token", return_value="token"), \
         patch("services.instagram_token.encrypt_token", return_value="enc-new"), \
         patch("services.instagram_token.requests.get", side_effect=[requests.RequestException("fail"), mock_resp_ok]):
        
        result = refresh_expiring_tokens()

    assert result.get("refreshed") == 1


def test_refresh_expiring_tokens_ignores_facebook_accounts():
    """AD-5: El filtro selecciona login_type='instagram'; las cuentas 'facebook' nunca se renuevan."""
    mock_db = MagicMock()
    query_chain = mock_db.table.return_value.select.return_value
    query_chain.eq.return_value = query_chain
    query_chain.lt.return_value.execute.return_value.data = []

    with patch("services.instagram_token.get_supabase_admin_client", return_value=mock_db):
        result = refresh_expiring_tokens()

    # Verificar que se filtró por login_type == 'instagram'
    calls = [c[0] for c in query_chain.eq.call_args_list]
    assert ("login_type", "instagram") in calls


def test_refresh_expiring_tokens_second_run_makes_no_calls():
    """AD-5: Tras renovar, la cuenta sale del filtro: una segunda ejecución no llama a Instagram."""
    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.lt.return_value.execute.return_value.data = []

    with patch("services.instagram_token.get_supabase_admin_client", return_value=mock_db), \
         patch("services.instagram_token.requests.get") as mock_get:
        result = refresh_expiring_tokens()

    mock_get.assert_not_called()
    assert result == {"refreshed": 0, "invalidated": 0, "skipped": 0}


def test_refresh_expiring_tokens_selects_only_tokens_expiring_within_15_days():
    """Solo entran las cuentas instagram activas, válidas y con < 15 días: las que tienen
    validez de sobra no se tocan."""
    mock_db = MagicMock()
    query_chain = mock_db.table.return_value.select.return_value
    query_chain.eq.return_value = query_chain
    query_chain.lt.return_value.execute.return_value.data = []

    before = datetime.now(timezone.utc)
    with patch("services.instagram_token.get_supabase_admin_client", return_value=mock_db), \
         patch("services.instagram_token.requests.get") as mock_get:
        refresh_expiring_tokens()
    after = datetime.now(timezone.utc)

    eq_calls = {c[0] for c in query_chain.eq.call_args_list}
    assert eq_calls == {("login_type", "instagram"), ("token_invalid", False), ("is_active", True)}
    column, threshold = query_chain.lt.call_args[0]
    assert column == "expires_at"
    threshold = datetime.fromisoformat(threshold)
    assert before + timedelta(days=15) <= threshold <= after + timedelta(days=15)
    mock_get.assert_not_called()
