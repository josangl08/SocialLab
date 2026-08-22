import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from services.agent_service import run_agent, _dispatch_telegram_proposal
from services.hermes.orchestrator import HermesSessionResult


ACCOUNT = {"telegram_chat_id": "999", "user_id": "user-1", "username": "test"}


def test_dispatch_telegram_proposal_no_chat_id_is_not_an_error():
    supabase = MagicMock()
    account = {"user_id": "user-1"}

    result = _dispatch_telegram_proposal(supabase, 7, account, "prop-1")

    assert result is None
    supabase.table.assert_not_called()


def test_dispatch_telegram_proposal_missing_proposal_returns_error():
    supabase = MagicMock()
    supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

    result = _dispatch_telegram_proposal(supabase, 7, ACCOUNT, "prop-missing")

    assert result is not None
    assert "prop-missing" in result


@patch("services.telegram_service.TelegramService")
def test_dispatch_telegram_proposal_success(mock_telegram_cls):
    supabase = MagicMock()
    supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"id": "prop-1", "slots": [{"day": "Monday"}]}]
    )
    mock_service = MagicMock()
    mock_service.send_proposal_card = AsyncMock()
    mock_telegram_cls.return_value = mock_service

    result = _dispatch_telegram_proposal(supabase, 7, ACCOUNT, "prop-1")

    assert result is None
    mock_service.send_proposal_card.assert_called_once()


@patch("services.telegram_service.TelegramService")
def test_dispatch_telegram_proposal_send_failure_returns_error(mock_telegram_cls):
    supabase = MagicMock()
    supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"id": "prop-1", "slots": []}]
    )
    mock_service = MagicMock()
    mock_service.send_proposal_card = AsyncMock(side_effect=RuntimeError("network down"))
    mock_telegram_cls.return_value = mock_service

    result = _dispatch_telegram_proposal(supabase, 7, ACCOUNT, "prop-1")

    assert result is not None
    assert "telegram_dispatch_failed" in result


@patch("services.agent_service._write_agent_log")
@patch("services.agent_service._dispatch_telegram_proposal")
@patch("services.agent_service.run_session")
@patch("services.agent_service.get_supabase_admin_client")
def test_run_agent_dispatches_telegram_only_when_proposal_id_present(
    mock_get_client, mock_run_session, mock_dispatch, mock_write_log
):
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[ACCOUNT]
    )
    mock_get_client.return_value = mock_client

    mock_run_session.return_value = HermesSessionResult(
        images_scanned=1, images_analyzed=1, posts_drafted=3, proposal_id="prop-1", error=None
    )
    mock_dispatch.return_value = None

    run_agent(account_id=7)

    mock_dispatch.assert_called_once_with(mock_client, 7, ACCOUNT, "prop-1")


@patch("services.agent_service._write_agent_log")
@patch("services.agent_service._dispatch_telegram_proposal")
@patch("services.agent_service.run_session")
@patch("services.agent_service.get_supabase_admin_client")
def test_run_agent_skips_telegram_when_no_proposal_created(
    mock_get_client, mock_run_session, mock_dispatch, mock_write_log
):
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[ACCOUNT]
    )
    mock_get_client.return_value = mock_client

    mock_run_session.return_value = HermesSessionResult(
        images_scanned=0, images_analyzed=0, posts_drafted=0, proposal_id=None, error=None
    )

    run_agent(account_id=7)

    mock_dispatch.assert_not_called()


@patch("services.agent_service._write_agent_log")
@patch("services.agent_service._dispatch_telegram_proposal")
@patch("services.agent_service.run_session")
@patch("services.agent_service.get_supabase_admin_client")
def test_run_agent_surfaces_telegram_failure_only_when_no_prior_error(
    mock_get_client, mock_run_session, mock_dispatch, mock_write_log
):
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[ACCOUNT]
    )
    mock_get_client.return_value = mock_client

    mock_run_session.return_value = HermesSessionResult(
        images_scanned=1, images_analyzed=1, posts_drafted=3, proposal_id="prop-1", error=None
    )
    mock_dispatch.return_value = "telegram_dispatch_failed: boom"

    log = run_agent(account_id=7)

    assert log.error == "telegram_dispatch_failed: boom"


@patch("services.agent_service._write_agent_log")
@patch("services.agent_service._dispatch_telegram_proposal")
@patch("services.agent_service.run_session")
@patch("services.agent_service.get_supabase_admin_client")
def test_run_agent_keeps_session_error_over_telegram_failure(
    mock_get_client, mock_run_session, mock_dispatch, mock_write_log
):
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[ACCOUNT]
    )
    mock_get_client.return_value = mock_client

    mock_run_session.return_value = HermesSessionResult(
        images_scanned=1, images_analyzed=1, posts_drafted=3, proposal_id="prop-1",
        error="gemini_error: boom"
    )
    mock_dispatch.return_value = "telegram_dispatch_failed: should not surface"

    log = run_agent(account_id=7)

    assert log.error == "gemini_error: boom"
