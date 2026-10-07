from typing import Optional, List, Dict
from mcp.server.mcpserver import MCPServer
from services.google_drive_connector import get_drive_connector

mcp = MCPServer("Google Drive Server")

@mcp.tool()
def drive_list_files(
    user_id: str,
    folder_id: Optional[str] = None,
    mime_type: Optional[str] = None,
    limit: int = 100
) -> List[Dict]:
    """List files from Google Drive for a specific user."""
    drive = get_drive_connector(user_id)
    return drive.list_files(folder_id=folder_id, mime_type=mime_type, limit=limit)

@mcp.tool()
def drive_download_file(
    user_id: str,
    file_id: str,
    destination_path: str
) -> bool:
    """Download a specific file from Google Drive for a user to a local path."""
    drive = get_drive_connector(user_id)
    return drive.download_file(file_id=file_id, destination_path=destination_path)
