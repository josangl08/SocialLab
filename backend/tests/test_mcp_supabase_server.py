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
        # instagram_accounts.select("user_id").eq(...).execute()
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"user_id": "user-abc"}]
        )

        result = supabase_create_post(
            instagram_account_id=123,
            caption="New Post",
            media_url="http://example.com/img.jpg",
            scheduled_publish_time="2026-07-30T10:00:00Z",
            media_product_type="FEED",
            drive_file_id="drive_123"
        )

        assert result == {"id": 1, "content": "New Post"}
        mock_client.table.assert_any_call("instagram_accounts")
        mock_client.table.assert_any_call("posts")
        inserted = mock_client.table.return_value.insert.call_args[0][0]
        quality_report = inserted.pop("quality_report")
        assert inserted == {
            "instagram_account_id": 123,
            "user_id": "user-abc",
            "content": "New Post",
            "media_url": "http://example.com/img.jpg",
            "scheduled_at": "2026-07-30T10:00:00Z",
            "post_type": "FEED",
            "drive_file_id": "drive_123",
            "status": "draft",
            "is_ai_generated": True,
            "content_format": None,
            "matrix_role": None,
            "trial_graduation": None,
        }
        assert quality_report["hashtag_count"] == 0


def test_supabase_create_post_user_id_none_when_account_missing():
    with patch("mcp.supabase_server.get_supabase_admin_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"id": 1, "content": "New Post"}]
        )
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

        result = supabase_create_post(instagram_account_id=999, caption="New Post")

        assert result == {"id": 1, "content": "New Post"}
        inserted = mock_client.table.return_value.insert.call_args[0][0]
        assert inserted["user_id"] is None

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
        mock_client.table.assert_any_call("instagram_accounts")
        mock_client.table.assert_any_call("content_proposals")
        mock_client.table.return_value.insert.assert_called_once_with({
            "account_id": 123,
            "week_start": "2026-07-27",
            "status": "pending_approval",
            "slots": [{
                "day": "Monday", "post_id": None, "image_id": None, "media_url": None,
                "theme": "match highlight", "caption": "cap 1", "post_type": None,
                "matrix_role": None, "hook_candidates": None
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

def test_supabase_get_campaign_pending_hidden_by_default():
    with patch("mcp.supabase_server.get_supabase_admin_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{
                "id": 5, "title": "Borrador", "status": "pending_approval",
                "strategy_mode": "personal_storyline",
                "weekly_focus": {"3": "Foco de la semana"}, "milestones": []
            }]
        )
        result = supabase_get_campaign(instagram_account_id=123, week_start="2026-07-20")
        assert result["has_campaign"] is False


def test_supabase_get_campaign_include_pending_returns_pending_campaign():
    with patch("mcp.supabase_server.get_supabase_admin_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{
                "id": 5, "title": "Borrador", "status": "pending_approval",
                "strategy_mode": "personal_storyline",
                "weekly_focus": {"3": "Foco de la semana"}, "milestones": []
            }]
        )
        result = supabase_get_campaign(instagram_account_id=123, week_start="2026-07-20", include_pending=True)
        assert result["has_campaign"] is True
        assert result["campaign_id"] == 5
        assert "Foco de la semana" in result["context_text"]


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
         patch("mcp.supabase_server.local_today") as mock_local_today:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_response = MagicMock()
        mock_response.data = []
        mock_client.table.return_value.select.return_value.eq.return_value.neq.return_value.execute.return_value = mock_response

        mock_local_today.return_value = date(2026, 7, 22)  # Wednesday

        result = supabase_get_next_planning_week(instagram_account_id=123)

        assert result == "2026-07-27"  # next Monday after Wed 2026-07-22


def test_supabase_get_next_planning_week_skips_covered_weeks():
    with patch("mcp.supabase_server.get_supabase_admin_client") as mock_get_client, \
         patch("mcp.supabase_server.local_today") as mock_local_today:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_response = MagicMock()
        mock_response.data = [{"week_start": "2026-07-27"}, {"week_start": "2026-08-03"}]
        mock_client.table.return_value.select.return_value.eq.return_value.neq.return_value.execute.return_value = mock_response

        mock_local_today.return_value = date(2026, 7, 22)  # Wednesday

        result = supabase_get_next_planning_week(instagram_account_id=123)

        assert result == "2026-08-10"  # first Monday not already planned


