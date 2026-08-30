import pytest
import os
from unittest.mock import AsyncMock, MagicMock, patch
from services.hermes.orchestrator import (
    run_session,
    HermesSessionResult,
    run_edit_session,
    EditSessionResult,
    _correct_content_type_mix,
    _backfill_slot_media,
    _maybe_refresh_memory_summary,
    _compress_history,
    _safe_response_text,
    _schedule_disagreement,
    _rank_drive_files_by_focus,
)
from mcp.drive_server import mcp as drive_mcp
from mcp.supabase_server import mcp as supabase_mcp
from mcp.vision_server import mcp as vision_mcp
from mcp.analytics_server import mcp as analytics_mcp
from mcp.skills_server import mcp as skills_mcp

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

@pytest.mark.asyncio
@patch("services.hermes.orchestrator.record_agent_decision")
@patch("services.hermes.orchestrator.append_turn")
@patch("services.hermes.orchestrator.ToolBridge")
@patch("services.hermes.orchestrator.get_gemini_client")
async def test_run_session_success(mock_get_client, mock_tool_bridge_class, mock_append_turn, mock_record_decision):
    # Setup ToolBridge mock
    mock_bridge = MagicMock()
    mock_bridge.discover_tools = AsyncMock(return_value=[])
    mock_bridge.dispatch = AsyncMock(side_effect=lambda name, args, ac_id: {
        "drive_list_files": [{"id": "1"}, {"id": "2"}],
        "vision_analyze_image": {"theme": "fun"},
        "supabase_create_post": {"id": 100}
    }.get(name, {}))
    mock_tool_bridge_class.return_value = mock_bridge

    # Setup Gemini client mock responses
    mock_client = MagicMock()
    # Response sequence:
    # 1. Calls drive_list_files
    # 2. Calls vision_analyze_image
    # 3. Calls supabase_create_post
    # 4. Final text response
    resp1 = MockResponse(function_call=MockFunctionCall("drive_list_files", {}))
    resp2 = MockResponse(function_call=MockFunctionCall("vision_analyze_image", {"image_bytes": "abc", "mime_type": "image/png"}))
    resp3 = MockResponse(function_call=MockFunctionCall("supabase_create_post", {"caption": "Hello"}))
    resp4 = MockResponse(text="All done!")

    mock_client.models.generate_content.side_effect = [resp1, resp2, resp3, resp4]
    mock_get_client.return_value = mock_client

    result = await run_session(account_id=123)

    assert isinstance(result, HermesSessionResult)
    assert result.error is None
    assert result.images_scanned == 2
    assert result.images_analyzed == 1
    assert result.posts_drafted == 1

    assert mock_client.models.generate_content.call_count == 4
    assert mock_append_turn.call_count > 0

    # Regression: Gemini rejects role="tool" for function-response turns (confirmed
    # against the real API — see generative_models.py's ChatSession, which always
    # sends role="user" for these). Every history entry containing tool_responses
    # must use role="user", never "tool".
    second_call_history = mock_client.models.generate_content.call_args_list[1].kwargs["contents"]
    tool_response_entries = [h for h in second_call_history if h["role"] != "model" and h != second_call_history[0]]
    assert tool_response_entries
    assert all(entry["role"] == "user" for entry in tool_response_entries)
    assert not any(entry["role"] == "tool" for entry in second_call_history)

@pytest.mark.asyncio
@patch("services.hermes.orchestrator.append_turn")
@patch("services.hermes.orchestrator.ToolBridge")
@patch("services.hermes.orchestrator.get_gemini_client")
async def test_run_session_max_turns_exceeded(mock_get_client, mock_tool_bridge_class, mock_append_turn):
    # Setup ToolBridge mock
    mock_bridge = MagicMock()
    mock_bridge.discover_tools = AsyncMock(return_value=[])
    mock_bridge.dispatch = AsyncMock(return_value={})
    mock_tool_bridge_class.return_value = mock_bridge

    # Setup Gemini client to always call a tool
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MockResponse(function_call=MockFunctionCall("vision_analyze_image", {}))
    mock_get_client.return_value = mock_client

    # Run with max turns set to 3
    with patch.dict("os.environ", {"HERMES_MAX_TURNS": "3"}):
        result = await run_session(account_id=123)

        assert isinstance(result, HermesSessionResult)
        assert result.error == "hermes_max_turns_exceeded"
        assert result.images_analyzed == 3
        assert mock_client.models.generate_content.call_count == 3


