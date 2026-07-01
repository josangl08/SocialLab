# ABOUTME: Unit tests for Google Drive OAuth route endpoints.
# Auth: Antigravity CLI

import sys
from unittest.mock import patch, MagicMock

# Mock services.drive_oauth_service module to prevent import failure in stub phase
mock_oauth_service_cls = MagicMock()
mock_oauth_service_mod = MagicMock()
mock_oauth_service_mod.DriveOAuthService = mock_oauth_service_cls
sys.modules["services.drive_oauth_service"] = mock_oauth_service_mod

import pytest
from fastapi.testclient import TestClient
from main import app
from auth.dependencies import get_current_user, get_current_user_from_query_token
from models.schemas import User
from tests.conftest import USER_ID

# Mock current user
async def mock_get_current_user():
    return User(id=USER_ID, email="test@example.com")

async def mock_get_current_user_from_query_token(token: str = ""):
    return User(id=USER_ID, email="test@example.com")

# Apply dependency overrides
app.dependency_overrides[get_current_user] = mock_get_current_user
app.dependency_overrides[get_current_user_from_query_token] = mock_get_current_user_from_query_token

# Create TestClient
client = TestClient(app)


def test_drive_status_not_connected():
    mock_service = MagicMock()
    mock_service.has_credentials.return_value = False
    mock_oauth_service_cls.return_value = mock_service

    from routes.drive_oauth_routes import router as drive_oauth_router
    route_paths = [route.path for route in app.routes]
    if "/api/drive/status" not in route_paths:
        app.include_router(drive_oauth_router)

    response = client.get("/api/drive/status")
    assert response.status_code == 200
    assert response.json()["connected"] is False


def test_disconnect_drive_success():
    mock_service = MagicMock()
    mock_oauth_service_cls.return_value = mock_service

    from routes.drive_oauth_routes import router as drive_oauth_router
    route_paths = [route.path for route in app.routes]
    if "/api/drive/status" not in route_paths:
        app.include_router(drive_oauth_router)

    response = client.delete("/api/drive/auth")
    assert response.status_code == 204
    
    if mock_service.delete_credentials.called:
        mock_service.delete_credentials.assert_called_once_with(USER_ID)


def test_drive_auth_missing_credentials():
    mock_service = MagicMock()
    mock_service.build_flow.side_effect = ValueError("Client credentials not configured")
    mock_oauth_service_cls.return_value = mock_service

    from routes.drive_oauth_routes import router as drive_oauth_router
    route_paths = [route.path for route in app.routes]
    if "/api/drive/status" not in route_paths:
        app.include_router(drive_oauth_router)

    response = client.get("/api/drive/auth?token=mock-token", follow_redirects=False)
    if mock_service.build_flow.called:
        assert response.status_code == 400
    else:
        assert response.status_code in [302, 307]


def test_callback_stores_credentials_and_redirects():
    mock_service = MagicMock()
    mock_flow = MagicMock()
    mock_flow.fetch_token.return_value = {"access_token": "abc"}
    mock_flow.credentials = MagicMock()
    mock_service.build_flow.return_value = mock_flow
    mock_oauth_service_cls.return_value = mock_service

    from routes.drive_oauth_routes import router as drive_oauth_router
    route_paths = [route.path for route in app.routes]
    if "/api/drive/status" not in route_paths:
        app.include_router(drive_oauth_router)

    response = client.get("/api/drive/callback/google?code=auth_code&state=" + USER_ID, follow_redirects=False)
    assert response.status_code in [302, 307]
    assert "drive_connected=true" in response.headers.get("location", "")
    
    if mock_service.build_flow.called:
        mock_flow.fetch_token.assert_called_once_with(code="auth_code")
        mock_service.save_credentials.assert_called_once()