def test_supabase_get_next_planning_week_today_is_monday():
    with patch("mcp.supabase_server.get_supabase_admin_client") as mock_get_client, \
         patch("mcp.supabase_server.local_today") as mock_local_today:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_response = MagicMock()
        mock_response.data = []
        mock_client.table.return_value.select.return_value.eq.return_value.neq.return_value.execute.return_value = mock_response

        mock_local_today.return_value = date(2026, 7, 20)  # Monday

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
        
        assert len(response.content) == 1
        assert response.content[0].type == "text"
        assert "1" in response.content[0].text


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
        
        assert len(response.content) == 1
        assert response.content[0].type == "text"
        assert "10" in response.content[0].text


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
        
        assert len(response.content) == 1
        assert response.content[0].type == "text"
        assert "10" in response.content[0].text


def test_supabase_create_post_applies_humanize_and_hashtag_limit():
    with patch("mcp.supabase_server.get_supabase_admin_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"id": 101, "content": "Cleaned caption"}]
        )
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{
                "user_id": "user-abc",
                "humanizer_enabled": True,
                "banned_phrases": ["compra ya"]
            }]
        )

        raw_caption = (
            "Descubre este game-changer \u200b para tu negocio ——— compra ya hoy "
            "#uno #dos #tres #cuatro #cinco #seis #siete"
        )

        result = supabase_create_post(
            instagram_account_id=123,
            caption=raw_caption,
            content_format="reel",
            matrix_role="proof"
        )

        assert result == {"id": 101, "content": "Cleaned caption"}
        inserted = mock_client.table.return_value.insert.call_args[0][0]

        # Filtro de humanizado aplicado
        assert "\u200b" not in inserted["content"]
        assert "———" not in inserted["content"]
        assert "compra ya" not in inserted["content"]
        assert "game-changer" not in inserted["content"]

        # Límite duro de 5 hashtags aplicado (AD-7b)
        assert "#seis" not in inserted["content"]
        assert "#siete" not in inserted["content"]
        assert inserted["content"].count("#") <= 5

        # Metadatos persistidos
        assert inserted["content_format"] == "reel"
        assert inserted["matrix_role"] == "proof"
        assert "quality_report" in inserted
        assert isinstance(inserted["quality_report"], dict)
        assert "slop" in inserted["quality_report"]


def test_supabase_create_post_respects_humanizer_enabled_false():
    with patch("mcp.supabase_server.get_supabase_admin_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"id": 102, "content": "Post"}]
        )
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{
                "user_id": "user-abc",
                "humanizer_enabled": False,
                "banned_phrases": ["compra ya"]
            }]
        )

        raw_caption = "Este game-changer compra ya #uno #dos #tres #cuatro #cinco #seis"

        result = supabase_create_post(
            instagram_account_id=123,
            caption=raw_caption
        )

        assert result == {"id": 102, "content": "Post"}
        inserted = mock_client.table.return_value.insert.call_args[0][0]

        # Respeta humanizer_enabled=False: no altera términos vetados ni sintéticos
        assert "game-changer" in inserted["content"]
        assert "compra ya" in inserted["content"]

        # Pero enforce_hashtag_limit se mantiene (AD-7b)
        assert "#seis" not in inserted["content"]
        assert inserted["content"].count("#") <= 5
        assert "quality_report" in inserted


def test_supabase_create_post_idempotence():
    with patch("mcp.supabase_server.get_supabase_admin_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"id": 103, "content": "Clean"}]
        )
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{
                "user_id": "user-abc",
                "humanizer_enabled": True,
                "banned_phrases": []
            }]
        )

        clean_caption = "Entrenamiento de fuerza enfocado en técnica #fitness #gym #salud"

        supabase_create_post(instagram_account_id=123, caption=clean_caption)
        inserted_1 = mock_client.table.return_value.insert.call_args[0][0]

        # Aplicar el filtro sobre un texto ya limpio no lo modifica
        assert inserted_1["content"] == clean_caption


