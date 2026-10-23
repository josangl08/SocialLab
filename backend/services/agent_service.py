import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from database.supabase_client import get_supabase_admin_client
from models.schemas import AgentLog
from config import FRONTEND_URL
from services.hermes.orchestrator import run_session

logger = logging.getLogger(__name__)


def run_agent(account_id: int) -> AgentLog:
    start = datetime.now(timezone.utc)
    supabase = get_supabase_admin_client()
    images_scanned = 0
    images_analyzed = 0
    posts_drafted = 0
    error_msg = None

    try:
        acc_res = supabase.table('instagram_accounts').select('*').eq('id', account_id).execute()
        if not acc_res.data:
            raise ValueError(f"Account {account_id} not found")
        account = acc_res.data[0]
        logger.info(f"[Agent] Started — account_id={account_id}, username={account.get('username', 'unknown')}")

        result = asyncio.run(run_session(account_id))
        images_scanned = result.images_scanned
        images_analyzed = result.images_analyzed
        posts_drafted = result.posts_drafted
        error_msg = result.error
        logger.info(
            f"[Agent] Hermes session complete — account_id={account_id}, "
            f"images_scanned={images_scanned}, images_analyzed={images_analyzed}, "
            f"posts_drafted={posts_drafted}, proposal_id={result.proposal_id}, error={error_msg}"
        )

        if result.proposal_id is not None:
            telegram_error = _dispatch_telegram_proposal(supabase, account_id, account, result.proposal_id)
            if telegram_error and not error_msg:
                error_msg = telegram_error

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Agent error for account {account_id}: {e}")

    duration = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
    logger.info(f"[Agent] Complete — account_id={account_id}, images_scanned={images_scanned}, posts_drafted={posts_drafted}, duration_ms={duration}")
    _write_agent_log(supabase, account_id, images_scanned, images_analyzed, posts_drafted, error_msg, duration)

    return AgentLog(
        account_id=str(account_id),
        images_scanned=images_scanned,
        images_analyzed=images_analyzed,
        posts_drafted=posts_drafted,
        error=error_msg,
        duration_ms=duration
    )


def _dispatch_telegram_proposal(supabase, account_id: int, account: dict, proposal_id: str) -> Optional[str]:
    """Sends the just-created proposal's approval card via Telegram. Returns None on
    success (including the routine "no Telegram linked" case), or an error message
    if something genuinely went wrong — the caller surfaces that into agent_logs.error
    (polled by the frontend) instead of it being silently swallowed."""
    chat_id = account.get('telegram_chat_id')
    if not chat_id:
        logger.info(f"No telegram_chat_id for account {account_id} — skipping Telegram dispatch")
        return None

    proposal_res = supabase.table('content_proposals').select('*').eq('id', proposal_id).execute()
    if not proposal_res.data:
        logger.error(f"[Agent] proposal {proposal_id} not found — cannot dispatch Telegram card")
        return f"telegram_dispatch_failed: proposal {proposal_id} not found"
    proposal = proposal_res.data[0]

    # Enlace a la pestaña Publicación si quedan sugerencias pendientes (AD-7)
    strategy_url = None
    pending_res = supabase.table('agent_decisions').select('id')\
        .eq('account_id', account_id).eq('status', 'suggested').limit(1).execute()
    if pending_res.data:
        strategy_url = f"{FRONTEND_URL}/strategy?account={account_id}&tab=publicacion"

    try:
        from services.telegram_service import TelegramService
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(
                TelegramService().send_proposal_card(
                    str(chat_id), proposal['id'], proposal['slots'], str(account.get('user_id', '')),
                    strategy_url=strategy_url,
                )
            )
        finally:
            loop.close()
        logger.info(f"[Agent] Telegram dispatch succeeded — chat_id={chat_id}")
        return None
    except Exception as te:
        logger.error(f"Telegram dispatch failed for account {account_id}: {te}")
        return f"telegram_dispatch_failed: {te}"


def _write_agent_log(
    supabase,
    account_id: int,
    images_scanned: int,
    images_analyzed: int,
    posts_drafted: int,
    error: Optional[str],
    duration_ms: int
) -> None:
    try:
        supabase.table('agent_logs').insert({
            'account_id': account_id,
            'images_scanned': images_scanned,
            'images_analyzed': images_analyzed,
            'posts_drafted': posts_drafted,
            'error': error,
            'duration_ms': duration_ms
        }).execute()
    except Exception as e:
        logger.error(f"Failed to write agent log: {e}")
