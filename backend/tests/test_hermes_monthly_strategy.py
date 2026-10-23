import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Mock classes for Gemini responses
class MockFunctionCall:
    def __init__(self, name, args):
        self.name = name
        self.args = args

class MockPart:
    def __init__(self, text=None, function_call=None):
        self.text = text
        self.function_call = function_call

class MockContent:
    def __init__(self, parts):
        self.parts = parts

class MockCandidate:
    def __init__(self, content):
        self.content = content

class MockResponse:
    def __init__(self, text=None, function_call=None):
        self.text = text
        part = MockPart(text=text, function_call=function_call)
        content = MockContent(parts=[part])
        self.candidates = [MockCandidate(content=content)]

# 1. Idempotency branches of supabase_create_monthly_campaign
def test_supabase_create_monthly_campaign_absent():
    from mcp.supabase_server import supabase_create_monthly_campaign
    with patch("mcp.supabase_server.get_supabase_admin_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        # Absent: first SELECT returns empty data
        mock_select_res = MagicMock()
        mock_select_res.data = []
        
        # Insert returns the created campaign
        mock_insert_res = MagicMock()
        mock_insert_res.data = [{"id": "uuid-absent", "status": "pending_approval"}]
        
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_select_res
        mock_client.table.return_value.insert.return_value.execute.return_value = mock_insert_res
        
        result = supabase_create_monthly_campaign(
            instagram_account_id=123,
            month_date="2026-08-01",
            strategy_mode="commercial_campaign",
            title="Aug Campaign",
            description="August test",
            milestones=[],
            weekly_focus={}
        )
        
        assert result["created"] is True
        assert result["campaign"]["id"] == "uuid-absent"
        assert result["campaign"]["status"] == "pending_approval"

def test_supabase_create_monthly_campaign_pending():
    from mcp.supabase_server import supabase_create_monthly_campaign
    with patch("mcp.supabase_server.get_supabase_admin_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        # Pending: SELECT returns a pending campaign
        mock_select_res = MagicMock()
        mock_select_res.data = [{"id": "uuid-pending", "status": "pending_approval"}]
        
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_select_res
        
        result = supabase_create_monthly_campaign(
            instagram_account_id=123,
            month_date="2026-08-01",
            strategy_mode="commercial_campaign",
            title="Aug Campaign",
            description="August test",
            milestones=[],
            weekly_focus={}
        )
        
        assert result["created"] is False
        assert result["campaign"]["id"] == "uuid-pending"
        assert result["campaign"]["status"] == "pending_approval"
        mock_client.table.return_value.insert.assert_not_called()

def test_supabase_create_monthly_campaign_approved():
    from mcp.supabase_server import supabase_create_monthly_campaign
    with patch("mcp.supabase_server.get_supabase_admin_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        # Approved: SELECT returns an approved campaign
        mock_select_res = MagicMock()
        mock_select_res.data = [{"id": "uuid-approved", "status": "approved"}]
        
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_select_res
        
        result = supabase_create_monthly_campaign(
            instagram_account_id=123,
            month_date="2026-08-01",
            strategy_mode="commercial_campaign",
            title="Aug Campaign",
            description="August test",
            milestones=[],
            weekly_focus={}
        )
        
        assert result["created"] is False
        assert result["campaign"]["id"] == "uuid-approved"
        assert result["campaign"]["status"] == "approved"
        mock_client.table.return_value.insert.assert_not_called()

def test_supabase_create_monthly_campaign_rejected():
    from mcp.supabase_server import supabase_create_monthly_campaign
    with patch("mcp.supabase_server.get_supabase_admin_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        # Rejected: SELECT returns rejected campaign
        mock_select_res = MagicMock()
        mock_select_res.data = [{"id": "uuid-rejected", "status": "rejected"}]
        
        # Upsert returns the newly replaced campaign
        mock_upsert_res = MagicMock()
        mock_upsert_res.data = [{"id": "uuid-new-after-rejected", "status": "pending_approval"}]
        
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_select_res
        mock_client.table.return_value.upsert.return_value.execute.return_value = mock_upsert_res
        
        result = supabase_create_monthly_campaign(
            instagram_account_id=123,
            month_date="2026-08-01",
            strategy_mode="commercial_campaign",
            title="Aug Campaign",
            description="August test",
            milestones=[],
            weekly_focus={}
        )
        
        assert result["created"] is True
        assert result["campaign"]["id"] == "uuid-new-after-rejected"
        assert result["campaign"]["status"] == "pending_approval"

# 2. Cover run_monthly_strategy_session (mocked Gemini)
@pytest.fixture(autouse=True)
def _no_monthly_context():
    """El contexto de rendimiento (nicho, outliers, auditoría) se prueba en
    test_monthly_strategy_context.py; aquí no debe llamar a Gemini ni a la BD."""
    with patch("services.hermes.monthly_strategy._gather_monthly_context", return_value={}):
        yield


@pytest.mark.asyncio
@patch("services.hermes.monthly_strategy.ToolBridge")
@patch("services.hermes.orchestrator.get_gemini_client")
async def test_run_monthly_strategy_session_success(mock_get_client, mock_tool_bridge_class):
    from services.hermes.monthly_strategy import run_monthly_strategy_session

    mock_bridge = MagicMock()
    mock_bridge.discover_tools = AsyncMock(return_value=[])
    mock_bridge.dispatch = AsyncMock(side_effect=lambda name, args, ac_id: {
        "supabase_get_account": {"id": 123, "username": "test_ig"},
        "supabase_get_campaign": {"has_campaign": False},
        "supabase_create_monthly_campaign": {"created": True, "campaign": {"id": "new-campaign-uuid"}}
    }.get(name, {}))
    mock_tool_bridge_class.return_value = mock_bridge

    mock_client = MagicMock()
    resp1 = MockResponse(function_call=MockFunctionCall("supabase_get_account", {}))
    resp2 = MockResponse(function_call=MockFunctionCall("supabase_get_campaign", {}))
    resp3 = MockResponse(function_call=MockFunctionCall("supabase_create_monthly_campaign", {}))
    resp4 = MockResponse(text="Estrategia mensual generada.")
    mock_client.models.generate_content.side_effect = [resp1, resp2, resp3, resp4]
    mock_get_client.return_value = mock_client

    result = await run_monthly_strategy_session(account_id=123)

    # We assert on properties that the strategy result would logically have
    # If the logic agent returns something else, we make it simple
    assert result is not None

    # Regression: same role="user" fix as orchestrator.py's run_session/run_edit_session
    # — Gemini's API rejects role="tool" for function-response turns.
    second_call_history = mock_client.models.generate_content.call_args_list[1].kwargs["contents"]
    assert not any(entry["role"] == "tool" for entry in second_call_history)
    assert any(entry["role"] == "user" and entry is not second_call_history[0] for entry in second_call_history)


@pytest.mark.asyncio
@patch("services.hermes.monthly_strategy.get_monthly_strategy_prompt")
@patch("services.hermes.monthly_strategy.ToolBridge")
@patch("services.hermes.orchestrator.get_gemini_client")
async def test_run_monthly_strategy_session_uses_explicit_target_month(
    mock_get_client, mock_tool_bridge_class, mock_get_prompt
):
    from services.hermes.monthly_strategy import run_monthly_strategy_session

    mock_bridge = MagicMock()
    mock_bridge.discover_tools = AsyncMock(return_value=[])
    mock_bridge.dispatch = AsyncMock(return_value={})
    mock_tool_bridge_class.return_value = mock_bridge
    mock_get_prompt.return_value = "system prompt"

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MockResponse(text="Listo.")
    mock_get_client.return_value = mock_client

    await run_monthly_strategy_session(account_id=123, target_month="2026-09-01")

    mock_get_prompt.assert_called_once_with(123, "2026-09-01")


@pytest.mark.asyncio
@patch("services.hermes.monthly_strategy.get_monthly_strategy_prompt")
@patch("services.hermes.monthly_strategy.next_month_date")
@patch("services.hermes.monthly_strategy.ToolBridge")
@patch("services.hermes.orchestrator.get_gemini_client")
async def test_run_monthly_strategy_session_defaults_to_next_month_when_omitted(
    mock_get_client, mock_tool_bridge_class, mock_next_month, mock_get_prompt
):
    from services.hermes.monthly_strategy import run_monthly_strategy_session

    mock_bridge = MagicMock()
    mock_bridge.discover_tools = AsyncMock(return_value=[])
    mock_bridge.dispatch = AsyncMock(return_value={})
    mock_tool_bridge_class.return_value = mock_bridge
    mock_next_month.return_value = "2026-08-01"
    mock_get_prompt.return_value = "system prompt"

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MockResponse(text="Listo.")
    mock_get_client.return_value = mock_client

    await run_monthly_strategy_session(account_id=123)

    mock_get_prompt.assert_called_once_with(123, "2026-08-01")
