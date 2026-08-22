import pytest
import asyncio
from unittest.mock import MagicMock, patch
from mcp.drive_server import mcp, drive_list_files, drive_download_file

def test_drive_list_files_direct():
    with patch("mcp.drive_server.get_drive_connector") as mock_get_connector:
        mock_connector = MagicMock()
        mock_connector.list_files.return_value = [{"id": "1", "name": "file.jpg"}]
        mock_get_connector.return_value = mock_connector

        result = drive_list_files(user_id="user_123", folder_id="folder_456", mime_type="image/jpeg", limit=50)

        assert result == [{"id": "1", "name": "file.jpg"}]
        mock_get_connector.assert_called_once_with("user_123")
        mock_connector.list_files.assert_called_once_with(folder_id="folder_456", mime_type="image/jpeg", limit=50)

def test_drive_download_file_direct():
    with patch("mcp.drive_server.get_drive_connector") as mock_get_connector:
        mock_connector = MagicMock()
        mock_connector.download_file.return_value = True
        mock_get_connector.return_value = mock_connector

        result = drive_download_file(user_id="user_123", file_id="file_abc", destination_path="/tmp/file.jpg")

        assert result is True
        mock_get_connector.assert_called_once_with("user_123")
        mock_connector.download_file.assert_called_once_with(file_id="file_abc", destination_path="/tmp/file.jpg")

@pytest.mark.asyncio
async def test_drive_list_files_via_mcp():
    with patch("mcp.drive_server.get_drive_connector") as mock_get_connector:
        mock_connector = MagicMock()
        mock_connector.list_files.return_value = [{"id": "1", "name": "file.jpg"}]
        mock_get_connector.return_value = mock_connector

        response = await mcp.call_tool("drive_list_files", {"user_id": "user_123"})
        
        assert len(response) == 1
        assert response[0].type == "text"
        assert "file.jpg" in response[0].text
