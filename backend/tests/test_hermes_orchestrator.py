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
    _drive_file_id,
    _filter_unavailable_drive_files,
    _rank_drive_files,
    _log_empty_drive_result,
    _is_transient_gemini_error,
    _FallbackGenerativeModel,
)
from mcp.drive_server import mcp as drive_mcp
from mcp.supabase_server import mcp as supabase_mcp
from mcp.vision_server import mcp as vision_mcp
from mcp.analytics_server import mcp as analytics_mcp
from mcp.skills_server import mcp as skills_mcp


@pytest.fixture(autouse=True)
def _no_reference_accounts():
    """run_session pide el resumen de referentes (Business Discovery + BD); se prueba aparte."""
    with patch("services.hermes.orchestrator.reference_summary_for_prompt", return_value=None):
        yield

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
@patch("services.hermes.orchestrator.append_turn")
@patch("services.hermes.orchestrator.ToolBridge")
@patch("services.hermes.orchestrator.get_gemini_client")
async def test_run_session_fetches_references_off_the_event_loop(mock_get_client, mock_tool_bridge_class, mock_append_turn):
    """Un refresco de referentes llama en serie a la Graph API y a Gemini: no debe bloquear el event loop."""
    import threading

    mock_bridge = MagicMock()
    mock_bridge.discover_tools = AsyncMock(return_value=[])
    mock_bridge.dispatch = AsyncMock(return_value={})
    mock_tool_bridge_class.return_value = mock_bridge
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MockResponse(text="Listo.")
    mock_get_client.return_value = mock_client
    threads = []

    with patch("services.hermes.orchestrator.reference_summary_for_prompt",
               side_effect=lambda _id: threads.append(threading.get_ident())):
        await run_session(account_id=123)

    assert threads and threads[0] != threading.get_ident()


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
    mock_get_prompt.side_effect = lambda account_id, **kwargs: call_order.append(("prompt", account_id)) or "system prompt"

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

    # The campaign_id captured from supabase_get_campaign (has_campaign=True, even
    # for a pending campaign) must be threaded into the create_post decision.
    post_decisions = [
        c for c in mock_record_decision.call_args_list
        if c.kwargs.get("decision_type") == "supabase_create_post"
    ]
    assert post_decisions, "expected a supabase_create_post decision"
    for call_args in post_decisions:
        assert call_args.kwargs.get("campaign_id") == campaign_uuid


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

def test_rank_drive_files_noop_short_list_legacy():
    assert _rank_drive_files_by_focus([], "", 1) == []
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


# --- Eje 1 & 2 Tests: Deduplicación y Ranking Visual ---

def test_drive_file_id_extractor():
    assert _drive_file_id({"id": "abc"}) == "abc"
    assert _drive_file_id({"file_id": "def"}) == "def"
    assert _drive_file_id({"drive_file_id": "ghi"}) == "ghi"
    assert _drive_file_id(None) is None
    assert _drive_file_id("not_a_dict") is None


