# ABOUTME: Test suite for agent monthly campaign API routes (GET, POST /campaign).
# Auth: Antigravity CLI

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from main import app
from auth.dependencies import get_current_user
from models.schemas import User, MonthlyCampaign
from tests.conftest import USER_ID

# Mock current user
async def mock_get_current_user():
    return User(id=USER_ID, email="test@example.com")

# Apply dependency override
app.dependency_overrides[get_current_user] = mock_get_current_user

client = TestClient(app)

@pytest.fixture
def mock_agent_supabase():
    with patch("routes.agent_routes.supabase") as mock_sup:
        yield mock_sup

@pytest.fixture
def mock_agent_admin_supabase():
    with patch("routes.agent_routes.admin_supabase") as mock_sup_admin:
        yield mock_sup_admin


def test_upsert_campaign_success(mock_agent_supabase, mock_agent_admin_supabase):
    account_id = 12
    month_date = "2026-07-01"
    
    # 1. Mock account ownership check
    mock_acc_exec = MagicMock()
    mock_acc_exec.execute.return_value = MagicMock(data=[{"user_id": USER_ID}])
    
    # 2. Mock campaign upsert execution
    mock_upsert_exec = MagicMock()
    mock_upsert_exec.execute.return_value = MagicMock(data=[{
        "id": "campaign-uuid-123",
        "account_id": account_id,
        "month_date": month_date,
        "strategy_mode": "personal_storyline",
        "title": "Viaje a Japón",
        "description": "Viaje por Tokio",
        "milestones": [{"date": "2026-07-15", "event": "Llegada"}],
        "weekly_focus": {"1": "Prep"}
    }])

    def mock_table_admin(name):
        mock_t = MagicMock()
        if name == "instagram_accounts":
            mock_t.select.return_value.eq.return_value = mock_acc_exec
        elif name == "monthly_campaigns":
            mock_t.upsert.return_value = mock_upsert_exec
        return mock_t

    mock_agent_admin_supabase.table.side_effect = mock_table_admin

    payload = {
        "account_id": account_id,
        "month_date": month_date,
        "strategy_mode": "personal_storyline",
        "title": "Viaje a Japón",
        "description": "Viaje por Tokio",
        "milestones": [{"date": "2026-07-15", "event": "Llegada"}],
        "weekly_focus": {"1": "Prep"}
    }
    response = client.post("/api/agent/campaign", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "campaign-uuid-123"
    assert data["title"] == "Viaje a Japón"
    assert data["strategy_mode"] == "personal_storyline"
    mock_agent_admin_supabase.table.assert_any_call("instagram_accounts")
    mock_agent_admin_supabase.table.assert_any_call("monthly_campaigns")


def test_upsert_campaign_forbidden(mock_agent_supabase, mock_agent_admin_supabase):
    account_id = 12
    
    # Mock account ownership with a different user ID
    mock_acc_exec = MagicMock()
    mock_acc_exec.execute.return_value = MagicMock(data=[{"user_id": "other-user"}])
    mock_agent_admin_supabase.table.return_value.select.return_value.eq.return_value = mock_acc_exec

    payload = {
        "account_id": account_id,
        "month_date": "2026-07-01",
        "strategy_mode": "personal_storyline",
        "title": "Viaje a Japón"
    }
    response = client.post("/api/agent/campaign", json=payload)
    
    assert response.status_code == 403
    assert "No tienes acceso" in response.json()["detail"]


def test_upsert_campaign_not_found(mock_agent_supabase, mock_agent_admin_supabase):
    account_id = 12
    
    # Mock account not existing (empty data)
    mock_acc_exec = MagicMock()
    mock_acc_exec.execute.return_value = MagicMock(data=[])
    mock_agent_admin_supabase.table.return_value.select.return_value.eq.return_value = mock_acc_exec

    payload = {
        "account_id": account_id,
        "month_date": "2026-07-01",
        "strategy_mode": "personal_storyline",
        "title": "Viaje a Japón"
    }
    response = client.post("/api/agent/campaign", json=payload)
    
    assert response.status_code == 404
    assert "no encontrada" in response.json()["detail"]


def test_get_campaign_success(mock_agent_supabase, mock_agent_admin_supabase):
    account_id = 12
    month_date = "2026-07-01"
    
    # 1. Mock account ownership check
    mock_acc_exec = MagicMock()
    mock_acc_exec.execute.return_value = MagicMock(data=[{"user_id": USER_ID}])
    mock_agent_admin_supabase.table.return_value.select.return_value.eq.return_value = mock_acc_exec
    
    # 2. Mock campaign select query
    mock_campaign_exec = MagicMock()
    mock_campaign_exec.execute.return_value = MagicMock(data=[{
        "id": "campaign-uuid-123",
        "account_id": account_id,
        "month_date": month_date,
        "strategy_mode": "personal_storyline",
        "title": "Viaje a Japón",
        "description": "Viaje por Tokio",
        "milestones": [{"date": "2026-07-15", "event": "Llegada"}],
        "weekly_focus": {"1": "Prep"}
    }])
    mock_agent_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value = mock_campaign_exec

    response = client.get(f"/api/agent/campaign?account_id={account_id}&month_date={month_date}")
    
    assert response.status_code == 200
    data = response.json()
    assert data is not None
    assert data["id"] == "campaign-uuid-123"
    assert data["title"] == "Viaje a Japón"


def test_get_campaign_none(mock_agent_supabase, mock_agent_admin_supabase):
    account_id = 12
    month_date = "2026-07-01"
    
    # 1. Mock account ownership check
    mock_acc_exec = MagicMock()
    mock_acc_exec.execute.return_value = MagicMock(data=[{"user_id": USER_ID}])
    mock_agent_admin_supabase.table.return_value.select.return_value.eq.return_value = mock_acc_exec
    
    # 2. Mock campaign select query returning empty list
    mock_campaign_exec = MagicMock()
    mock_campaign_exec.execute.return_value = MagicMock(data=[])
    mock_agent_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value = mock_campaign_exec

    response = client.get(f"/api/agent/campaign?account_id={account_id}&month_date={month_date}")
    
    assert response.status_code == 200
    assert response.json() is None
