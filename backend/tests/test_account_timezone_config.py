"""
Tests para configuración de zonas horarias en cuentas de Instagram (AD-4).
Cubre:
- Guardar primary_timezone y secondary_timezone válidas
- Validación IANA devuelve 422 si la zona no existe
- Reset explícito con null (vía model_fields_set)
- No tocar telegram ni drive cuando solo se configuran zonas
- Guardar detected_timezone reportada por el frontend
- GET /instagram/accounts incluye las tres columnas de zona horaria
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from main import app
from auth.dependencies import get_current_user
from models.schemas import User
from tests.conftest import USER_ID

async def mock_get_current_user():
    return User(id=USER_ID, email="test@example.com")

app.dependency_overrides[get_current_user] = mock_get_current_user
client = TestClient(app)

@pytest.fixture
def mock_admin_supabase():
    with patch("routes.instagram_routes.admin_supabase") as mock_admin_sup:
        yield mock_admin_sup


def test_update_account_timezone_success(mock_admin_supabase):
    # Mock account exists
    mock_admin_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"id": 1}]
    )
    mock_update = MagicMock()
    mock_admin_supabase.table.return_value.update.return_value.eq.return_value = mock_update

    response = client.put(
        "/instagram/accounts/1/config",
        json={"primary_timezone": "Europe/Madrid", "secondary_timezone": "Asia/Kuching"}
    )

    assert response.status_code == 200
    assert response.json() == {"success": True}
    update_data = mock_admin_supabase.table.return_value.update.call_args[0][0]
    assert update_data["primary_timezone"] == "Europe/Madrid"
    assert update_data["secondary_timezone"] == "Asia/Kuching"


def test_update_account_timezone_invalid_iana_returns_422(mock_admin_supabase):
    mock_admin_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"id": 1}]
    )

    # primary_timezone inválida
    response_primary = client.put(
        "/instagram/accounts/1/config",
        json={"primary_timezone": "Invalid/NonExistent_Zone"}
    )
    assert response_primary.status_code == 422

    # secondary_timezone inválida
    response_sec = client.put(
        "/instagram/accounts/1/config",
        json={"secondary_timezone": "Mars/Base_Station"}
    )
    assert response_sec.status_code == 422


def test_update_account_timezone_reset_with_explicit_null(mock_admin_supabase):
    mock_admin_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"id": 1}]
    )
    mock_update = MagicMock()
    mock_admin_supabase.table.return_value.update.return_value.eq.return_value = mock_update

    # null explícito en primary y secondary para volver al navegador y quitar secundaria
    response = client.put(
        "/instagram/accounts/1/config",
        json={"primary_timezone": None, "secondary_timezone": None}
    )

    assert response.status_code == 200
    update_data = mock_admin_supabase.table.return_value.update.call_args[0][0]
    assert "primary_timezone" in update_data and update_data["primary_timezone"] is None
    assert "secondary_timezone" in update_data and update_data["secondary_timezone"] is None


def test_update_account_timezone_does_not_touch_telegram_or_drive(mock_admin_supabase):
    mock_admin_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"id": 1}]
    )
    mock_update = MagicMock()
    mock_admin_supabase.table.return_value.update.return_value.eq.return_value = mock_update

    with patch("services.drive_webhook_service.register_channel") as mock_register:
        response = client.put(
            "/instagram/accounts/1/config",
            json={"primary_timezone": "Europe/Madrid"}
        )

        assert response.status_code == 200
        update_data = mock_admin_supabase.table.return_value.update.call_args[0][0]
        assert "telegram_chat_id" not in update_data
        assert "drive_folder_id" not in update_data
        mock_register.assert_not_called()


def test_update_account_detected_timezone(mock_admin_supabase):
    mock_admin_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"id": 1}]
    )
    mock_update = MagicMock()
    mock_admin_supabase.table.return_value.update.return_value.eq.return_value = mock_update

    response = client.put(
        "/instagram/accounts/1/config",
        json={"detected_timezone": "Asia/Kuching"}
    )

    assert response.status_code == 200
    update_data = mock_admin_supabase.table.return_value.update.call_args[0][0]
    assert update_data["detected_timezone"] == "Asia/Kuching"


def test_get_instagram_accounts_includes_timezone_columns(mock_admin_supabase):
    mock_accounts = [
        {
            "id": 1,
            "instagram_business_account_id": "ig-123",
            "username": "brand_account",
            "account_name": "Brand",
            "followers_count": 500,
            "profile_picture_url": "http://img.url/1.png",
            "expires_at": "2026-12-31T23:59:59Z",
            "is_active": True,
            "telegram_chat_id": None,
            "drive_folder_id": None,
            "token_invalid": False,
            "sector": "tech",
            "primary_timezone": "Europe/Madrid",
            "secondary_timezone": "Asia/Kuching",
            "detected_timezone": "Europe/Madrid",
        }
    ]

    mock_select = MagicMock()
    mock_select.execute.return_value = MagicMock(data=mock_accounts)
    mock_admin_supabase.table.return_value.select.return_value.eq.return_value = mock_select

    response = client.get("/instagram/accounts")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["primary_timezone"] == "Europe/Madrid"
    assert data[0]["secondary_timezone"] == "Asia/Kuching"
    assert data[0]["detected_timezone"] == "Europe/Madrid"

    # Verificar que el SELECT incluye las columnas de zona
    select_query = mock_admin_supabase.table.return_value.select.call_args[0][0]
    assert "primary_timezone" in select_query
    assert "secondary_timezone" in select_query
    assert "detected_timezone" in select_query
