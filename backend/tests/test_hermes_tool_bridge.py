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
