import logging
from datetime import datetime, timedelta, date
from typing import Optional, List, Dict, Any
from mcp.server.fastmcp import FastMCP
from database.supabase_client import get_supabase_admin_client
from models.schemas import CalendarSlot

logger = logging.getLogger(__name__)

mcp = FastMCP("Supabase Database Server")

@mcp.tool()
def supabase_get_posts(instagram_account_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """Retrieve posts for a specific Instagram account ID, up to a limit."""
    supabase = get_supabase_admin_client()
    response = supabase.table("posts").select("*").eq("instagram_account_id", instagram_account_id).limit(limit).execute()
    return response.data or []

@mcp.tool()
def supabase_get_account(instagram_account_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve account details for a specific Instagram account ID."""
    supabase = get_supabase_admin_client()
    response = supabase.table("instagram_accounts").select("*").eq("id", instagram_account_id).execute()
    if response.data and len(response.data) > 0:
        return response.data[0]
    return None

@mcp.tool()
def supabase_write_agent_log(
    account_id: int,
    images_scanned: int,
    images_analyzed: int,
    posts_drafted: int,
    error: Optional[str] = None,
    duration_ms: int = 0
) -> Dict[str, Any]:
    """Write an execution log for the agent to the agent_logs table."""
    supabase = get_supabase_admin_client()
    log_data = {
        'account_id': account_id,
        'images_scanned': images_scanned,
        'images_analyzed': images_analyzed,
        'posts_drafted': posts_drafted,
        'error': error,
        'duration_ms': duration_ms
    }
    response = supabase.table("agent_logs").insert(log_data).execute()
    if response.data and len(response.data) > 0:
        return response.data[0]
    return {}

@mcp.tool()
def supabase_create_post(
    instagram_account_id: int,
    caption: str,
    media_url: Optional[str] = None,
    scheduled_publish_time: Optional[str] = None,
    media_product_type: str = "FEED",
    drive_file_id: Optional[str] = None
) -> Dict[str, Any]:
    """Create a new post draft in the posts table."""
    supabase = get_supabase_admin_client()
    # Resolve the owning user_id from the account: this tool runs with the
    # service-role client (bypasses RLS), but /api/posts reads with the user's
    # client (RLS: user_id = auth.uid()), so a post without user_id is invisible
    # in the calendar even though it exists.
    acc_res = supabase.table("instagram_accounts").select("user_id").eq("id", instagram_account_id).execute()
    user_id: Optional[str] = acc_res.data[0].get("user_id") if acc_res.data else None
    if user_id is None:
        logger.warning("supabase_create_post: no user_id for instagram_account_id=%s", instagram_account_id)
    post_data = {
        "instagram_account_id": instagram_account_id,
        "user_id": user_id,
        "content": caption,
        "media_url": media_url,
        "scheduled_at": scheduled_publish_time,
        "post_type": media_product_type,
        "drive_file_id": drive_file_id,
        "status": "draft",
        "is_ai_generated": True
    }
    response = supabase.table("posts").insert(post_data).execute()
    if response.data and len(response.data) > 0:
        return response.data[0]
    return {}

@mcp.tool()
def supabase_create_proposal(
    instagram_account_id: int,
    week_start: str,
    slots: Optional[List[CalendarSlot]] = None
) -> Dict[str, Any]:
    """Create a new content proposal for a week. Each slot MUST include day, theme
    and caption (post_id, image_id, post_type are optional) — this shape is what
    the planner UI renders, so an incomplete slot won't display correctly. status
    is not a caller-settable param — a new proposal always starts pending_approval,
    same principle as supabase_create_monthly_campaign hardcoding its own status."""
    supabase = get_supabase_admin_client()
    proposal_data = {
        "account_id": instagram_account_id,
        "week_start": week_start,
        "status": "pending_approval",
        "slots": [s.model_dump() for s in (slots or [])]
    }
    response = supabase.table("content_proposals").insert(proposal_data).execute()
    if response.data and len(response.data) > 0:
        return response.data[0]
    return {}

@mcp.tool()
def supabase_list_visual_analyses(instagram_account_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """Retrieve visual analyses for a specific Instagram account ID, up to a limit."""
    supabase = get_supabase_admin_client()
    response = supabase.table("visual_analyses").select("*").eq("account_id", instagram_account_id).limit(limit).execute()
    return response.data or []

@mcp.tool()
def supabase_save_visual_analysis(
    instagram_account_id: int,
    drive_file_id: str,
    analysis_result: Dict[str, Any]
) -> Dict[str, Any]:
    """Save a new visual analysis record."""
    supabase = get_supabase_admin_client()
    analysis_data = {
        "account_id": instagram_account_id,
        "drive_file_id": drive_file_id,
        "gemini_description": analysis_result
    }
    response = supabase.table("visual_analyses").insert(analysis_data).execute()
    if response.data and len(response.data) > 0:
        return response.data[0]
    return {}

@mcp.tool()
def supabase_get_campaign(instagram_account_id: int, week_start: str, include_pending: bool = False) -> Dict[str, Any]:
    """Retrieve the monthly campaign context for the week starting on week_start
    (YYYY-MM-DD): a formatted text of this week's narrative/commercial focus plus
    any milestones landing in that week. Returns has_campaign=False when there's no
    campaign configured for that month. By default only an approved campaign is
    considered — a pending Hermes draft never leaks into caption generation unless
    the caller explicitly opts in with include_pending=True."""
    supabase = get_supabase_admin_client()
    week_start_date = date.fromisoformat(week_start)
    month_date = week_start_date.replace(day=1).isoformat()

    response = supabase.table("monthly_campaigns")\
        .select("*")\
        .eq("account_id", instagram_account_id)\
        .eq("month_date", month_date)\
        .execute()
    campaign = response.data[0] if response.data else None

    if campaign and not include_pending and campaign.get("status", "approved") != "approved":
        campaign = None

    if not campaign:
        return {"has_campaign": False, "campaign_id": None, "context_text": "", "milestones_in_range": []}

    week_of_month = min(((week_start_date.day - 1) // 7) + 1, 4)
    focus = (campaign.get("weekly_focus") or {}).get(str(week_of_month), "").strip()

    week_end = week_start_date + timedelta(days=6)
    milestones_in_range = [
        m for m in (campaign.get("milestones") or [])
        if m.get("date") and week_start_date.isoformat() <= m["date"] <= week_end.isoformat()
    ]

    if not focus and not milestones_in_range:
        return {"has_campaign": True, "campaign_id": campaign["id"], "context_text": "", "milestones_in_range": []}

    strategy_mode = campaign.get("strategy_mode", "personal_storyline")
    title = campaign.get("title", "")

    if strategy_mode == "commercial_campaign":
        parts = [f"ENFOQUE DE CAMPAÑA DEL MES: '{title}' (campaña comercial)."]
        if focus:
            parts.append(f"Foco de esta semana: {focus}. Alinea el lenguaje y las CTAs con este objetivo del embudo.")
    else:
        parts = [f"HILO NARRATIVO DEL MES: '{title}' (historia personal)."]
        if focus:
            parts.append(f"Esta semana el hilo se centra en: {focus}. Continúa la narrativa en primera persona.")

    if milestones_in_range:
        events = "; ".join(f"{m['date']}: {m['event']}" for m in milestones_in_range)
        parts.append(f"Hitos de esta semana ({events}) — asegúrate de que al menos un post los mencione explícitamente.")

    return {
        "has_campaign": True,
        "campaign_id": campaign["id"],
        "context_text": " ".join(parts),
        "milestones_in_range": milestones_in_range
    }

def _fetch_planned_weeks(supabase, instagram_account_id: int) -> List[str]:
    response = supabase.table("content_proposals")\
        .select("week_start")\
        .eq("account_id", instagram_account_id)\
        .neq("status", "rejected")\
        .execute()
    return [row["week_start"] for row in response.data] if response.data else []


@mcp.tool()
def supabase_get_planned_weeks(instagram_account_id: int) -> List[str]:
    """Retrieve list of week starts that already have proposals (not rejected)."""
    supabase = get_supabase_admin_client()
    return _fetch_planned_weeks(supabase, instagram_account_id)


@mcp.tool()
def supabase_get_next_planning_week(instagram_account_id: int) -> str:
    """Deterministically computes the next Monday (week_start, YYYY-MM-DD) not
    covered by a non-rejected proposal, starting from today. Hermes must use this
    value as-is when choosing which week to plan — do not recompute it."""
    supabase = get_supabase_admin_client()
    planned = set(_fetch_planned_weeks(supabase, instagram_account_id))
    today = date.today()
    candidate = today + timedelta(days=(7 - today.weekday()) % 7)
    while candidate.isoformat() in planned:
        candidate += timedelta(days=7)
    return candidate.isoformat()

@mcp.tool()
def supabase_update_last_sync(instagram_account_id: int) -> Dict[str, Any]:
    """Update last_agent_sync timestamp to now for the given Instagram account ID."""
    from datetime import datetime, timezone
    supabase = get_supabase_admin_client()
    now_iso = datetime.now(timezone.utc).isoformat()
    response = supabase.table("instagram_accounts")\
        .update({"last_agent_sync": now_iso})\
        .eq("id", instagram_account_id)\
        .execute()
    if response.data and len(response.data) > 0:
        return response.data[0]
    return {}


@mcp.tool()
def supabase_update_post_schedule(
    instagram_account_id: int,
    post_id: int,
    scheduled_at: str
) -> Dict[str, Any]:
    """Update the scheduled publish time for a specific post and reschedule its
    APScheduler publish job so it actually fires at the new time."""
    supabase = get_supabase_admin_client()
    response = supabase.table("posts")\
        .update({"scheduled_at": scheduled_at})\
        .eq("id", post_id)\
        .eq("instagram_account_id", instagram_account_id)\
        .execute()
    if not response.data:
        return {}

    updated = response.data[0]
    if updated.get("media_url"):
        from services.scheduler.post_scheduler import PostScheduler
        try:
            PostScheduler().reschedule_post(post_id, datetime.fromisoformat(scheduled_at))
        except Exception as e:
            logger.warning(f"No se pudo reprogramar el job de APScheduler para post {post_id}: {e}")
    return updated


@mcp.tool()
def supabase_update_post_image(
    instagram_account_id: int,
    post_id: int,
    drive_file_id: str
) -> Dict[str, Any]:
    """Update the drive file ID/image for a specific post."""
    supabase = get_supabase_admin_client()
    response = supabase.table("posts")\
        .update({"drive_file_id": drive_file_id})\
        .eq("id", post_id)\
        .eq("instagram_account_id", instagram_account_id)\
        .execute()
    if response.data and len(response.data) > 0:
        return response.data[0]
    return {}


@mcp.tool()
def supabase_create_monthly_campaign(
    instagram_account_id: int,
    month_date: str,
    strategy_mode: str,
    title: str,
    description: Optional[str] = None,
    milestones: Optional[List[Dict[str, Any]]] = None,
    weekly_focus: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Draft a monthly campaign for an account, idempotently: no-ops if a pending
    or approved campaign already exists for that month (returns it as-is),
    replaces a rejected one, and inserts fresh if none exists. Returns
    {"created": bool, "campaign": {...}}."""
    supabase = get_supabase_admin_client()
    existing_res = supabase.table("monthly_campaigns")\
        .select("*")\
        .eq("account_id", instagram_account_id)\
        .eq("month_date", month_date)\
        .execute()
    existing = existing_res.data[0] if existing_res.data else None

    if existing and existing.get("status") in ("pending_approval", "approved"):
        return {"created": False, "campaign": existing}

    payload = {
        "account_id": instagram_account_id,
        "month_date": month_date,
        "strategy_mode": strategy_mode,
        "title": title,
        "description": description,
        "milestones": milestones or [],
        "weekly_focus": weekly_focus or {},
        "status": "pending_approval",
        "generated_by": "hermes",
    }

    if existing and existing.get("status") == "rejected":
        response = supabase.table("monthly_campaigns")\
            .upsert(payload, on_conflict="account_id,month_date")\
            .execute()
    else:
        response = supabase.table("monthly_campaigns").insert(payload).execute()

    campaign = response.data[0] if response.data else {}
    return {"created": True, "campaign": campaign}


@mcp.tool()
def supabase_update_campaign_focus(campaign_id: str, week_number: int, focus_text: str) -> Dict[str, Any]:
    """Update the weekly_focus text for a single week (1-4) of a monthly campaign,
    leaving the other weeks untouched."""
    supabase = get_supabase_admin_client()
    existing_res = supabase.table("monthly_campaigns").select("weekly_focus").eq("id", campaign_id).execute()
    if not existing_res.data:
        return {}
    weekly_focus = dict(existing_res.data[0].get("weekly_focus") or {})
    weekly_focus[str(week_number)] = focus_text
    response = supabase.table("monthly_campaigns")\
        .update({"weekly_focus": weekly_focus})\
        .eq("id", campaign_id)\
        .execute()
    return response.data[0] if response.data else {}


@mcp.tool()
def supabase_update_campaign_milestones(campaign_id: str, milestones: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Replace the full milestones list of a monthly campaign."""
    supabase = get_supabase_admin_client()
    response = supabase.table("monthly_campaigns")\
        .update({"milestones": milestones})\
        .eq("id", campaign_id)\
        .execute()
    return response.data[0] if response.data else {}


@mcp.tool()
def supabase_update_campaign_details(
    campaign_id: str,
    title: Optional[str] = None,
    description: Optional[str] = None
) -> Dict[str, Any]:
    """Update the title and/or description of a monthly campaign."""
    supabase = get_supabase_admin_client()
    updates: Dict[str, Any] = {}
    if title is not None:
        updates["title"] = title
    if description is not None:
        updates["description"] = description
    if not updates:
        return {}
    response = supabase.table("monthly_campaigns")\
        .update(updates)\
        .eq("id", campaign_id)\
        .execute()
    return response.data[0] if response.data else {}

