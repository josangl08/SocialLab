import pytest
from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import patch, MagicMock, AsyncMock
from services.hermes.memory import (
    load_session_history,
    append_turn,
    append_correction,
    get_correction_count_since,
    summarize_recent_corrections,
)

def test_load_session_history():
    session_id = uuid4()
    account_id = 123
    
    with patch("services.hermes.memory.get_supabase_admin_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.data = [{"id": 1, "role": "user", "content": "hello"}]
        
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value = mock_response
        
        history = load_session_history(account_id, session_id)
        
        assert history == [{"id": 1, "role": "user", "content": "hello"}]
        mock_client.table.assert_called_once_with("agent_memory")
        
        # Verify query parameters
        mock_client.table.return_value.select.assert_called_once_with("*")
        eq1 = mock_client.table.return_value.select.return_value.eq
        eq1.assert_called_once_with("account_id", account_id)
        
        eq2 = eq1.return_value.eq
        eq2.assert_called_once_with("session_id", str(session_id))
        
        order = eq2.return_value.order
        order.assert_called_once_with("id", desc=False)

def test_append_turn():
    session_id = uuid4()
    account_id = 123
    
    with patch("services.hermes.memory.get_supabase_admin_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.data = [{"id": 42, "role": "model"}]
        mock_client.table.return_value.insert.return_value.execute.return_value = mock_response
        
        res = append_turn(
            account_id=account_id,
            session_id=session_id,
            role="model",
            content="model output",
            tool_name="some_tool",
            tool_args={"arg": 1},
            tool_result="success"
        )
        
        assert res == {"id": 42, "role": "model"}
        mock_client.table.assert_called_once_with("agent_memory")
        mock_client.table.return_value.insert.assert_called_once_with({
            "account_id": account_id,
            "session_id": str(session_id),
            "role": "model",
            "content": "model output",
            "tool_name": "some_tool",
            "tool_args": {"arg": 1},
            "tool_result": "success"
        })


def test_append_correction_inserts_with_correction_role():
    account_id = 123

    with patch("services.hermes.memory.get_supabase_admin_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_response = MagicMock()
        mock_response.data = [{"id": 1}]
        mock_client.table.return_value.insert.return_value.execute.return_value = mock_response

        append_correction(account_id, edit_type="TIME", user_message="muévelo al martes", resolution="Hecho")

        mock_client.table.assert_called_once_with("agent_memory")
        insert_payload = mock_client.table.return_value.insert.call_args[0][0]
        assert insert_payload["account_id"] == account_id
        assert insert_payload["role"] == "correction"
        assert insert_payload["content"] == {
            "edit_type": "TIME",
            "user_message": "muévelo al martes",
            "resolution": "Hecho",
        }


def test_get_correction_count_since_returns_zero_when_no_int_count():
    with patch("services.hermes.memory.get_supabase_admin_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_response = MagicMock()
        mock_response.count = None
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_response

        assert get_correction_count_since(123, since=None) == 0


def test_get_correction_count_since_filters_by_since_when_given():
    with patch("services.hermes.memory.get_supabase_admin_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_response = MagicMock()
        mock_response.count = 3
        query = mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value
        query.gt.return_value.execute.return_value = mock_response

        since = datetime(2026, 1, 1, tzinfo=timezone.utc)
        result = get_correction_count_since(123, since=since)

        assert result == 3
        query.gt.assert_called_once_with("created_at", since.isoformat())


@pytest.mark.asyncio
async def test_summarize_recent_corrections_returns_none_when_no_rows():
    with patch("services.hermes.memory.get_supabase_admin_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_response = MagicMock()
        mock_response.data = []
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = mock_response

        result = await summarize_recent_corrections(123)
        assert result is None


@pytest.mark.asyncio
async def test_summarize_recent_corrections_calls_gemini_with_oldest_first_rows():
    with patch("services.hermes.memory.get_supabase_admin_client") as mock_get_client, \
         patch("services.hermes.memory._summarize_corrections_llm", new_callable=AsyncMock) as mock_llm:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_response = MagicMock()
        # Query orders desc — newest first — summarize_recent_corrections must reverse it.
        mock_response.data = [
            {"id": 2, "content": {"edit_type": "TIME", "user_message": "b", "resolution": "y"}},
            {"id": 1, "content": {"edit_type": "DATE", "user_message": "a", "resolution": "x"}},
        ]
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = mock_response
        mock_llm.return_value = "Resumen de prueba"

        result = await summarize_recent_corrections(123, limit=20)

        assert result == "Resumen de prueba"
        passed_rows = mock_llm.call_args[0][0]
        assert [r["id"] for r in passed_rows] == [1, 2]
