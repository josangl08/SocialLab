import pytest
import time
import threading
from unittest.mock import patch, MagicMock
from main import run_agent_for_all_accounts

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
