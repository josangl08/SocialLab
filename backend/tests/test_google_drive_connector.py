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