def test_supabase_create_proposal_saves_matrix_role_and_hook_candidates():
    with patch("mcp.supabase_server.get_supabase_admin_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"id": 201, "week_start": "2026-10-12"}]
        )

        slots = [
            CalendarSlot(
                day="Monday",
                theme="Proof of work",
                caption="Gancho elegido",
                post_type="reel",
                matrix_role="proof",
                hook_candidates=["Gancho 1", "Gancho 2", "Gancho 3"]
            )
        ]

        result = supabase_create_proposal(
            instagram_account_id=123,
            week_start="2026-10-12",
            slots=slots
        )

        assert result == {"id": 201, "week_start": "2026-10-12"}
        inserted = mock_client.table.return_value.insert.call_args[0][0]
        slot_data = inserted["slots"][0]
        assert slot_data["matrix_role"] == "proof"
        assert slot_data["hook_candidates"] == ["Gancho 1", "Gancho 2", "Gancho 3"]


def _proposal_client(mock_get_client, account):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{"id": 301}])
    mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[account]
    )
    return mock_client


def test_supabase_create_proposal_cleans_caption_and_hook_candidates():
    with patch("mcp.supabase_server.get_supabase_admin_client") as mock_get_client:
        mock_client = _proposal_client(mock_get_client, {"humanizer_enabled": True, "banned_phrases": ["compra ya"]})

        slots = [CalendarSlot(
            day="Monday", theme="t", post_type="reel", matrix_role="proof",
            caption="Un game-changer\u200b total, compra ya #a #b #c #d #e #f",
            hook_candidates=["Un game-changer total", "Compra ya y gana 40%", "Sin cambios aquí"],
        )]
        supabase_create_proposal(instagram_account_id=123, week_start="2026-10-12", slots=slots)

        slot = mock_client.table.return_value.insert.call_args[0][0]["slots"][0]
        assert "game-changer" not in slot["caption"]
        assert "\u200b" not in slot["caption"]
        assert "compra ya" not in slot["caption"]
        assert slot["caption"].count("#") == 5
        assert all("game-changer" not in h and "compra ya" not in h.lower() for h in slot["hook_candidates"])
        assert slot["hook_candidates"][2] == "Sin cambios aquí"


def test_supabase_create_proposal_respects_humanizer_disabled():
    with patch("mcp.supabase_server.get_supabase_admin_client") as mock_get_client:
        mock_client = _proposal_client(mock_get_client, {"humanizer_enabled": False, "banned_phrases": []})

        slots = [CalendarSlot(
            day="Monday", theme="t", post_type="reel", caption="Un game-changer",
            hook_candidates=["Un game-changer", "Otro", "Tercero"],
        )]
        supabase_create_proposal(instagram_account_id=123, week_start="2026-10-12", slots=slots)

        slot = mock_client.table.return_value.insert.call_args[0][0]["slots"][0]
        assert slot["caption"] == "Un game-changer"
        assert slot["hook_candidates"][0] == "Un game-changer"


def _create_post_with_trial(content_format):
    with patch("mcp.supabase_server.get_supabase_admin_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{"id": 1}])
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"user_id": "user-abc", "humanizer_enabled": True, "banned_phrases": []}]
        )
        supabase_create_post(
            instagram_account_id=123, caption="Gancho\nCuerpo",
            content_format=content_format, trial_graduation="MANUAL",
        )
        return mock_client.table.return_value.insert.call_args[0][0]


def test_supabase_create_post_trial_reel():
    """Hermes puede crear un Reel como Trial Reel (AD-10)."""
    assert _create_post_with_trial("reel")["trial_graduation"] == "MANUAL"


def test_supabase_create_post_trial_ignored_outside_reels():
    assert _create_post_with_trial("post")["trial_graduation"] is None
    assert _create_post_with_trial(None)["trial_graduation"] is None


def test_supabase_create_post_normalizes_schedule_time_without_offset():
    with patch("mcp.supabase_server.get_supabase_admin_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{"id": 1}])
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{
                "user_id": "user-abc",
                "humanizer_enabled": True,
                "banned_phrases": [],
                "primary_timezone": "Europe/Madrid",
            }]
        )

        supabase_create_post(
            instagram_account_id=123,
            caption="Post sin offset",
            scheduled_publish_time="2026-10-14T20:00:00",
        )

        inserted = mock_client.table.return_value.insert.call_args[0][0]
        # En Europe/Madrid (UTC+2 CEST), 20:00 hora local es 18:00 UTC
        assert "18:00:00" in inserted["scheduled_at"]


