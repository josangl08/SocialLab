import asyncio
import logging
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
from database.supabase_client import get_supabase_admin_client
from services.analytics.analytics_service import AnalyticsService
from services.content_quality import audit_profile
from services.hermes.skills import run_niche_research_for_account
from services.reference_accounts import reference_summary_for_prompt

logger = logging.getLogger(__name__)


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


def _monthly_outliers_summary(account_id: int) -> str:
    """Top 5 del Swipe File del último mes con Outlier Multiple (AD-6)."""
    swipe = AnalyticsService(db_client=get_supabase_admin_client()).get_swipe_file(account_id, days=30)
    top = [it for it in swipe.get("items", []) if it.get("outlier_multiple") is not None][:5]
    return "\n".join(
        f"- \"{it['hook_text']}\" ({it.get('formula_name') or 'sin fórmula'}, {it['outlier_multiple']}x la mediana)"
        for it in top
    )


def _monthly_audit_summary(account_id: int) -> str:
    """Puntos de la auditoría de perfil que no se cumplen, con su peso (AD-6). Usa
    los datos guardados de la cuenta, sin llamar a Instagram."""
    res = get_supabase_admin_client().table("instagram_accounts").select("*").eq("id", account_id).execute()
    if not res.data:
        return ""
    audit = audit_profile(res.data[0])
    return "\n".join(
        f"- {it['label']} (peso {it['weight']}): {it['tip']}" for it in audit["items"] if not it["passed"]
    )


def _gather_monthly_context(account_id: int) -> dict:
    """Cada fuente es opcional: si falla se registra y se omite, nunca aborta la sesión."""
    sources = {
        "niche_brief": lambda: run_niche_research_for_account(account_id).get("brief"),
        "outliers_summary": lambda: _monthly_outliers_summary(account_id),
        "audit_summary": lambda: _monthly_audit_summary(account_id),
        "references_summary": lambda: reference_summary_for_prompt(account_id),
    }
    context = {}
    for key, fetch in sources.items():
        try:
            context[key] = fetch() or None
        except Exception as e:
            logger.warning(f"Contexto mensual sin {key} para cuenta {account_id}: {e}")
            context[key] = None
    return context


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

    # En un hilo: las fuentes hacen I/O síncrono (Graph API, Gemini, BD) y no deben bloquear el event loop
    monthly_context = await asyncio.to_thread(_gather_monthly_context, account_id)
    system_prompt = get_monthly_strategy_prompt(account_id, target_month, **monthly_context)
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
