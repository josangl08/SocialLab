import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from services.drive_webhook_service import (
    register_channel,
    renew_expiring_channels,
    handle_notification,
    analyze_new_files_fast_path,
)


def test_register_channel_returns_none_when_account_not_found():
    with patch("services.drive_webhook_service.get_supabase_admin_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

        result = register_channel(999, "folder-abc")

        assert result is None


def test_register_channel_returns_none_when_drive_not_connected():
    with patch("services.drive_webhook_service.get_supabase_admin_client") as mock_get_client, \
         patch("services.drive_webhook_service.get_drive_connector", side_effect=RuntimeError("no creds")):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"user_id": "user-1"}]
        )

        result = register_channel(7, "folder-abc")

        assert result is None


def test_register_channel_persists_row_on_success():
    with patch("services.drive_webhook_service.get_supabase_admin_client") as mock_get_client, \
         patch("services.drive_webhook_service.get_drive_connector") as mock_get_connector:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"user_id": "user-1"}]
        )

        mock_connector = MagicMock()
        mock_connector.watch_folder.return_value = {
            "channel_id": "chan-1",
            "resource_id": "res-1",
            "expiration": "1893456000000",  # ms epoch
        }
        mock_get_connector.return_value = mock_connector

        result = register_channel(7, "folder-abc")

        assert result["channel_id"] == "chan-1"
        mock_client.table.return_value.delete.return_value.eq.assert_called_once_with("account_id", 7)
        insert_payload = mock_client.table.return_value.insert.call_args[0][0]
        assert insert_payload["account_id"] == 7
        assert insert_payload["channel_id"] == "chan-1"
        assert insert_payload["resource_id"] == "res-1"
        assert insert_payload["folder_id"] == "folder-abc"


def test_renew_expiring_channels_reregisters_each_expiring_row():
    with patch("services.drive_webhook_service.get_supabase_admin_client") as mock_get_client, \
         patch("services.drive_webhook_service.register_channel") as mock_register:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.table.return_value.select.return_value.lte.return_value.execute.return_value = MagicMock(
            data=[{"account_id": 7, "folder_id": "f1"}, {"account_id": 8, "folder_id": "f2"}]
        )
        mock_register.side_effect = [{"channel_id": "c1"}, None]

        renewed = renew_expiring_channels()

        assert renewed == 1
        assert mock_register.call_count == 2


def test_handle_notification_ignores_unknown_channel():
    with patch("services.drive_webhook_service.get_supabase_admin_client") as mock_get_client, \
         patch("services.drive_webhook_service.analyze_new_files_fast_path") as mock_analyze:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

        handle_notification("unknown-channel", "add", "some-token")

        mock_analyze.assert_not_called()


def test_handle_notification_rejects_token_mismatch():
    with patch("services.drive_webhook_service.get_supabase_admin_client") as mock_get_client, \
         patch("services.drive_webhook_service.analyze_new_files_fast_path") as mock_analyze:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"account_id": 7, "folder_id": "f1", "channel_token": "real-token"}]
        )

        handle_notification("chan-1", "add", "wrong-token")

        mock_analyze.assert_not_called()


def test_handle_notification_ignores_sync_state():
    with patch("services.drive_webhook_service.get_supabase_admin_client") as mock_get_client, \
         patch("services.drive_webhook_service.analyze_new_files_fast_path") as mock_analyze:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"account_id": 7, "folder_id": "f1", "channel_token": "real-token"}]
        )

        handle_notification("chan-1", "sync", "real-token")

        mock_analyze.assert_not_called()


def test_handle_notification_triggers_analysis_on_valid_add():
    with patch("services.drive_webhook_service.get_supabase_admin_client") as mock_get_client, \
         patch("services.drive_webhook_service.analyze_new_files_fast_path") as mock_analyze:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"account_id": 7, "folder_id": "f1", "channel_token": "real-token"}]
        )

        handle_notification("chan-1", "add", "real-token")

        mock_analyze.assert_called_once_with(7, "f1")


def test_analyze_new_files_fast_path_skips_already_analyzed_images():
    with patch("services.drive_webhook_service.get_supabase_admin_client") as mock_get_client, \
         patch("services.drive_webhook_service.get_drive_connector") as mock_get_connector, \
         patch("services.drive_webhook_service.analyze_image_vision") as mock_analyze_vision:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        def select_side_effect(*args, **kwargs):
            m = MagicMock()
            return m

        acc_select = MagicMock()
        acc_select.eq.return_value.execute.return_value = MagicMock(data=[{"user_id": "user-1"}])

        existing_select = MagicMock()
        existing_select.eq.return_value.execute.return_value = MagicMock(data=[{"drive_file_id": "already-1"}])

        mock_client.table.side_effect = lambda name: {
            "instagram_accounts": MagicMock(select=MagicMock(return_value=acc_select)),
            "visual_analyses": MagicMock(select=MagicMock(return_value=existing_select), insert=MagicMock(return_value=MagicMock(execute=MagicMock()))),
        }[name]

        mock_connector = MagicMock()
        mock_connector.list_files.return_value = [
            {"id": "already-1", "mimeType": "image/jpeg", "name": "a.jpg"},
            {"id": "new-1", "mimeType": "image/jpeg", "name": "b.jpg"},
        ]
        mock_connector.download_file_bytes.return_value = b"fake-bytes"
        mock_get_connector.return_value = mock_connector

        async def fake_analyze(*args, **kwargs):
            return {"theme": "test", "suggested_caption": "caption"}
        mock_analyze_vision.side_effect = fake_analyze

        count = analyze_new_files_fast_path(7, "folder-abc")

        assert count == 1
        mock_connector.download_file_bytes.assert_called_once_with("new-1")


def test_analyze_new_files_fast_path_returns_zero_when_no_account():
    with patch("services.drive_webhook_service.get_supabase_admin_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

        assert analyze_new_files_fast_path(999, "folder-abc") == 0