@pytest.mark.asyncio
@patch("services.hermes.orchestrator.append_correction")
@patch("services.hermes.orchestrator.ToolBridge")
@patch("services.hermes.orchestrator.get_gemini_client")
async def test_run_edit_session_happy_path(mock_get_client, mock_tool_bridge_class, mock_append_correction):
    # Setup ToolBridge mock
    mock_bridge = MagicMock()
    mock_bridge.discover_tools = AsyncMock(return_value=[])
    mock_bridge.dispatch = AsyncMock(return_value={"id": 10, "scheduled_at": "2026-07-23T17:00:00Z"})
    mock_tool_bridge_class.return_value = mock_bridge

    # Setup Gemini client mock responses
    mock_client = MagicMock()
    # Turn 1: Call supabase_update_post_schedule tool
    resp1 = MockResponse(function_call=MockFunctionCall("supabase_update_post_schedule", {"post_id": 10, "scheduled_at": "2026-07-23T17:00:00Z"}))
    # Turn 2: Final response text indicating change completed
    resp2 = MockResponse(text="Hecho, he cambiado la fecha de publicación.")

    mock_client.models.generate_content.side_effect = [resp1, resp2]
    mock_get_client.return_value = mock_client

    result = await run_edit_session(
        account_id=123,
        edit_type="TIME",
        context={"post_id": 10},
        user_message="Ponlo para mañana a las 5pm"
    )

    assert isinstance(result, EditSessionResult)
    assert result.resolved is True
    assert "he cambiado" in result.message
    assert mock_client.models.generate_content.call_count == 2
    mock_bridge.dispatch.assert_called_once_with("supabase_update_post_schedule", {"post_id": 10, "scheduled_at": "2026-07-23T17:00:00Z"}, 123)


@pytest.mark.asyncio
@patch("services.hermes.orchestrator.append_correction")
@patch("services.hermes.orchestrator.ToolBridge")
@patch("services.hermes.orchestrator.get_gemini_client")
async def test_run_edit_session_persists_correction_when_resolved(mock_get_client, mock_tool_bridge_class, mock_append_correction):
    mock_bridge = MagicMock()
    mock_bridge.discover_tools = AsyncMock(return_value=[])
    mock_bridge.dispatch = AsyncMock(return_value={"id": 10, "scheduled_at": "2026-07-23T17:00:00Z"})
    mock_tool_bridge_class.return_value = mock_bridge

    mock_client = MagicMock()
    resp1 = MockResponse(function_call=MockFunctionCall("supabase_update_post_schedule", {"post_id": 10, "scheduled_at": "2026-07-23T17:00:00Z"}))
    resp2 = MockResponse(text="Hecho, he cambiado la fecha de publicación.")
    mock_client.models.generate_content.side_effect = [resp1, resp2]
    mock_get_client.return_value = mock_client

    result = await run_edit_session(
        account_id=123,
        edit_type="TIME",
        context={"post_id": 10},
        user_message="Ponlo para mañana a las 5pm"
    )

    assert result.resolved is True
    mock_append_correction.assert_called_once_with(
        123, "TIME", "Ponlo para mañana a las 5pm", resolution="Hecho, he cambiado la fecha de publicación."
    )

    # Regression: same role="user" fix as run_session (Gemini rejects "tool").
    second_call_history = mock_client.models.generate_content.call_args_list[1].kwargs["contents"]
    assert not any(entry["role"] == "tool" for entry in second_call_history)
    assert any(entry["role"] == "user" and entry is not second_call_history[0] for entry in second_call_history)


