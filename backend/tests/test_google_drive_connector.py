# ABOUTME: Unit tests for Google Drive connector.
# Auth: Antigravity CLI

import io
import pytest
from unittest.mock import MagicMock, patch
from services.google_drive_connector import GoogleDriveConnector

def test_download_file_bytes_success():
    connector = GoogleDriveConnector()
    connector.service = MagicMock()
    
    dummy_bytes = b"hello google drive bytes"
    
    mock_request = MagicMock()
    connector.service.files().get_media.return_value = mock_request
    
    with patch("services.google_drive_connector.MediaIoBaseDownload") as mock_downloader_cls:
        mock_downloader = MagicMock()
        
        def next_chunk_side_effect():
            stream = mock_downloader_cls.call_args[0][0]
            stream.write(dummy_bytes)
            return None, True
            
        mock_downloader.next_chunk.side_effect = next_chunk_side_effect
        mock_downloader_cls.return_value = mock_downloader
        
        result = connector.download_file_bytes("test_file_id")
        
        assert result == dummy_bytes
        connector.service.files().get_media.assert_called_once_with(fileId="test_file_id")
        
        args, kwargs = mock_downloader_cls.call_args
        assert isinstance(args[0], io.BytesIO)
        assert args[1] == mock_request

def test_download_file_bytes_failure():
    connector = GoogleDriveConnector()
    connector.service = MagicMock()

    connector.service.files().get_media.side_effect = Exception("Drive API Error")

    result = connector.download_file_bytes("test_file_id")
    assert result is None


def test_watch_folder_returns_channel_id_resource_id_and_expiration():
    connector = GoogleDriveConnector()
    connector.service = MagicMock()
    connector.service.files().watch.return_value.execute.return_value = {
        "id": "chan-1",
        "resourceId": "res-1",
        "expiration": "1893456000000",
    }

    result = connector.watch_folder("folder-abc", "https://example.com/webhook", "chan-1", "tok-1")

    assert result == {"channel_id": "chan-1", "resource_id": "res-1", "expiration": "1893456000000"}
    call_kwargs = connector.service.files().watch.call_args
    assert call_kwargs[1]["fileId"] == "folder-abc"
    assert call_kwargs[1]["body"] == {
        "id": "chan-1",
        "type": "web_hook",
        "address": "https://example.com/webhook",
        "token": "tok-1",
    }


def test_watch_folder_returns_none_on_failure():
    connector = GoogleDriveConnector()
    connector.service = MagicMock()
    connector.service.files().watch.side_effect = Exception("Drive API Error")

    result = connector.watch_folder("folder-abc", "https://example.com/webhook", "chan-1", "tok-1")

    assert result is None


def test_stop_channel_success():
    connector = GoogleDriveConnector()
    connector.service = MagicMock()

    result = connector.stop_channel("chan-1", "res-1")

    assert result is True
    connector.service.channels().stop.assert_called_once_with(body={"id": "chan-1", "resourceId": "res-1"})


def test_stop_channel_failure():
    connector = GoogleDriveConnector()
    connector.service = MagicMock()
    connector.service.channels().stop.side_effect = Exception("Drive API Error")

    result = connector.stop_channel("chan-1", "res-1")

    assert result is False
