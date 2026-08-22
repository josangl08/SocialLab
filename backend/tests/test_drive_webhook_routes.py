from unittest.mock import patch
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_drive_webhook_returns_200_immediately_even_before_background_completes():
    with patch("routes.drive_webhook_routes.drive_webhook_service.handle_notification") as mock_handle:
        response = client.post(
            "/api/drive/webhook",
            headers={
                "X-Goog-Channel-Id": "chan-1",
                "X-Goog-Resource-State": "add",
                "X-Goog-Channel-Token": "tok-1",
            },
        )

        assert response.status_code == 200
        mock_handle.assert_called_once_with("chan-1", "add", "tok-1")


def test_drive_webhook_returns_200_and_skips_dispatch_when_headers_missing():
    with patch("routes.drive_webhook_routes.drive_webhook_service.handle_notification") as mock_handle:
        response = client.post("/api/drive/webhook")

        assert response.status_code == 200
        mock_handle.assert_not_called()


def test_drive_webhook_defaults_missing_token_to_empty_string():
    with patch("routes.drive_webhook_routes.drive_webhook_service.handle_notification") as mock_handle:
        response = client.post(
            "/api/drive/webhook",
            headers={
                "X-Goog-Channel-Id": "chan-1",
                "X-Goog-Resource-State": "sync",
            },
        )

        assert response.status_code == 200
        mock_handle.assert_called_once_with("chan-1", "sync", "")