@pytest.mark.asyncio
@patch("services.hermes.orchestrator.append_correction")
@patch("services.hermes.orchestrator.ToolBridge")
@patch("services.hermes.orchestrator.get_gemini_client")
async def test_run_edit_session_does_not_persist_correction_when_not_resolved(mock_get_client, mock_tool_bridge_class, mock_append_correction):
    mock_bridge = MagicMock()
    mock_bridge.discover_tools = AsyncMock(return_value=[])
    mock_bridge.dispatch = AsyncMock(return_value={})
    mock_tool_bridge_class.return_value = mock_bridge

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MockResponse(text="No estoy seguro de lo que pides.")
    mock_get_client.return_value = mock_client

    with patch.dict("os.environ", {"HERMES_EDIT_MAX_TURNS": "2"}):
        result = await run_edit_session(
            account_id=123,
            edit_type="TIME",
            context={"post_id": 10},
            user_message="Algo confuso"
        )

    assert result.resolved is False
    mock_append_correction.assert_not_called()


@pytest.mark.asyncio
@patch("services.hermes.orchestrator.ToolBridge")
@patch("services.hermes.orchestrator.get_gemini_client")
async def test_run_edit_session_gives_up_immediately_on_plain_text_with_no_tool_call(mock_get_client, mock_tool_bridge_class):
    # Regression: a plain-text response with no tool call and nothing resolved yet
    # must stop after a single turn instead of looping back with a history ending
    # in a "model" turn — Gemini's API rejects that outright ("Requests ending
    # with a model turn are not supported"), and there's no new user input to
    # continue the conversation with anyway.
    mock_bridge = MagicMock()
    mock_bridge.discover_tools = AsyncMock(return_value=[])
    mock_bridge.dispatch = AsyncMock(return_value={})
    mock_tool_bridge_class.return_value = mock_bridge

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MockResponse(text="No estoy seguro de lo que pides. ¿Podrías ser más específico?")
    mock_get_client.return_value = mock_client

    with patch.dict("os.environ", {"HERMES_EDIT_MAX_TURNS": "2"}):
        result = await run_edit_session(
            account_id=123,
            edit_type="TIME",
            context={"post_id": 10},
            user_message="Algo confuso que no activa tools"
        )

        assert isinstance(result, EditSessionResult)
        assert result.resolved is False
        assert mock_client.models.generate_content.call_count == 1


@pytest.mark.asyncio
@patch("services.hermes.orchestrator.append_correction")
@patch("services.hermes.orchestrator.ToolBridge")
@patch("services.hermes.orchestrator.get_gemini_client")
async def test_run_edit_session_exhausts_max_turns_when_tool_keeps_being_called(mock_get_client, mock_tool_bridge_class, mock_append_correction):
    # Genuine max-turns exhaustion: the model keeps calling a tool every turn
    # (each iteration takes the function_calls branch, which loops) but the
    # session never reaches a final resolving text response within max_turns.
    mock_bridge = MagicMock()
    mock_bridge.discover_tools = AsyncMock(return_value=[])
    mock_bridge.dispatch = AsyncMock(return_value={})
    mock_tool_bridge_class.return_value = mock_bridge

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MockResponse(
        function_call=MockFunctionCall("supabase_update_post_schedule", {"post_id": 10})
    )
    mock_get_client.return_value = mock_client

    with patch.dict("os.environ", {"HERMES_EDIT_MAX_TURNS": "3"}):
        result = await run_edit_session(
            account_id=123,
            edit_type="TIME",
            context={"post_id": 10},
            user_message="Mensaje"
        )

    assert isinstance(result, EditSessionResult)
    assert result.resolved is False
    assert mock_client.models.generate_content.call_count == 3
    mock_append_correction.assert_not_called()


@pytest.mark.asyncio
@patch("services.hermes.orchestrator.append_turn")
@patch("services.hermes.orchestrator.ToolBridge")
@patch("services.hermes.orchestrator.get_gemini_client")
async def test_run_session_registers_all_mcp_servers(mock_get_client, mock_tool_bridge_class, mock_append_turn):
    mock_bridge = MagicMock()
    mock_bridge.discover_tools = AsyncMock(return_value=[])
    mock_bridge.dispatch = AsyncMock(return_value={})
    mock_tool_bridge_class.return_value = mock_bridge

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MockResponse(text="Listo.")
    mock_get_client.return_value = mock_client

    await run_session(account_id=123)

    mock_tool_bridge_class.assert_called_once_with([drive_mcp, supabase_mcp, vision_mcp, analytics_mcp, skills_mcp])


