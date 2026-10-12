import pytest
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock
from mcp.server.mcpserver import MCPServer
from services.hermes.tool_bridge import ToolBridge
from google.genai.types import FunctionDeclaration

class MockTool:
    def __init__(self, name, description, input_schema):
        self.name = name
        self.description = description
        self.input_schema = input_schema

@pytest.mark.asyncio
async def test_discover_tools_filters_account_id():
    # Mock MCP tools
    tool1 = MockTool(
        name="supabase_get_posts",
        description="Retrieve posts",
        input_schema={
            "properties": {
                "instagram_account_id": {"type": "integer"},
                "limit": {"type": "integer"}
            },
            "required": ["instagram_account_id"]
        }
    )
    
    tool2 = MockTool(
        name="supabase_write_agent_log",
        description="Write agent log",
        input_schema={
            "properties": {
                "account_id": {"type": "integer"},
                "images_scanned": {"type": "integer"}
            },
            "required": ["account_id", "images_scanned"]
        }
    )
    
    mock_server = MagicMock()
    mock_server.list_tools = AsyncMock(return_value=[tool1, tool2])
    
    bridge = ToolBridge(mcp_servers=[mock_server])
    decls = await bridge.discover_tools()
    
    assert len(decls) == 2
    assert all(isinstance(d, FunctionDeclaration) for d in decls)
    
    # Verify that account_id and instagram_account_id are not in declaration parameters
    d1 = next(d for d in decls if d.name == "supabase_get_posts")
    assert "instagram_account_id" not in d1.parameters.properties
    assert "limit" in d1.parameters.properties
    assert "instagram_account_id" not in (d1.parameters.required or [])
    
    d2 = next(d for d in decls if d.name == "supabase_write_agent_log")
    assert "account_id" not in d2.parameters.properties
    assert "images_scanned" in d2.parameters.properties
    assert "account_id" not in getattr(d2.parameters, "required", [])

@pytest.mark.asyncio
async def test_dispatch_injects_account_id():
    tool1 = MockTool(
        name="supabase_get_posts",
        description="Retrieve posts",
        input_schema={
            "properties": {
                "instagram_account_id": {"type": "integer"},
                "limit": {"type": "integer"}
            },
            "required": ["instagram_account_id"]
        }
    )
    
    mock_server = MagicMock()
    mock_server.list_tools = AsyncMock(return_value=[tool1])
    mock_server.call_tool = AsyncMock(return_value="tool_result")
    
    bridge = ToolBridge(mcp_servers=[mock_server])
    await bridge.discover_tools() # populate tools_map
    
    # Model sends some args, maybe even tries to inject a malicious instagram_account_id
    model_args = {"limit": 5, "instagram_account_id": 999}
    
    # We call dispatch with session's account_id = 42
    result = await bridge.dispatch("supabase_get_posts", model_args, account_id=42)

    assert result == "tool_result"
    # Verify that mock_server.call_tool was called with instagram_account_id = 42
    mock_server.call_tool.assert_called_once_with("supabase_get_posts", {
        "limit": 5,
        "instagram_account_id": 42
    })


# ── Real (non-mocked) MCPServer integration ─────────────────────────────────
# MCPServer.call_tool() always wraps the tool's return value in a CallToolResult
# (MCP wire format), even for in-process calls — no test above exercises that real
# server, so it never caught dispatch() leaking raw TextContent into callers
# (which blows up Gemini function responses with "Object of type TextContent is
# not JSON serializable"). These hit a real MCPServer instance to close that gap.

real_mcp = MCPServer("Test Server")


@real_mcp.tool()
def echo_dict(instagram_account_id: int) -> dict:
    """Returns a dict."""
    return {"id": instagram_account_id, "name": "test"}


@real_mcp.tool()
def echo_list(instagram_account_id: int) -> list:
    """Returns a list of dicts."""
    return [{"id": 1}, {"id": 2}]


@real_mcp.tool()
def echo_empty_list(instagram_account_id: int) -> list:
    """Returns an empty list."""
    return []


@real_mcp.tool()
def echo_single_item_list(instagram_account_id: int) -> List[Dict[str, Any]]:
    """Returns a one-element list (wrapped as {"result": [...]} by MCP)."""
    return [{"id": 1}]


@real_mcp.tool()
def echo_optional_none(instagram_account_id: int) -> Optional[Dict[str, Any]]:
    """Returns None."""
    return None


@real_mcp.tool()
def echo_builtin_dict(instagram_account_id: int) -> dict[str, Any]:
    """Returns a dict (not wrapped by MCP)."""
    return {"id": instagram_account_id}


@pytest.mark.asyncio
async def test_dispatch_unwraps_real_mcp_dict_result():
    bridge = ToolBridge(mcp_servers=[real_mcp])
    await bridge.discover_tools()

    result = await bridge.dispatch("echo_dict", {}, account_id=7)

    assert result == {"id": 7, "name": "test"}


@pytest.mark.asyncio
async def test_dispatch_unwraps_real_mcp_list_result():
    bridge = ToolBridge(mcp_servers=[real_mcp])
    await bridge.discover_tools()

    result = await bridge.dispatch("echo_list", {}, account_id=7)

    assert result == [{"id": 1}, {"id": 2}]


@pytest.mark.asyncio
async def test_dispatch_unwraps_real_mcp_empty_list_result():
    bridge = ToolBridge(mcp_servers=[real_mcp])
    await bridge.discover_tools()

    result = await bridge.dispatch("echo_empty_list", {}, account_id=7)

    assert result == []


