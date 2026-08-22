from typing import Dict, List
from mcp.server.fastmcp import FastMCP
from database.supabase_client import get_supabase_admin_client
from services.analytics.analytics_service import AnalyticsService

mcp = FastMCP("Analytics Server")

@mcp.tool()
def analytics_get_empirical_scheduling_data(account_id: int, days: int = 90) -> Dict:
    """Get a compact summary of optimal posting times based on this account's real
    posting history — has_data, top_times, best_times_by_weekday and summary_text.
    Call only when the account profile has no custom best_times configured."""
    supabase = get_supabase_admin_client()
    return AnalyticsService(db_client=supabase).get_empirical_scheduling_data(account_id, days)

@mcp.tool()
def analytics_get_visual_performance_data(account_id: int, days: int = 180) -> List[Dict]:
    """Get raw per-post rows joining visual content tags (objects/theme/mood from
    Gemini Vision analysis) with real Instagram performance metrics (likes, reach,
    engagement). Returns unaggregated data — no correlation is computed here."""
    supabase = get_supabase_admin_client()
    return AnalyticsService(db_client=supabase).get_visual_performance_data(account_id, days)