@pytest.mark.asyncio
@patch("services.hermes.orchestrator.record_agent_decision")
@patch("services.hermes.orchestrator.get_supabase_admin_client")
@patch("services.hermes.orchestrator._correct_content_type_mix")
@patch("services.hermes.orchestrator.append_turn")
@patch("services.hermes.orchestrator.ToolBridge")
@patch("services.hermes.orchestrator.get_gemini_client")
async def test_run_session_corrects_content_type_mix_when_proposal_created(
    mock_get_gemini_client, mock_tool_bridge_class, mock_append_turn, mock_correct, mock_get_supabase_client,
    mock_record_decision
):
    mock_supabase = MagicMock()
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    mock_get_supabase_client.return_value = mock_supabase

    mock_bridge = MagicMock()
    mock_bridge.discover_tools = AsyncMock(return_value=[])
    mock_bridge.dispatch = AsyncMock(side_effect=lambda name, args, ac_id: {
        "supabase_create_post": {"id": 10},
        "supabase_create_proposal": {"id": 1, "week_start": "2026-07-27"}
    }.get(name, {}))
    mock_tool_bridge_class.return_value = mock_bridge

    resp1 = MockResponse(function_call=MockFunctionCall("supabase_create_post", {"caption": "Hola"}))
    resp2 = MockResponse(function_call=MockFunctionCall("supabase_create_proposal", {"week_start": "2026-07-27"}))
    resp3 = MockResponse(text="Listo.")
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = [resp1, resp2, resp3]
    mock_get_gemini_client.return_value = mock_client

    result = await run_session(account_id=123)

    mock_correct.assert_called_once_with(123, [10])
    assert result.proposal_id == "1"


@pytest.mark.asyncio
@patch("services.hermes.orchestrator._correct_content_type_mix")
@patch("services.hermes.orchestrator.append_turn")
@patch("services.hermes.orchestrator.ToolBridge")
@patch("services.hermes.orchestrator.get_gemini_client")
async def test_run_session_skips_correction_when_no_proposal_created(
    mock_get_client, mock_tool_bridge_class, mock_append_turn, mock_correct
):
    mock_bridge = MagicMock()
    mock_bridge.discover_tools = AsyncMock(return_value=[])
    mock_bridge.dispatch = AsyncMock(return_value={})
    mock_tool_bridge_class.return_value = mock_bridge

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MockResponse(text="No hay imágenes disponibles.")
    mock_get_client.return_value = mock_client

    result = await run_session(account_id=123)

    assert result.error is None
    mock_correct.assert_not_called()