@patch("services.hermes.orchestrator.get_supabase_admin_client")
def test_filter_unavailable_drive_files_filters_posts_and_slots(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    # Mock posts query (draft, scheduled, published)
    mock_posts_select = MagicMock()
    mock_posts_select.eq.return_value.in_.return_value.not_.is_.return_value.execute.return_value = MagicMock(
        data=[
            {"drive_file_id": "file_draft"},
            {"drive_file_id": "file_sched"},
            {"drive_file_id": "file_pub"},
        ]
    )

    # Mock content_proposals query (pending_approval, approved)
    mock_props_select = MagicMock()
    mock_props_select.eq.return_value.in_.return_value.execute.return_value = MagicMock(
        data=[
            {"slots": [{"image_id": "file_pending_slot"}, {"image_id": None}]},
            {"slots": [{"image_id": "file_approved_slot"}]},
        ]
    )

    def table_side_effect(table_name):
        mock_t = MagicMock()
        if table_name == "posts":
            mock_t.select.return_value = mock_posts_select
        elif table_name == "content_proposals":
            mock_t.select.return_value = mock_props_select
        return mock_t

    mock_client.table.side_effect = table_side_effect

    files = [
        {"id": "file_draft"},
        {"id": "file_sched"},
        {"id": "file_pub"},
        {"id": "file_pending_slot"},
        {"id": "file_approved_slot"},
        {"id": "file_rejected_slot"},
        {"id": "file_free"},
    ]

    result = _filter_unavailable_drive_files(files, account_id=1)
    result_ids = [f["id"] for f in result]

    assert "file_draft" not in result_ids
    assert "file_sched" not in result_ids
    assert "file_pub" not in result_ids
    assert "file_pending_slot" not in result_ids
    assert "file_approved_slot" not in result_ids
    assert "file_rejected_slot" in result_ids
    assert "file_free" in result_ids


@patch("services.hermes.orchestrator.get_supabase_admin_client")
def test_filter_unavailable_drive_files_returns_intact_on_exception(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_client.table.side_effect = Exception("DB error")

    files = [{"id": "1"}, {"id": "2"}]
    assert _filter_unavailable_drive_files(files, account_id=1) is files


def test_log_empty_drive_result_distinguishes_causes(caplog):
    import logging

    with caplog.at_level(logging.INFO, logger="services.hermes.orchestrator"):
        _log_empty_drive_result(0, account_id=7)
        _log_empty_drive_result(5, account_id=7)

    messages = "\n".join(caplog.messages)
    assert "no_images_in_drive" in messages
    assert "all_images_already_used" in messages
    assert "filtered_out=5" in messages


@patch("services.hermes.orchestrator.get_supabase_admin_client")
def test_rank_drive_files_formula_and_aesthetic(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    # file_a: overlap 1 token (playa) -> score = 1*2 + 4 = 6
    # file_b: overlap 0 tokens -> score = 0*2 + 8 = 8
    # file_b ranks first (8 > 6)
    mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[
            {"drive_file_id": "file_a", "gemini_description": {"theme": "playa arena", "aesthetic_score": 4}},
            {"drive_file_id": "file_b", "gemini_description": {"theme": "ciudad noche", "aesthetic_score": 8}},
        ]
    )

    files = [{"id": "file_a"}, {"id": "file_b"}]
    ranked = _rank_drive_files(files, "Foco: ir a la playa", account_id=1)

    assert [f["id"] for f in ranked] == ["file_b", "file_a"]


@patch("services.hermes.orchestrator.get_supabase_admin_client")
def test_rank_drive_files_aesthetic_only_without_focus(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[
            {"drive_file_id": "low", "gemini_description": {"aesthetic_score": 3}},
            {"drive_file_id": "high", "gemini_description": {"aesthetic_score": 9}},
        ]
    )

    files = [{"id": "low"}, {"id": "high"}]
    ranked = _rank_drive_files(files, focus_text="", account_id=1)

    assert [f["id"] for f in ranked] == ["high", "low"]


@patch("services.hermes.orchestrator.get_supabase_admin_client")
def test_rank_drive_files_neutral_5_without_analysis(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    # Only "low" (3) and "high" (8) have analysis. "neutral" has none -> score 5.
    mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[
            {"drive_file_id": "low", "gemini_description": {"aesthetic_score": 3}},
            {"drive_file_id": "high", "gemini_description": {"aesthetic_score": 8}},
        ]
    )

    files = [{"id": "low"}, {"id": "neutral"}, {"id": "high"}]
    ranked = _rank_drive_files(files, focus_text="", account_id=1)

    assert [f["id"] for f in ranked] == ["high", "neutral", "low"]


def test_rank_drive_files_noop_short_list():
    assert _rank_drive_files([], "focus", 1) == []
    assert _rank_drive_files([{"id": "x"}], "focus", 1) == [{"id": "x"}]


# --- Auto-inyección Tests ---

@pytest.mark.asyncio
@patch("services.hermes.orchestrator.get_system_prompt")
@patch("services.hermes.orchestrator.run_visual_performance_skill")
@patch("services.hermes.orchestrator.run_niche_research_for_account")
@patch("services.hermes.orchestrator.record_agent_decision")
@patch("services.hermes.orchestrator.append_turn")
@patch("services.hermes.orchestrator.ToolBridge")
@patch("services.hermes.orchestrator.get_gemini_client")
async def test_run_session_auto_injects_niche_and_visual_perf(
    mock_get_client, mock_tool_bridge_class, mock_append_turn, mock_record_decision,
    mock_niche_research, mock_visual_perf, mock_get_system_prompt
):
    mock_bridge = MagicMock()
    mock_bridge.discover_tools = AsyncMock(return_value=[])
    mock_bridge.dispatch = AsyncMock(return_value={})
    mock_tool_bridge_class.return_value = mock_bridge

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MockResponse(text="Done")
    mock_get_client.return_value = mock_client

    mock_niche_research.return_value = {"niche": "trail", "brief": "Brief de trail running"}
    mock_visual_perf.return_value = {"summary": "Visual perf summary"}
    mock_get_system_prompt.return_value = "System prompt mock"

    result = await run_session(account_id=10)

    assert result.error is None
    mock_get_system_prompt.assert_called_once_with(
        10,
        niche_brief="Brief de trail running",
        visual_perf_summary="Visual perf summary",
        references_summary=None,
    )


@pytest.mark.asyncio
@patch("services.hermes.orchestrator.get_system_prompt")
@patch("services.hermes.orchestrator.run_visual_performance_skill", side_effect=Exception("Visual error"))
@patch("services.hermes.orchestrator.run_niche_research_for_account", side_effect=Exception("Niche error"))
@patch("services.hermes.orchestrator.record_agent_decision")
@patch("services.hermes.orchestrator.append_turn")
@patch("services.hermes.orchestrator.ToolBridge")
@patch("services.hermes.orchestrator.get_gemini_client")
async def test_run_session_auto_inject_exception_continues_with_none(
    mock_get_client, mock_tool_bridge_class, mock_append_turn, mock_record_decision,
    mock_niche_research, mock_visual_perf, mock_get_system_prompt
):
    mock_bridge = MagicMock()
    mock_bridge.discover_tools = AsyncMock(return_value=[])
    mock_bridge.dispatch = AsyncMock(return_value={})
    mock_tool_bridge_class.return_value = mock_bridge

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MockResponse(text="Done")
    mock_get_client.return_value = mock_client
    mock_get_system_prompt.return_value = "System prompt fallback"

    result = await run_session(account_id=20)

    assert result.error is None
    mock_get_system_prompt.assert_called_once_with(
        20,
        niche_brief=None,
        visual_perf_summary=None,
        references_summary=None,
    )


# --- Rate Limiting Fallback Test ---

def test_fallback_generative_model_429_falls_back_to_flash():
    from google.genai import errors

    with patch("services.hermes.orchestrator.get_gemini_client") as mock_get_client:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Success response from flash"

        def generate_side_effect(model, contents, config):
            if model == "gemini-pro-latest":
                raise errors.ClientError(code=429, response_json={}, response=MagicMock())
            return mock_response

        mock_client.models.generate_content.side_effect = generate_side_effect
        mock_get_client.return_value = mock_client

        fallback_model = _FallbackGenerativeModel(
            system_instruction="sys",
            tools=None,
            model_names=["gemini-pro-latest", "gemini-flash-latest"],
        )

        resp = fallback_model.generate_content([{"role": "user", "parts": [{"text": "hi"}]}])

        assert resp == mock_response
        assert fallback_model._resolved_name == "gemini-flash-latest"
        assert mock_client.models.generate_content.call_count == 2


def test_is_transient_gemini_error():
    from google.genai import errors
    import httpx

    # 429 ClientError -> True
    e_429 = errors.ClientError(code=429, response_json={}, response=MagicMock())
    assert _is_transient_gemini_error(e_429) is True

    # 400 ClientError -> False
    e_400 = errors.ClientError(code=400, response_json={}, response=MagicMock())
    assert _is_transient_gemini_error(e_400) is False

    # 503 ServerError -> True
    e_503 = errors.ServerError(code=503, response_json={}, response=MagicMock())
    assert _is_transient_gemini_error(e_503) is True

    # httpx.ReadTimeout (TimeoutException) -> True
    e_timeout = httpx.ReadTimeout("read timeout")
    assert _is_transient_gemini_error(e_timeout) is True

    # ValueError -> False
    e_val = ValueError("unexpected value")
    assert _is_transient_gemini_error(e_val) is False


def test_fallback_generative_model_503_falls_back_to_flash():
    from google.genai import errors

    with patch("services.hermes.orchestrator.get_gemini_client") as mock_get_client:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Success response from flash"

        def generate_side_effect(model, contents, config):
            if model == "gemini-pro-latest":
                raise errors.ServerError(code=503, response_json={}, response=MagicMock())
            return mock_response

        mock_client.models.generate_content.side_effect = generate_side_effect
        mock_get_client.return_value = mock_client

        fallback_model = _FallbackGenerativeModel(
            system_instruction="sys",
            tools=None,
            model_names=["gemini-pro-latest", "gemini-flash-latest"],
        )

        resp = fallback_model.generate_content([{"role": "user", "parts": [{"text": "hi"}]}])

        assert resp == mock_response
        assert fallback_model._resolved_name == "gemini-flash-latest"
        assert mock_client.models.generate_content.call_count == 2


def test_fallback_generative_model_read_timeout_falls_back_to_flash():
    import httpx

    with patch("services.hermes.orchestrator.get_gemini_client") as mock_get_client:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Success response from flash"

        def generate_side_effect(model, contents, config):
            if model == "gemini-pro-latest":
                raise httpx.ReadTimeout("deadline expired")
            return mock_response

        mock_client.models.generate_content.side_effect = generate_side_effect
        mock_get_client.return_value = mock_client

        fallback_model = _FallbackGenerativeModel(
            system_instruction="sys",
            tools=None,
            model_names=["gemini-pro-latest", "gemini-flash-latest"],
        )

        resp = fallback_model.generate_content([{"role": "user", "parts": [{"text": "hi"}]}])

        assert resp == mock_response
        assert fallback_model._resolved_name == "gemini-flash-latest"
        assert mock_client.models.generate_content.call_count == 2


def test_fallback_generative_model_400_propagates_without_fallback():
    from google.genai import errors

    with patch("services.hermes.orchestrator.get_gemini_client") as mock_get_client:
        mock_client = MagicMock()

        mock_client.models.generate_content.side_effect = errors.ClientError(
            code=400, response_json={}, response=MagicMock()
        )
        mock_get_client.return_value = mock_client

        fallback_model = _FallbackGenerativeModel(
            system_instruction="sys",
            tools=None,
            model_names=["gemini-pro-latest", "gemini-flash-latest"],
        )

        with pytest.raises(errors.ClientError) as exc_info:
            fallback_model.generate_content([{"role": "user", "parts": [{"text": "hi"}]}])

        assert exc_info.value.code == 400
        assert mock_client.models.generate_content.call_count == 1


def test_fallback_generative_model_resolved_pro_falls_back_on_later_turn():
    from google.genai import errors

    with patch("services.hermes.orchestrator.get_gemini_client") as mock_get_client:
        mock_client = MagicMock()
        mock_response_1 = MagicMock(text="Turn 1 from pro")
        mock_response_2 = MagicMock(text="Turn 2 from flash")

        fallback_model = _FallbackGenerativeModel(
            system_instruction="sys",
            tools=None,
            model_names=["gemini-pro-latest", "gemini-flash-latest"],
        )

        # Turn 1: pro succeeds
        mock_client.models.generate_content.return_value = mock_response_1
        mock_get_client.return_value = mock_client

        resp1 = fallback_model.generate_content([{"role": "user", "parts": [{"text": "turn 1"}]}])
        assert resp1 == mock_response_1
        assert fallback_model._resolved_name == "gemini-pro-latest"
        assert mock_client.models.generate_content.call_count == 1

        # Turn 2: pro throws 503 ServerError -> falls back to flash
        def turn2_side_effect(model, contents, config):
            if model == "gemini-pro-latest":
                raise errors.ServerError(code=503, response_json={}, response=MagicMock())
            return mock_response_2

        mock_client.models.generate_content.side_effect = turn2_side_effect

        resp2 = fallback_model.generate_content([{"role": "user", "parts": [{"text": "turn 2"}]}])
        assert resp2 == mock_response_2
        assert fallback_model._resolved_name == "gemini-flash-latest"
        assert mock_client.models.generate_content.call_count == 3


def test_fallback_generative_model_resolved_flash_does_not_retry_pro():
    from google.genai import errors

    with patch("services.hermes.orchestrator.get_gemini_client") as mock_get_client:
        mock_client = MagicMock()
        mock_response = MagicMock(text="Flash response")

        def turn1_side_effect(model, contents, config):
            if model == "gemini-pro-latest":
                raise errors.ClientError(code=429, response_json={}, response=MagicMock())
            return mock_response

        mock_client.models.generate_content.side_effect = turn1_side_effect
        mock_get_client.return_value = mock_client

        fallback_model = _FallbackGenerativeModel(
            system_instruction="sys",
            tools=None,
            model_names=["gemini-pro-latest", "gemini-flash-latest"],
        )

        # Turn 1: falls back to flash
        resp1 = fallback_model.generate_content([{"role": "user", "parts": [{"text": "turn 1"}]}])
        assert resp1 == mock_response
        assert fallback_model._resolved_name == "gemini-flash-latest"
        assert mock_client.models.generate_content.call_count == 2

        # Turn 2: pro must NOT be called again
        mock_client.models.generate_content.reset_mock()
        mock_client.models.generate_content.side_effect = None
        mock_client.models.generate_content.return_value = mock_response

        resp2 = fallback_model.generate_content([{"role": "user", "parts": [{"text": "turn 2"}]}])
        assert resp2 == mock_response
        assert mock_client.models.generate_content.call_count == 1
        called_model = mock_client.models.generate_content.call_args[1].get("model") or mock_client.models.generate_content.call_args[0][0]
        assert called_model == "gemini-flash-latest"


def test_fallback_generative_model_all_fail_raises_last_error():
    from google.genai import errors

    with patch("services.hermes.orchestrator.get_gemini_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = errors.ServerError(
            code=503, response_json={}, response=MagicMock()
        )
        mock_get_client.return_value = mock_client

        fallback_model = _FallbackGenerativeModel(
            system_instruction="sys",
            tools=None,
            model_names=["gemini-pro-latest", "gemini-flash-latest"],
        )

        with pytest.raises(errors.ServerError) as exc_info:
            fallback_model.generate_content([{"role": "user", "parts": [{"text": "hi"}]}])

        assert exc_info.value.code == 503
        assert mock_client.models.generate_content.call_count == 2


def test_fallback_generative_model_respects_timeout_env(monkeypatch):
    with patch("services.hermes.orchestrator.get_gemini_client") as mock_get_client:
        mock_client = MagicMock()
        mock_response = MagicMock(text="ok")
        mock_client.models.generate_content.return_value = mock_response
        mock_get_client.return_value = mock_client

        # Default timeout: 90s -> 90_000 ms
        monkeypatch.delenv("HERMES_GEMINI_TIMEOUT_S", raising=False)
        model_default = _FallbackGenerativeModel(
            system_instruction="sys",
            tools=None,
            model_names=["gemini-flash-latest"],
        )
        model_default.generate_content([{"role": "user", "parts": [{"text": "hi"}]}])
        call_kwargs = mock_client.models.generate_content.call_args[1]
        config = call_kwargs.get("config")
        assert config is not None
        assert config.http_options is not None
        assert config.http_options.timeout == 90_000

        # Custom timeout: 45s -> 45_000 ms
        mock_client.models.generate_content.reset_mock()
        monkeypatch.setenv("HERMES_GEMINI_TIMEOUT_S", "45")
        model_custom = _FallbackGenerativeModel(
            system_instruction="sys",
            tools=None,
            model_names=["gemini-flash-latest"],
        )
        model_custom.generate_content([{"role": "user", "parts": [{"text": "hi"}]}])
        call_kwargs = mock_client.models.generate_content.call_args[1]
        config = call_kwargs.get("config")
        assert config is not None
        assert config.http_options is not None
        assert config.http_options.timeout == 45_000