def test_supabase_create_post_respects_schedule_time_with_offset():
    with patch("mcp.supabase_server.get_supabase_admin_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{"id": 1}])
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{
                "user_id": "user-abc",
                "humanizer_enabled": True,
                "banned_phrases": [],
                "primary_timezone": "Europe/Madrid",
            }]
        )

        supabase_create_post(
            instagram_account_id=123,
            caption="Post con offset +08:00",
            scheduled_publish_time="2026-10-14T20:00:00+08:00",
        )

        inserted = mock_client.table.return_value.insert.call_args[0][0]
        # Con offset explícito +08:00, 20:00 es 12:00 UTC
        assert "12:00:00" in inserted["scheduled_at"]



def test_supabase_update_post_schedule_without_offset_uses_account_timezone():
    with patch("mcp.supabase_server.get_supabase_admin_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"primary_timezone": "Europe/Madrid", "detected_timezone": None}]
        )
        mock_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": 10, "scheduled_at": "2026-10-26T17:00:00Z"}]
        )

        supabase_update_post_schedule(instagram_account_id=123, post_id=10, scheduled_at="2026-10-26T18:00:00")

        # 26-oct-2026 ya es horario de invierno en Madrid (UTC+1)
        mock_client.table.return_value.update.assert_called_once_with({"scheduled_at": "2026-10-26T17:00:00Z"})


def test_supabase_get_next_planning_week_uses_account_local_date():
    # 2026-10-18 20:00 UTC ya es lunes 19 en Asia/Kuching: la semana a planificar es la que empieza hoy
    from datetime import datetime, timezone
    with patch("mcp.supabase_server.get_supabase_admin_client") as mock_get_client, \
         patch("services.account_timezone.get_supabase_admin_client") as mock_tz_client, \
         patch("utils.timezones.datetime") as mock_dt:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.neq.return_value.execute.return_value = MagicMock(data=[])
        mock_tz_client.return_value.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"primary_timezone": "Asia/Kuching", "detected_timezone": None}]
        )
        mock_dt.now.return_value = datetime(2026, 10, 18, 20, 0, tzinfo=timezone.utc)

        result = supabase_get_next_planning_week(instagram_account_id=123)

        assert result == "2026-10-19"


# --- Días específicos estrictos (AD-3) ---

def _create_post_with_account(account: dict, scheduled: str) -> dict:
    with patch("mcp.supabase_server.get_supabase_admin_client") as mock_get_client, \
            patch("mcp.supabase_server.local_today", return_value=date(2026, 11, 2)):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{"id": 1}])
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"user_id": "user-abc", "primary_timezone": "Europe/Madrid", **account}]
        )
        occupied = mock_client.table.return_value.select.return_value.eq.return_value \
            .neq.return_value.eq.return_value.gte.return_value.lt.return_value
        occupied.execute.return_value = MagicMock(data=[])
        supabase_create_post(instagram_account_id=7, caption="Post", scheduled_publish_time=scheduled)
        return mock_client.table.return_value.insert.call_args[0][0]


def test_supabase_create_post_moves_post_to_allowed_day():
    inserted = _create_post_with_account(
        {"scheduling_mode": "fixed", "preferred_days": ["Tuesday", "Thursday"]},
        "2026-11-06T20:00:00+01:00",  # viernes
    )
    assert inserted["scheduled_at"] == "2026-11-05T19:00:00Z"  # jueves, misma hora local
    assert inserted["quality_report"]["schedule_adjustment"] == {
        "from": "2026-11-06T20:00:00+01:00",
        "to": "2026-11-05T20:00:00+01:00",
        "reason": "fixed_days",
    }


def test_supabase_create_post_allowed_day_has_no_adjustment():
    inserted = _create_post_with_account(
        {"scheduling_mode": "fixed", "preferred_days": ["Tuesday", "Thursday"]},
        "2026-11-05T20:00:00+01:00",
    )
    assert inserted["scheduled_at"] == "2026-11-05T19:00:00Z"
    assert "schedule_adjustment" not in inserted["quality_report"]


def test_supabase_create_post_flexible_mode_not_corrected():
    inserted = _create_post_with_account(
        {"scheduling_mode": "flexible", "preferred_days": ["Tuesday"]},
        "2026-11-06T20:00:00+01:00",
    )
    assert inserted["scheduled_at"] == "2026-11-06T19:00:00Z"
    assert "schedule_adjustment" not in inserted["quality_report"]
