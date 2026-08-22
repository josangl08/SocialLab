import pytest
import time
import threading
from unittest.mock import patch, MagicMock, AsyncMock
from main import run_agent_for_all_accounts, run_monthly_strategy_for_all_accounts
from services.hermes.monthly_strategy import MonthlyStrategyResult

def test_run_agent_for_all_accounts_empty():
    """Comportamiento con lista de cuentas vacía (no debe fallar)."""
    mock_supabase = MagicMock()
    mock_response = MagicMock()
    mock_response.data = []
    mock_supabase.table.return_value.select.return_value.execute.return_value = mock_response

    with patch("main.admin_supabase", mock_supabase), \
         patch("services.agent_service.run_agent") as mock_run:
        
        # No exception should be raised
        run_agent_for_all_accounts()
        
        mock_run.assert_not_called()

def test_run_agent_for_all_accounts_concurrency_and_isolation():
    """
    Ejecución concurrente de múltiples cuentas, respeto al semáforo de límite 2,
    y que una excepción en una cuenta no impida que se procesen las demás.
    """
    accounts = [
        {"id": "acc-1", "is_active": True},
        {"id": "acc-error", "is_active": True},
        {"id": "acc-2", "is_active": True},
        {"id": "acc-inactive", "is_active": False},
    ]
    
    mock_supabase = MagicMock()
    mock_response = MagicMock()
    mock_response.data = accounts
    mock_supabase.table.return_value.select.return_value.execute.return_value = mock_response

    processed_accounts = []
    active_threads = 0
    max_active_threads = 0
    lock = threading.Lock()

    def side_effect(account_id):
        nonlocal active_threads, max_active_threads
        with lock:
            active_threads += 1
            if active_threads > max_active_threads:
                max_active_threads = active_threads
        
        # Simulate some delay to check concurrency
        time.sleep(0.1)
        
        with lock:
            active_threads -= 1
            processed_accounts.append(account_id)
            
        if account_id == "acc-error":
            raise Exception("Mock agent execution error")

    with patch("main.admin_supabase", mock_supabase), \
         patch("services.agent_service.run_agent", side_effect=side_effect) as mock_run:
        
        # No error should propagate out of the cron job
        run_agent_for_all_accounts()
        
        # Confirm run_agent was called for active accounts only
        assert "acc-1" in processed_accounts
        assert "acc-error" in processed_accounts
        assert "acc-2" in processed_accounts
        assert "acc-inactive" not in processed_accounts
        
        # We had 3 active accounts. The semaphore limit is 2.
        # So we expect max_active_threads to be exactly 2.
        assert max_active_threads == 2


def test_run_monthly_strategy_for_all_accounts_skips_outside_window():
    """Más de 2 días para fin de mes: no debe tocar ninguna cuenta."""
    with patch("main._days_until_month_end", return_value=5), \
         patch("services.hermes.monthly_strategy.run_monthly_strategy_session") as mock_run:
        run_monthly_strategy_for_all_accounts()
        mock_run.assert_not_called()


def test_run_monthly_strategy_for_all_accounts_sends_card_only_when_created_and_isolates_errors():
    """
    Dentro de la ventana (<=2 días para fin de mes): cuentas inactivas se ignoran,
    la tarjeta de Telegram solo se envía cuando created=True, y una excepción en
    una cuenta no impide procesar las demás (mismo patrón de aislamiento que el
    cron semanal).
    """
    accounts = [
        {"id": 1, "telegram_chat_id": "111", "is_active": True},
        {"id": 2, "telegram_chat_id": "222", "is_active": True},
        {"id": 3, "telegram_chat_id": "333", "is_active": True},
        {"id": 4, "telegram_chat_id": "444", "is_active": False},
    ]
    campaign_row = {"id": "camp-1", "account_id": 1, "title": "Test"}

    async def fake_run_session(account_id):
        if account_id == 1:
            return MonthlyStrategyResult(account_id=1, created=True, campaign_id="camp-1")
        if account_id == 2:
            raise Exception("boom")
        return MonthlyStrategyResult(account_id=account_id, created=False)

    def table_side_effect(name):
        m = MagicMock()
        if name == "instagram_accounts":
            m.select.return_value.execute.return_value = MagicMock(data=accounts)
        elif name == "monthly_campaigns":
            m.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[campaign_row])
        return m

    mock_supabase = MagicMock()
    mock_supabase.table.side_effect = table_side_effect

    mock_telegram = MagicMock()
    mock_telegram.send_campaign_approval_card = AsyncMock()

    with patch("main._days_until_month_end", return_value=1), \
         patch("main.admin_supabase", mock_supabase), \
         patch("services.hermes.monthly_strategy.run_monthly_strategy_session", side_effect=fake_run_session), \
         patch("services.telegram_service.TelegramService", return_value=mock_telegram):
        # No exception should propagate out of the cron job despite account 2 failing.
        run_monthly_strategy_for_all_accounts()

    # Card sent only for the account whose session actually created a campaign.
    mock_telegram.send_campaign_approval_card.assert_awaited_once_with("111", campaign_row)
