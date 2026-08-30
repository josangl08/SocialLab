import pytest
import asyncio
from datetime import date
from unittest.mock import MagicMock, patch
from mcp.supabase_server import (
    mcp,
    supabase_get_posts,
    supabase_get_account,
    supabase_write_agent_log,
    supabase_create_post,
    supabase_create_proposal,
    supabase_list_visual_analyses,
    supabase_save_visual_analysis,
    supabase_get_campaign,
    supabase_get_planned_weeks,
    supabase_get_next_planning_week,
    supabase_update_last_sync,
    supabase_update_post_schedule,
    supabase_update_post_image
)
from models.schemas import CalendarSlot

def test_supabase_get_posts():
    with patch("mcp.supabase_server.get_supabase_admin_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.data = [{"id": 1, "caption": "Hello!"}]
        mock_client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = mock_response

        result = supabase_get_posts(instagram_account_id=123, limit=5)

        assert result == [{"id": 1, "caption": "Hello!"}]
        mock_client.table.assert_called_once_with("posts")

def test_supabase_get_account():
    with patch("mcp.supabase_server.get_supabase_admin_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.data = [{"id": 123, "username": "test_ig"}]
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

        result = supabase_get_account(instagram_account_id=123)

        assert result == {"id": 123, "username": "test_ig"}
        mock_client.table.assert_called_once_with("instagram_accounts")

def test_supabase_write_agent_log():
    with patch("mcp.supabase_server.get_supabase_admin_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.data = [{"id": 999, "account_id": 123}]
        mock_client.table.return_value.insert.return_value.execute.return_value = mock_response

        result = supabase_write_agent_log(
            account_id=123,
            images_scanned=10,
            images_analyzed=8,
            posts_drafted=5,
            error="None",
            duration_ms=5000
        )

        assert result == {"id": 999, "account_id": 123}
        mock_client.table.assert_called_once_with("agent_logs")

def test_supabase_create_post():
    with patch("mcp.supabase_server.get_supabase_admin_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.data = [{"id": 1, "content": "New Post"}]
        mock_client.table.return_value.insert.return_value.execute.return_value = mock_response

        result = supabase_create_post(
            instagram_account_id=123,
            caption="New Post",
            media_url="http://example.com/img.jpg",
            scheduled_publish_time="2026-07-30T10:00:00Z",
            media_product_type="FEED",
            drive_file_id="drive_123"
        )

        assert result == {"id": 1, "content": "New Post"}
        mock_client.table.assert_called_once_with("posts")
        mock_client.table.return_value.insert.assert_called_once_with({
            "instagram_account_id": 123,
            "content": "New Post",
            "media_url": "http://example.com/img.jpg",
            "scheduled_at": "2026-07-30T10:00:00Z",
            "post_type": "FEED",
            "drive_file_id": "drive_123",
            "status": "draft",
            "is_ai_generated": True
        })

def test_supabase_create_proposal():
    with patch("mcp.supabase_server.get_supabase_admin_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.data = [{"id": 2, "week_start": "2026-07-27"}]
        mock_client.table.return_value.insert.return_value.execute.return_value = mock_response

        result = supabase_create_proposal(
            instagram_account_id=123,
            week_start="2026-07-27",
            slots=[CalendarSlot(day="Monday", theme="match highlight", caption="cap 1")]
        )

        assert result == {"id": 2, "week_start": "2026-07-27"}
        mock_client.table.assert_called_once_with("content_proposals")
        mock_client.table.return_value.insert.assert_called_once_with({
            "account_id": 123,
            "week_start": "2026-07-27",
            "status": "pending_approval",
            "slots": [{
                "day": "Monday", "post_id": None, "image_id": None,
                "theme": "match highlight", "caption": "cap 1", "post_type": None
            }]
        })

def test_supabase_list_visual_analyses():
    with patch("mcp.supabase_server.get_supabase_admin_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.data = [{"id": 3, "account_id": 123}]
        mock_client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = mock_response

        result = supabase_list_visual_analyses(instagram_account_id=123, limit=5)

        assert result == [{"id": 3, "account_id": 123}]
        mock_client.table.assert_called_once_with("visual_analyses")

def test_supabase_save_visual_analysis():
    with patch("mcp.supabase_server.get_supabase_admin_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.data = [{"id": 4, "drive_file_id": "file_abc"}]
        mock_client.table.return_value.insert.return_value.execute.return_value = mock_response

        result = supabase_save_visual_analysis(
            instagram_account_id=123,
            drive_file_id="file_abc",
            analysis_result={"theme": "inspiring"}
        )

        assert result == {"id": 4, "drive_file_id": "file_abc"}
        mock_client.table.assert_called_once_with("visual_analyses")
        mock_client.table.return_value.insert.assert_called_once_with({
            "account_id": 123,
            "drive_file_id": "file_abc",
            "gemini_description": {"theme": "inspiring"}
        })

def test_supabase_get_campaign_no_campaign():
    with patch("mcp.supabase_server.get_supabase_admin_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_response = MagicMock()
        mock_response.data = []
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_response

        result = supabase_get_campaign(instagram_account_id=123, week_start="2026-07-20")

        assert result == {"has_campaign": False, "campaign_id": None, "context_text": "", "milestones_in_range": []}
        mock_client.table.assert_called_once_with("monthly_campaigns")


def test_supabase_get_campaign_focus_no_milestones():
    with patch("mcp.supabase_server.get_supabase_admin_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_response = MagicMock()
        mock_response.data = [{
            "id": 5,
            "title": "Verano 2026",
            "strategy_mode": "commercial_campaign",
            "weekly_focus": {"3": "Lanzamiento de la colección de verano"},
            "milestones": []
        }]
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_response

        # week_start 2026-07-20 -> day 20 -> week_of_month = ((20-1)//7)+1 = 3
        result = supabase_get_campaign(instagram_account_id=123, week_start="2026-07-20")

        assert result["has_campaign"] is True
        assert "Verano 2026" in result["context_text"]
        assert "Lanzamiento de la colección de verano" in result["context_text"]
        assert result["milestones_in_range"] == []
        mock_client.table.assert_called_once_with("monthly_campaigns")


def test_supabase_get_campaign_with_milestone_in_range():
    with patch("mcp.supabase_server.get_supabase_admin_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_response = MagicMock()
        mock_response.data = [{
            "id": 5,
            "title": "Historia de Julio",
            "strategy_mode": "personal_storyline",
            "weekly_focus": {},
            "milestones": [
                {"date": "2026-07-22", "event": "Aniversario de la marca"},
                {"date": "2026-08-01", "event": "Fuera de rango"}
            ]
        }]
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_response

        result = supabase_get_campaign(instagram_account_id=123, week_start="2026-07-20")

        assert result["has_campaign"] is True
        assert "Aniversario de la marca" in result["context_text"]
        assert len(result["milestones_in_range"]) == 1
        assert result["milestones_in_range"][0]["event"] == "Aniversario de la marca"

def test_supabase_get_planned_weeks():
    with patch("mcp.supabase_server.get_supabase_admin_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.data = [{"week_start": "2026-07-20"}, {"week_start": "2026-07-27"}]
        mock_client.table.return_value.select.return_value.eq.return_value.neq.return_value.execute.return_value = mock_response

        result = supabase_get_planned_weeks(instagram_account_id=123)

        assert result == ["2026-07-20", "2026-07-27"]
        mock_client.table.assert_called_once_with("content_proposals")


def test_supabase_get_next_planning_week_no_planned_weeks():
    with patch("mcp.supabase_server.get_supabase_admin_client") as mock_get_client, \
         patch("mcp.supabase_server.date") as mock_date:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_response = MagicMock()
        mock_response.data = []
        mock_client.table.return_value.select.return_value.eq.return_value.neq.return_value.execute.return_value = mock_response

        mock_date.today.return_value = date(2026, 7, 22)  # Wednesday

        result = supabase_get_next_planning_week(instagram_account_id=123)

        assert result == "2026-07-27"  # next Monday after Wed 2026-07-22


def test_supabase_get_next_planning_week_skips_covered_weeks():
    with patch("mcp.supabase_server.get_supabase_admin_client") as mock_get_client, \
         patch("mcp.supabase_server.date") as mock_date:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_response = MagicMock()
        mock_response.data = [{"week_start": "2026-07-27"}, {"week_start": "2026-08-03"}]
        mock_client.table.return_value.select.return_value.eq.return_value.neq.return_value.execute.return_value = mock_response

        mock_date.today.return_value = date(2026, 7, 22)  # Wednesday

        result = supabase_get_next_planning_week(instagram_account_id=123)

        assert result == "2026-08-10"  # first Monday not already planned


def test_supabase_get_next_planning_week_today_is_monday():
    with patch("mcp.supabase_server.get_supabase_admin_client") as mock_get_client, \
         patch("mcp.supabase_server.date") as mock_date:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_response = MagicMock()
        mock_response.data = []
        mock_client.table.return_value.select.return_value.eq.return_value.neq.return_value.execute.return_value = mock_response

        mock_date.today.return_value = date(2026, 7, 20)  # Monday

        result = supabase_get_next_planning_week(instagram_account_id=123)

        assert result == "2026-07-20"

def test_supabase_update_last_sync():
    with patch("mcp.supabase_server.get_supabase_admin_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.data = [{"id": 123, "last_agent_sync": "2026-07-22T13:49:00Z"}]
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = mock_response

        result = supabase_update_last_sync(instagram_account_id=123)

        assert "last_agent_sync" in result
        mock_client.table.assert_called_once_with("instagram_accounts")

@pytest.mark.asyncio
async def test_supabase_get_posts_via_mcp():
    with patch("mcp.supabase_server.get_supabase_admin_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.data = [{"id": 1}]
        mock_client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = mock_response

        response = await mcp.call_tool("supabase_get_posts", {"instagram_account_id": 123})
        
        assert len(response) == 1
        assert response[0].type == "text"
        assert "1" in response[0].text


def test_supabase_update_post_schedule():
    with patch("mcp.supabase_server.get_supabase_admin_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.data = [{"id": 10, "scheduled_at": "2026-07-30T15:00:00Z"}]
        mock_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = mock_response

        result = supabase_update_post_schedule(
            instagram_account_id=123,
            post_id=10,
            scheduled_at="2026-07-30T15:00:00Z"
        )

        assert result == {"id": 10, "scheduled_at": "2026-07-30T15:00:00Z"}
        mock_client.table.assert_called_once_with("posts")
        mock_client.table.return_value.update.assert_called_once_with({"scheduled_at": "2026-07-30T15:00:00Z"})


def test_supabase_update_post_image():
    with patch("mcp.supabase_server.get_supabase_admin_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.data = [{"id": 10, "drive_file_id": "drive_abc"}]
        mock_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = mock_response

        result = supabase_update_post_image(
            instagram_account_id=123,
            post_id=10,
            drive_file_id="drive_abc"
        )

        assert result == {"id": 10, "drive_file_id": "drive_abc"}
        mock_client.table.assert_called_once_with("posts")
        mock_client.table.return_value.update.assert_called_once_with({"drive_file_id": "drive_abc"})


@pytest.mark.asyncio
async def test_supabase_update_post_schedule_via_mcp():
    with patch("mcp.supabase_server.get_supabase_admin_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.data = [{"id": 10}]
        mock_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = mock_response

        response = await mcp.call_tool("supabase_update_post_schedule", {
            "instagram_account_id": 123,
            "post_id": 10,
            "scheduled_at": "2026-07-30T15:00:00Z"
        })
        
        assert len(response) == 1
        assert response[0].type == "text"
        assert "10" in response[0].text


@pytest.mark.asyncio
async def test_supabase_update_post_image_via_mcp():
    with patch("mcp.supabase_server.get_supabase_admin_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.data = [{"id": 10}]
        mock_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = mock_response

        response = await mcp.call_tool("supabase_update_post_image", {
            "instagram_account_id": 123,
            "post_id": 10,
            "drive_file_id": "drive_abc"
        })
        
        assert len(response) == 1
        assert response[0].type == "text"
        assert "10" in response[0].text

