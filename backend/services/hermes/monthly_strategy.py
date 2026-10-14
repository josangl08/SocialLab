import os
from datetime import date
from typing import Optional
from pydantic import BaseModel

from services.hermes.tool_bridge import ToolBridge
from services.hermes.orchestrator import _dispatch_turn, _FallbackGenerativeModel
from services.hermes.prompts import get_monthly_strategy_prompt
from mcp.supabase_server import mcp as supabase_mcp
from services.account_timezone import get_account_timezone
from utils.timezones import local_today


class MonthlyStrategyResult(BaseModel):
    account_id: int
    created: bool = False
    campaign_id: Optional[str] = None
    error: Optional[str] = None


def next_month_date(today: Optional[date] = None) -> str:
    """First day (YYYY-MM-01) of the month after today."""
    today = today or date.today()
    if today.month == 12:
        return date(today.year + 1, 1, 1).isoformat()
    return date(today.year, today.month + 1, 1).isoformat()


_MONTHLY_TOOLS = [
    "supabase_get_account",
    "supabase_get_campaign",
    "supabase_create_monthly_campaign",
]


async def run_monthly_strategy_session(account_id: int, target_month: Optional[str] = None) -> MonthlyStrategyResult:
    """Run a bounded Hermes session that drafts one monthly campaign for account_id,
    per design.md §Data Flow. Idempotency (no duplicate/overwrite of a pending or
    approved campaign) lives in supabase_create_monthly_campaign itself, not here —
    this session just calls the tool and reports what happened. target_month
    (YYYY-MM-01) defaults to next_month_date() — the cron's on-demand-trigger
    counterpart passes an explicit month so the user can generate for whichever
    month the drawer has open."""
    max_turns = int(os.environ.get("HERMES_MONTHLY_MAX_TURNS", "5"))
    # Mes siguiente según la fecha local de la cuenta (AD-15)
    target_month = target_month or next_month_date(local_today(get_account_timezone(account_id)))

    bridge = ToolBridge([supabase_mcp], allowed_tools=_MONTHLY_TOOLS)
    declarations = await bridge.discover_tools()

    system_prompt = get_monthly_strategy_prompt(account_id, target_month)
    model = _FallbackGenerativeModel(system_prompt, declarations)

    history = [{"role": "user", "parts": [{"text": "Redacta el borrador de campaña del próximo mes."}]}]

    turns = 0
    created = False
    campaign_id: Optional[str] = None

    while turns < max_turns:
        try:
            response = model.generate_content(history)
            turns += 1
        except Exception as e:
            return MonthlyStrategyResult(account_id=account_id, error=f"gemini_error: {str(e)}")

        function_calls, model_parts, tool_responses, dispatched = await _dispatch_turn(
            response, bridge, account_id
        )
        history.append({"role": "model", "parts": model_parts})

        if not function_calls:
            break

        for tool_name, _tool_args, result in dispatched:
            if tool_name == "supabase_create_monthly_campaign" and isinstance(result, dict):
                created = bool(result.get("created"))
                campaign_id = (result.get("campaign") or {}).get("id")

        # Gemini expects role="user" for function-response turns, not "tool" —
        # see orchestrator.py's run_session/run_edit_session for the same fix.
        history.append({"role": "user", "parts": tool_responses})
    else:
        return MonthlyStrategyResult(
            account_id=account_id,
            created=created,
            campaign_id=campaign_id,
            error="hermes_monthly_max_turns_exceeded"
        )

    return MonthlyStrategyResult(account_id=account_id, created=created, campaign_id=campaign_id)