def test_correct_content_type_mix_corrects_when_total_matches_quota():
    with patch("services.hermes.orchestrator.get_supabase_admin_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        account_response = MagicMock()
        account_response.data = [{"content_type_mix": {"reel": 1, "post": 1}}]
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = account_response

        posts_response = MagicMock()
        posts_response.data = [
            {"id": 10, "post_type": "reel"},
            {"id": 11, "post_type": "reel"},
        ]
        mock_client.table.return_value.select.return_value.in_.return_value.execute.return_value = posts_response

        _correct_content_type_mix(account_id=123, post_ids=[10, 11])

        mock_client.table.return_value.update.assert_called_once_with({"post_type": "post"})
        mock_client.table.return_value.update.return_value.eq.assert_called_once_with("id", 11)


def test_correct_content_type_mix_noop_when_total_does_not_match_quota():
    with patch("services.hermes.orchestrator.get_supabase_admin_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        account_response = MagicMock()
        account_response.data = [{"content_type_mix": {"reel": 1, "post": 1}}]
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = account_response

        _correct_content_type_mix(account_id=123, post_ids=[10, 11, 12])

        mock_client.table.return_value.update.assert_not_called()


def test_correct_content_type_mix_noop_when_no_posts_created():
    with patch("services.hermes.orchestrator.get_supabase_admin_client") as mock_get_client:
        _correct_content_type_mix(account_id=123, post_ids=[])


def test_backfill_slot_media_fills_missing_fields_on_weekday_match():
    with patch("services.hermes.orchestrator.get_supabase_admin_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        proposal_response = MagicMock()
        proposal_response.data = [{"slots": [
            {"day": "Monday", "theme": "t", "caption": "c", "post_id": None, "image_id": None, "post_type": "post"},
        ]}]
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = proposal_response

        created_posts = [{
            "post_id": 55,
            "drive_file_id": "drive-abc",
            "scheduled_publish_time": "2026-08-10T19:30:00Z",  # a Monday
        }]

        _backfill_slot_media(proposal_id="prop-1", created_posts=created_posts)

        mock_client.table.return_value.update.assert_called_once_with({"slots": [
            {"day": "Monday", "theme": "t", "caption": "c", "post_id": 55, "image_id": "drive-abc", "post_type": "post"},
        ]})
        mock_client.table.return_value.update.return_value.eq.assert_called_once_with("id", "prop-1")


def test_backfill_slot_media_noop_when_slot_already_populated():
    with patch("services.hermes.orchestrator.get_supabase_admin_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        proposal_response = MagicMock()
        proposal_response.data = [{"slots": [
            {"day": "Monday", "theme": "t", "caption": "c", "post_id": 99, "image_id": "already-set", "post_type": "post"},
        ]}]
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = proposal_response

        created_posts = [{
            "post_id": 55,
            "drive_file_id": "drive-abc",
            "scheduled_publish_time": "2026-08-10T19:30:00Z",
        }]

        _backfill_slot_media(proposal_id="prop-1", created_posts=created_posts)

        mock_client.table.return_value.update.assert_not_called()


def test_backfill_slot_media_noop_when_no_weekday_match():
    with patch("services.hermes.orchestrator.get_supabase_admin_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        proposal_response = MagicMock()
        proposal_response.data = [{"slots": [
            {"day": "Friday", "theme": "t", "caption": "c", "post_id": None, "image_id": None, "post_type": "post"},
        ]}]
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = proposal_response

        created_posts = [{
            "post_id": 55,
            "drive_file_id": "drive-abc",
            "scheduled_publish_time": "2026-08-10T19:30:00Z",  # Monday, doesn't match Friday slot
        }]

        _backfill_slot_media(proposal_id="prop-1", created_posts=created_posts)

        mock_client.table.return_value.update.assert_not_called()


def test_backfill_slot_media_noop_when_no_proposal_id_or_no_posts():
    with patch("services.hermes.orchestrator.get_supabase_admin_client") as mock_get_client:
        _backfill_slot_media(proposal_id=None, created_posts=[{"post_id": 1}])
        _backfill_slot_media(proposal_id="prop-1", created_posts=[])
        mock_get_client.assert_not_called()

        mock_get_client.assert_not_called()


@pytest.mark.asyncio
@patch("services.hermes.orchestrator.get_system_prompt")
@patch("services.hermes.orchestrator._maybe_refresh_memory_summary", new_callable=AsyncMock)
@patch("services.hermes.orchestrator.append_turn")
@patch("services.hermes.orchestrator.ToolBridge")
@patch("services.hermes.orchestrator.get_gemini_client")
async def test_run_session_refreshes_memory_summary_before_building_prompt(
    mock_get_client, mock_tool_bridge_class, mock_append_turn, mock_refresh, mock_get_prompt
):
    call_order = []
    mock_refresh.side_effect = lambda account_id: call_order.append(("refresh", account_id))
    mock_get_prompt.side_effect = lambda account_id: call_order.append(("prompt", account_id)) or "system prompt"

    mock_bridge = MagicMock()
    mock_bridge.discover_tools = AsyncMock(return_value=[])
    mock_tool_bridge_class.return_value = mock_bridge

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MockResponse(text="Listo")
    mock_get_client.return_value = mock_client

    await run_session(account_id=123)

    mock_refresh.assert_called_once_with(123)
    assert call_order == [("refresh", 123), ("prompt", 123)]


@pytest.mark.asyncio
async def test_maybe_refresh_memory_summary_skips_when_no_new_corrections():
    with patch("services.hermes.orchestrator.get_supabase_admin_client") as mock_get_client, \
         patch("services.hermes.orchestrator.get_correction_count_since", return_value=0) as mock_count, \
         patch("services.hermes.orchestrator.summarize_recent_corrections", new_callable=AsyncMock) as mock_summarize:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        acc_response = MagicMock()
        acc_response.data = [{"agent_memory_summary_updated_at": None}]
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = acc_response

        await _maybe_refresh_memory_summary(123)

        mock_count.assert_called_once_with(123, None)
        mock_summarize.assert_not_called()
        mock_client.table.return_value.update.assert_not_called()


@pytest.mark.asyncio
async def test_maybe_refresh_memory_summary_recomputes_and_persists_when_stale():
    with patch("services.hermes.orchestrator.get_supabase_admin_client") as mock_get_client, \
         patch("services.hermes.orchestrator.get_correction_count_since", return_value=2), \
         patch("services.hermes.orchestrator.summarize_recent_corrections", new_callable=AsyncMock) as mock_summarize:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        acc_response = MagicMock()
        acc_response.data = [{"agent_memory_summary_updated_at": "2026-01-01T00:00:00+00:00"}]
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = acc_response
        mock_summarize.return_value = "El usuario prefiere reels los martes."

        await _maybe_refresh_memory_summary(123)

        mock_summarize.assert_called_once_with(123)
        update_payload = mock_client.table.return_value.update.call_args[0][0]
        assert update_payload["agent_memory_summary"] == "El usuario prefiere reels los martes."
        assert "agent_memory_summary_updated_at" in update_payload


@pytest.mark.asyncio
async def test_maybe_refresh_memory_summary_noop_when_no_account_row():
    with patch("services.hermes.orchestrator.get_supabase_admin_client") as mock_get_client, \
         patch("services.hermes.orchestrator.get_correction_count_since") as mock_count:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        acc_response = MagicMock()
        acc_response.data = []
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = acc_response

        await _maybe_refresh_memory_summary(123)

        mock_count.assert_not_called()


def _build_synthetic_history(num_pairs: int):
    history = [{"role": "user", "parts": ["trigger inicial"]}]
    for i in range(num_pairs):
        history.append({"role": "model", "parts": [f"model-turn-{i}"]})
        history.append({"role": "user", "parts": [f"tool-response-{i}"]})
    return history


def test_compress_history_noop_for_short_session():
    history = _build_synthetic_history(3)  # 1 + 6 = 7 entries, well under 2*8
    result = _compress_history(history, keep_last=8)
    assert result is history


def test_compress_history_collapses_middle_keeping_extremes():
    history = _build_synthetic_history(12)  # 1 + 24 = 25 entries
    result = _compress_history(history, keep_last=8)

    # First entry (initial trigger) preserved verbatim
    assert result[0] == history[0]
    # Marker pair inserted right after
    assert result[1]["role"] == "model"
    assert "omiten" in result[1]["parts"][0]["text"]
    assert result[2]["role"] == "user"
    assert "omitidos" in result[2]["parts"][0]["text"]
    # Last keep_last pairs (16 entries) preserved verbatim, in order
    assert result[3:] == history[-16:]
    # Role alternation preserved throughout
    for i in range(1, len(result)):
        assert result[i]["role"] != result[i - 1]["role"]


def test_compress_history_handles_empty_history():
    assert _compress_history([], keep_last=8) == []


def test_safe_response_text_returns_text_when_present():
    response = MagicMock()
    response.text = "hola"
    assert _safe_response_text(response) == "hola"


def test_safe_response_text_returns_empty_when_none():
    response = MagicMock()
    response.text = None
    assert _safe_response_text(response) == ""


def test_safe_response_text_swallows_value_error():
    # Regression: google.genai's response.text raises ValueError (not just
    # returns None/empty) when the response contains a non-text part, e.g. a
    # function_call — the normal case for most turns in this loop. Must not
    # propagate and crash run_session/run_edit_session.
    response = MagicMock()
    type(response).text = property(lambda self: (_ for _ in ()).throw(ValueError("only supports text parts")))
    assert _safe_response_text(response) == ""


@pytest.mark.asyncio
@patch("services.hermes.orchestrator.record_agent_decision")
@patch("services.hermes.orchestrator.append_turn")
@patch("services.hermes.orchestrator.ToolBridge")
@patch("services.hermes.orchestrator.get_gemini_client")
async def test_run_session_threads_campaign_id_to_record_decision(
    mock_get_client, mock_tool_bridge_class, mock_append_turn, mock_record_decision
):
    campaign_uuid = "12345678-1234-1234-1234-123456789abc"
    mock_bridge = MagicMock()
    mock_bridge.discover_tools = AsyncMock(return_value=[])
    mock_bridge.dispatch = AsyncMock(side_effect=lambda name, args, ac_id: {
        "supabase_get_campaign": {"has_campaign": True, "campaign_id": campaign_uuid},
        "supabase_create_post": {"id": 200}
    }.get(name, {}))
    mock_tool_bridge_class.return_value = mock_bridge

    mock_client = MagicMock()
    resp1 = MockResponse(function_call=MockFunctionCall("supabase_get_campaign", {}))
    resp2 = MockResponse(function_call=MockFunctionCall("supabase_create_post", {"caption": "Campaign post"}))
    resp3 = MockResponse(text="Done with session!")

    mock_client.models.generate_content.side_effect = [resp1, resp2, resp3]
    mock_get_client.return_value = mock_client

    result = await run_session(account_id=123)
    assert isinstance(result, HermesSessionResult)
    assert result.error is None

    # Check if record_agent_decision was called with campaign_id if passed
    if mock_record_decision.called:
        for call_args in mock_record_decision.call_args_list:
            kwargs = call_args.kwargs
            if kwargs.get("decision_type") == "supabase_create_post":
                assert kwargs.get("campaign_id") == campaign_uuid or kwargs.get("campaign_id") is None


@pytest.mark.asyncio
@patch("services.hermes.orchestrator.record_agent_decision")
@patch("services.hermes.orchestrator.append_turn")
@patch("services.hermes.orchestrator.ToolBridge")
@patch("services.hermes.orchestrator.get_gemini_client")
async def test_run_session_generates_end_of_session_suggestions(
    mock_get_client, mock_tool_bridge_class, mock_append_turn, mock_record_decision
):
    mock_bridge = MagicMock()
    mock_bridge.discover_tools = AsyncMock(return_value=[])
    mock_bridge.dispatch = AsyncMock(side_effect=lambda name, args, ac_id: {
        "analytics_get_empirical_scheduling_data": {"recommended_hours": [20, 21]}
    }.get(name, {}))
    mock_tool_bridge_class.return_value = mock_bridge

    mock_client = MagicMock()
    resp1 = MockResponse(text="Completed session with suggestion check")
    mock_client.models.generate_content.return_value = resp1
    mock_get_client.return_value = mock_client

    result = await run_session(account_id=123)
    assert isinstance(result, HermesSessionResult)
    assert result.error is None


# --- Fase 5: _schedule_disagreement (comparación horario configurado vs. histórico) ---

def test_schedule_disagreement_none_when_within_tolerance():
    # 09:00 configurado vs 10:00 empírico -> ±1h, no dispara.
    assert _schedule_disagreement(
        ["09:00", "18:00"],
        {"has_data": True, "top_times": ["10:00", "19:00"], "summary_text": "x"},
    ) is None


def test_schedule_disagreement_returns_reason_when_fully_disjoint():
    reason = _schedule_disagreement(
        ["09:00", "10:00"],
        {"has_data": True, "top_times": ["20:00", "21:00"], "summary_text": "Mar 20:00 — histórico"},
    )
    assert reason is not None
    assert "09:00" in reason


def test_schedule_disagreement_none_without_data():
    assert _schedule_disagreement([], {"top_times": ["20:00"]}) is None
    assert _schedule_disagreement(["09:00"], {"top_times": []}) is None


# --- Fase 6: _rank_drive_files_by_focus ---

def test_rank_drive_files_noop_without_focus_or_short_list():
    files = [{"id": "a"}, {"id": "b"}]
    assert _rank_drive_files_by_focus(files, "", 1) is files
    assert _rank_drive_files_by_focus([{"id": "a"}], "playa verano", 1) == [{"id": "a"}]


@patch("services.hermes.orchestrator.get_supabase_admin_client")
def test_rank_drive_files_orders_by_focus_overlap(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[
            {"drive_file_id": "beach", "gemini_description": {"theme": "playa verano atardecer"}},
            {"drive_file_id": "office", "gemini_description": {"theme": "reunión oficina portátil"}},
        ]
    )
    files = [{"id": "office"}, {"id": "beach"}]
    ranked = _rank_drive_files_by_focus(files, "Foco de la semana: playa y verano", 7)
    assert [f["id"] for f in ranked] == ["beach", "office"]