@pytest.mark.asyncio
async def test_dispatch_keeps_single_item_list_as_list():
    bridge = ToolBridge(mcp_servers=[real_mcp])
    await bridge.discover_tools()

    result = await bridge.dispatch("echo_single_item_list", {}, account_id=7)

    assert result == [{"id": 1}]


@pytest.mark.asyncio
async def test_dispatch_returns_none_for_optional_none():
    bridge = ToolBridge(mcp_servers=[real_mcp])
    await bridge.discover_tools()

    result = await bridge.dispatch("echo_optional_none", {}, account_id=7)

    assert result is None


@pytest.mark.asyncio
async def test_dispatch_unwraps_unwrapped_structured_dict():
    bridge = ToolBridge(mcp_servers=[real_mcp])
    await bridge.discover_tools()

    result = await bridge.dispatch("echo_builtin_dict", {}, account_id=7)

    assert result == {"id": 7}


# --- Alcance de Drive: Hermes solo puede usar la carpeta de Drive de la cuenta ---

drive_mcp_test = MCPServer("Drive Scope Test Server")
drive_calls: List[Dict[str, Any]] = []


@drive_mcp_test.tool()
def drive_list_files(user_id: str, folder_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    """Lists files."""
    drive_calls.append({"tool": "drive_list_files", "user_id": user_id, "folder_id": folder_id})
    return [{"id": "in-folder-1", "name": "a.jpg"}]


@drive_mcp_test.tool()
def supabase_create_post(instagram_account_id: int, caption: str, drive_file_id: Optional[str] = None) -> Dict[str, Any]:
    """Creates a post."""
    drive_calls.append({"tool": "supabase_create_post", "drive_file_id": drive_file_id})
    return {"id": 1}


@pytest.fixture
def drive_bridge(monkeypatch):
    drive_calls.clear()
    bridge = ToolBridge(mcp_servers=[drive_mcp_test])
    monkeypatch.setattr(bridge, "_get_drive_scope", lambda account_id: ("user-real", "folder-real"))
    return bridge


def _mock_drive_parents(monkeypatch, parents_by_file: Dict[str, List[str]]):
    service = MagicMock()
    service.files.return_value.get.side_effect = lambda fileId, fields: MagicMock(
        execute=MagicMock(return_value={"parents": parents_by_file.get(fileId, [])})
    )
    connector = MagicMock(service=service)
    monkeypatch.setattr("services.google_drive_connector.get_drive_connector", lambda user_id: connector)
    return service


@pytest.mark.asyncio
async def test_drive_list_files_forced_to_account_folder(drive_bridge):
    await drive_bridge.discover_tools()

    await drive_bridge.dispatch("drive_list_files", {"user_id": "otro", "folder_id": "carpeta-ajena"}, account_id=7)
    await drive_bridge.dispatch("drive_list_files", {"user_id": "otro"}, account_id=7)

    assert drive_calls == [
        {"tool": "drive_list_files", "user_id": "user-real", "folder_id": "folder-real"},
        {"tool": "drive_list_files", "user_id": "user-real", "folder_id": "folder-real"},
    ]


@pytest.mark.asyncio
async def test_drive_tools_refused_without_configured_folder(monkeypatch):
    drive_calls.clear()
    bridge = ToolBridge(mcp_servers=[drive_mcp_test])
    monkeypatch.setattr(bridge, "_get_drive_scope", lambda account_id: ("user-real", None))
    await bridge.discover_tools()

    result = await bridge.dispatch("drive_list_files", {"user_id": "user-real"}, account_id=7)

    assert "error" in result
    assert drive_calls == []


@pytest.mark.asyncio
async def test_create_post_with_listed_file_skips_drive_check(drive_bridge, monkeypatch):
    service = _mock_drive_parents(monkeypatch, {})
    await drive_bridge.discover_tools()

    await drive_bridge.dispatch("drive_list_files", {"user_id": "x"}, account_id=7)
    result = await drive_bridge.dispatch("supabase_create_post", {"caption": "c", "drive_file_id": "in-folder-1"}, account_id=7)

    assert result == {"id": 1}
    service.files.return_value.get.assert_not_called()


@pytest.mark.asyncio
async def test_create_post_with_file_from_folder_checked_in_drive(drive_bridge, monkeypatch):
    _mock_drive_parents(monkeypatch, {"old-analysis": ["folder-real"]})
    await drive_bridge.discover_tools()

    result = await drive_bridge.dispatch("supabase_create_post", {"caption": "c", "drive_file_id": "old-analysis"}, account_id=7)

    assert result == {"id": 1}


@pytest.mark.asyncio
async def test_create_post_with_file_outside_folder_is_refused(drive_bridge, monkeypatch):
    _mock_drive_parents(monkeypatch, {"shared-photo": ["folder-de-otro-usuario"]})
    await drive_bridge.discover_tools()

    result = await drive_bridge.dispatch("supabase_create_post", {"caption": "c", "drive_file_id": "shared-photo"}, account_id=7)

    assert "error" in result
    assert not any(c["tool"] == "supabase_create_post" for c in drive_calls)


@pytest.mark.asyncio
async def test_proposal_slot_image_outside_folder_is_refused(drive_bridge, monkeypatch):
    _mock_drive_parents(monkeypatch, {"shared-photo": ["folder-de-otro-usuario"]})
    await drive_bridge.discover_tools()

    ids = drive_bridge._referenced_file_ids({"slots": [{"day": "Monday", "image_id": "shared-photo"}]})

    assert ids == ["shared-photo"]
    assert await drive_bridge._file_in_folder(7, "shared-photo") is False
