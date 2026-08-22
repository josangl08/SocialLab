from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Literal, Optional
from database.supabase_client import get_supabase_admin_client
from models.schemas import User, AgentConfig, ContentProposal, MonthlyCampaign
from auth.dependencies import get_current_user, get_user_supabase_client
from supabase import Client
from datetime import datetime, timezone, timedelta
import asyncio
import uuid
import json
import logging
from services.gemini_service import generate_gemini_content, clean_and_parse_json, regenerate_slot_caption
from services.analytics.analytics_service import AnalyticsService
from services.hermes.orchestrator import run_edit_session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/agent", tags=["Agent"])
admin_supabase = get_supabase_admin_client()

class TriggerRequest(BaseModel):
    account_id: int

@router.post("/trigger")
def trigger_agent(
    request: TriggerRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """
    Manually triggers the agent pipeline for an account (dev/debug use).
    """
    try:
        # Verify account exists and belongs to current_user
        acc_res = admin_supabase.table('instagram_accounts').select('user_id, drive_folder_id').eq('id', request.account_id).execute()
        if not acc_res.data:
            raise HTTPException(status_code=404, detail="Cuenta de Instagram no encontrada")
        if str(acc_res.data[0]['user_id']) != str(current_user.id):
            raise HTTPException(status_code=403, detail="No tienes acceso a esta cuenta")

        if not acc_res.data[0].get('drive_folder_id'):
            raise HTTPException(status_code=400, detail="Esta cuenta no tiene carpeta de Drive configurada")

        # Pre-check Drive credentials before launching background job
        from services.google_drive_connector import get_drive_connector
        try:
            get_drive_connector(str(current_user.id))
        except RuntimeError:
            raise HTTPException(
                status_code=503,
                detail="Google Drive no está conectado. Conéctalo desde Configuración > Cuentas."
            )

        run_id = str(uuid.uuid4())

        from services.agent_service import run_agent
        background_tasks.add_task(run_agent, request.account_id)

        return {"run_id": run_id, "status": "started"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering agent: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al iniciar el agente: {str(e)}")


class CampaignTriggerRequest(BaseModel):
    account_id: int
    month_date: Optional[str] = None  # defaults to next calendar month, like the daily cron


@router.post("/campaign/trigger")
def trigger_monthly_campaign(
    request: CampaignTriggerRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """
    Manually asks Hermes to draft a monthly campaign for the given account/month
    on demand (the drawer's "Generar con Hermes" button), instead of waiting for
    the daily cron. Idempotency (no duplicate/overwrite of a pending or approved
    campaign) is already handled inside supabase_create_monthly_campaign.
    """
    acc_res = admin_supabase.table('instagram_accounts').select('user_id').eq('id', request.account_id).execute()
    if not acc_res.data:
        raise HTTPException(status_code=404, detail="Cuenta de Instagram no encontrada")
    if str(acc_res.data[0]['user_id']) != str(current_user.id):
        raise HTTPException(status_code=403, detail="No tienes acceso a esta cuenta")

    background_tasks.add_task(_run_monthly_campaign_trigger, request.account_id, request.month_date)

    return {"status": "started"}


async def _run_monthly_campaign_trigger(account_id: int, month_date: Optional[str]) -> None:
    """Background-task wrapper for the on-demand monthly campaign trigger. Without
    this, an exception inside run_monthly_strategy_session fails silently — no
    HTTP response to catch it (already sent), no agent_logs-style record anywhere
    the frontend could poll. At minimum, make failures visible in server logs."""
    try:
        from services.hermes.monthly_strategy import run_monthly_strategy_session
        result = await run_monthly_strategy_session(account_id, month_date)
        logger.info(
            f"[MonthlyCampaign] On-demand trigger complete — account_id={account_id}, "
            f"created={result.created}, campaign_id={result.campaign_id}, error={result.error}"
        )
    except Exception as e:
        logger.error(f"[MonthlyCampaign] On-demand trigger failed for account {account_id}: {e}")

@router.get("/logs/latest")
def get_latest_agent_log(
    account_id: int,
    current_user: User = Depends(get_current_user)
):
    """Returns the most recent agent_logs row for account_id, or null if the
    agent has never run for it. Lets the planner poll for the outcome (including
    the error message) of a triggered run instead of guessing from side effects."""
    acc_res = admin_supabase.table('instagram_accounts').select('user_id').eq('id', account_id).execute()
    if not acc_res.data:
        raise HTTPException(status_code=404, detail="Cuenta de Instagram no encontrada")
    if str(acc_res.data[0]['user_id']) != str(current_user.id):
        raise HTTPException(status_code=403, detail="No tienes acceso a esta cuenta")

    log_res = admin_supabase.table('agent_logs')\
        .select('*')\
        .eq('account_id', account_id)\
        .order('run_at', desc=True)\
        .limit(1)\
        .execute()
    return log_res.data[0] if log_res.data else None


@router.get("/proposals", response_model=list[ContentProposal])
def list_proposals(
    account_id: int,
    current_user: User = Depends(get_current_user),
    supabase: Client = Depends(get_user_supabase_client)
):
    """
    Lists all content proposals for the authenticated user's Instagram account.
    """
    try:
        # Verify account exists and belongs to current_user
        acc_res = admin_supabase.table('instagram_accounts').select('user_id').eq('id', account_id).execute()
        if not acc_res.data:
            raise HTTPException(status_code=404, detail="Cuenta de Instagram no encontrada")
        if str(acc_res.data[0]['user_id']) != str(current_user.id):
            raise HTTPException(status_code=403, detail="No tienes acceso a esta cuenta")

        proposals_res = supabase.table('content_proposals')\
            .select('*')\
            .eq('account_id', account_id)\
            .order('created_at', desc=True)\
            .execute()

        proposals = []
        for row in proposals_res.data:
            try:
                proposals.append(ContentProposal(
                    id=str(row['id']),
                    account_id=str(row['account_id']),
                    week_start=str(row['week_start']),
                    slots=row['slots'],
                    status=row['status']
                ))
            except Exception as e:
                # A malformed legacy row (e.g. incomplete slots from before the
                # CalendarSlot schema was enforced) shouldn't hide every other
                # proposal behind a 500 — skip it and keep serving the rest.
                logger.warning(f"Skipping malformed proposal {row.get('id')}: {e}")
        return proposals
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing proposals: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al obtener las propuestas: {str(e)}")

@router.post("/proposals/{proposal_id}/approve")
def approve_proposal(
    proposal_id: str,
    current_user: User = Depends(get_current_user),
    supabase: Client = Depends(get_user_supabase_client)
):
    proposal_res = supabase.table('content_proposals').select('*').eq('id', proposal_id).execute()
    if not proposal_res.data:
        raise HTTPException(status_code=404, detail="Propuesta no encontrada")

    proposal = proposal_res.data[0]
    account_id = proposal['account_id']
    acc_res = admin_supabase.table('instagram_accounts').select('user_id').eq('id', account_id).execute()
    if not acc_res.data or str(acc_res.data[0]['user_id']) != str(current_user.id):
        raise HTTPException(status_code=403, detail="No tienes acceso a esta propuesta")

    admin_supabase.table('content_proposals').update({
        'status': 'approved',
        'resolved_at': datetime.now(timezone.utc).isoformat()
    }).eq('id', proposal_id).execute()

    slots = proposal.get('slots', [])
    post_ids = [s['post_id'] for s in slots if s.get('post_id')]
    scheduled_count = 0
    if post_ids:
        from services.scheduler.post_scheduler import PostScheduler
        scheduler = PostScheduler()
        posts_res = admin_supabase.table('posts').select('id, scheduled_at, media_url').in_('id', post_ids).execute()
        for post in (posts_res.data or []):
            admin_supabase.table('posts').update({'status': 'scheduled'}).eq('id', post['id']).execute()
            if post.get('media_url'):
                try:
                    scheduled_at_raw = post.get('scheduled_at')
                    scheduled_time = datetime.now(timezone.utc)
                    if scheduled_at_raw:
                        parsed = datetime.fromisoformat(str(scheduled_at_raw).replace('Z', '+00:00'))
                        if parsed.tzinfo is None:
                            parsed = parsed.replace(tzinfo=timezone.utc)
                        if parsed > datetime.now(timezone.utc):
                            scheduled_time = parsed
                    scheduler.schedule_post(post['id'], scheduled_time)
                    scheduled_count += 1
                except Exception as e:
                    logger.warning(f"Could not schedule post {post['id']}: {e}")

    return {"updated": True, "scheduled": scheduled_count}


@router.post("/proposals/{proposal_id}/reject")
def reject_proposal(
    proposal_id: str,
    current_user: User = Depends(get_current_user),
    supabase: Client = Depends(get_user_supabase_client)
):
    proposal_res = supabase.table('content_proposals').select('*').eq('id', proposal_id).execute()
    if not proposal_res.data:
        raise HTTPException(status_code=404, detail="Propuesta no encontrada")

    proposal = proposal_res.data[0]
    account_id = proposal['account_id']
    acc_res = admin_supabase.table('instagram_accounts').select('user_id').eq('id', account_id).execute()
    if not acc_res.data or str(acc_res.data[0]['user_id']) != str(current_user.id):
        raise HTTPException(status_code=403, detail="No tienes acceso a esta propuesta")

    slots = proposal.get('slots', [])
    post_ids = [s['post_id'] for s in slots if s.get('post_id')]
    for pid in post_ids:
        admin_supabase.table('posts').delete().eq('id', pid).eq('status', 'draft').execute()

    admin_supabase.table('content_proposals').update({
        'status': 'rejected',
        'resolved_at': datetime.now(timezone.utc).isoformat()
    }).eq('id', proposal_id).execute()
    return {"updated": True}


STRATEGY_FIELDS = (
    'id, account_type, sector, purpose, target_audience, style_guide, '
    'default_tone, default_language, posting_frequency, best_times, '
    'content_pillars, hashtag_strategy, caption_voice, reference_accounts, '
    'posts_per_week, scheduling_mode, preferred_days, content_type_mix, last_agent_sync'
)

@router.get("/config/{account_id}")
def get_agent_config(
    account_id: int,
    current_user: User = Depends(get_current_user)
):
    try:
        acc_res = admin_supabase.table('instagram_accounts').select(STRATEGY_FIELDS).eq('id', account_id).execute()
        if not acc_res.data:
            raise HTTPException(status_code=404, detail="Cuenta no encontrada")
        if str(acc_res.table if hasattr(acc_res, 'table') else ''):
            pass
        row = acc_res.data[0]
        return {
            'account_type': row.get('account_type', 'personal'),
            'sector': row.get('sector') or '',
            'purpose': row.get('purpose') or '',
            'target_audience': row.get('target_audience') or '',
            'style_guide': row.get('style_guide') or '',
            'default_tone': row.get('default_tone', 'energetic'),
            'default_language': row.get('default_language', 'es'),
            'posting_frequency': row.get('posting_frequency', 'few_times_week'),
            'best_times': row.get('best_times') or ['09:00', '18:00'],
            'content_pillars': row.get('content_pillars') or [],
            'hashtag_strategy': row.get('hashtag_strategy', 'moderate'),
            'caption_voice': row.get('caption_voice'),
            'reference_accounts': row.get('reference_accounts') or [],
            'posts_per_week': row.get('posts_per_week', 3),
            'scheduling_mode': row.get('scheduling_mode', 'flexible'),
            'preferred_days': row.get('preferred_days') or [],
            'content_type_mix': row.get('content_type_mix') or {'post': 2, 'reel': 1, 'carousel': 1, 'story': 0},
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/config/{account_id}")
def update_agent_config(
    account_id: int,
    config: AgentConfig,
    current_user: User = Depends(get_current_user)
):
    """
    Updates the strategy configuration for the specified Instagram account.
    """
    try:
        # Verify account exists and belongs to current_user
        acc_res = admin_supabase.table('instagram_accounts').select('user_id').eq('id', account_id).execute()
        if not acc_res.data:
            raise HTTPException(status_code=404, detail="Cuenta de Instagram no encontrada")
        if str(acc_res.data[0]['user_id']) != str(current_user.id):
            raise HTTPException(status_code=403, detail="No tienes acceso a esta cuenta")

        admin_supabase.table('instagram_accounts').update({
            'account_type': config.account_type,
            'sector': config.sector,
            'purpose': config.purpose,
            'target_audience': config.target_audience,
            'style_guide': config.style_guide,
            'default_tone': config.default_tone,
            'default_language': config.default_language,
            'posting_frequency': config.posting_frequency,
            'best_times': config.best_times,
            'content_pillars': config.content_pillars,
            'hashtag_strategy': config.hashtag_strategy,
            'caption_voice': config.caption_voice,
            'reference_accounts': config.reference_accounts,
            'posts_per_week': config.posts_per_week,
            'scheduling_mode': config.scheduling_mode,
            'preferred_days': config.preferred_days,
            'content_type_mix': config.content_type_mix,
        }).eq('id', account_id).execute()

        return {"updated": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating agent config: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al actualizar la configuración: {str(e)}")


class SuggestTimesRequest(BaseModel):
    sector: str = ""
    target_audience: str = ""
    default_tone: str = "energetic"
    account_type: str = "personal"
    account_id: Optional[int] = None


@router.post("/suggest-times")
async def suggest_times(
    request: SuggestTimesRequest,
    current_user: User = Depends(get_current_user)
):
    if request.account_id is not None:
        acc_res = admin_supabase.table('instagram_accounts').select('user_id').eq('id', request.account_id).execute()
        if not acc_res.data:
            raise HTTPException(status_code=404, detail="Cuenta de Instagram no encontrada")
        if str(acc_res.data[0]['user_id']) != str(current_user.id):
            raise HTTPException(status_code=403, detail="No tienes acceso a esta cuenta")

        analytics_data = AnalyticsService(db_client=admin_supabase).get_empirical_scheduling_data(request.account_id)
        if analytics_data.get('has_data'):
            return {"best_times": analytics_data['top_times'][:3], "source": "historical"}

    if request.account_type == "professional":
        timing_context = (
            "Es una cuenta PROFESIONAL/BUSINESS. Considera las ventanas en que la audiencia "
            "toma decisiones según el sector indicado (B2B: Mar-Jue mañana/tarde; "
            "B2C lifestyle/restauración: incluye fines de semana). "
            "El timing depende del sector y la audiencia, no del tipo de cuenta."
        )
    else:
        timing_context = (
            "Es una cuenta PERSONAL/CREATOR. Considera cuándo la audiencia hace scroll "
            "en su tiempo libre según el sector indicado (fitness: mañanas; viajes/lifestyle: "
            "tardes-noche y fines de semana; deporte: post-partido o post-entrenamiento)."
        )

    prompt = f"""Eres un experto en estrategia de Instagram con acceso a datos de 9.6M publicaciones analizadas en 2026.

Sector: "{request.sector or 'general'}" · Audiencia: "{request.target_audience or 'general'}" · Tono: "{request.default_tone}"
{timing_context}

¿Cuáles son los 2-3 mejores horarios de publicación en España para maximizar el engagement?
Ten en cuenta que los mejores días globales son miércoles y jueves, pero ajústalos al sector.

Devuelve SOLO este JSON: {{"best_times": ["HH:MM", "HH:MM", "HH:MM"]}}
Horarios en formato 24h, de mayor a menor impacto. Solo el JSON."""

    try:
        text = await generate_gemini_content(prompt)
        result = await clean_and_parse_json(text)
        result["source"] = "heuristic"
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class GenerateStrategyRequest(BaseModel):
    dedica: list[str] = []
    contenido: list[str] = []
    objetivo: list[str] = []
    referentes: list[str] = []


@router.post("/generate-strategy")
async def generate_strategy(
    request: GenerateStrategyRequest,
    current_user: User = Depends(get_current_user)
):
    referentes_text = ", ".join(f"@{r}" for r in request.referentes) if request.referentes else "Ninguna"

    prompt = f"""Eres un experto en estrategia de contenido para Instagram, con conocimiento de los datos de rendimiento de 2026.

CONTEXTO ALGORÍTMICO 2026:
- Cuentas PERSONALES/CREATOR: acceso a audio trending completo → Reels tienen mayor distribución orgánica. Prioriza Reels (60%+ del mix).
- Cuentas PROFESIONALES/BUSINESS: acceso solo a audio licenciado → 7-12% menos reach orgánico en Reels. Compensar con Carousels (40%+ del mix, +109% engagement/persona).
- Hashtags: cap de 5 máx desde dic 2025. Usa 3-5 muy relevantes.
- Captions importan más que hashtags para discoverability desde 2026.
- Instagram indexa contenido en Google desde 2025 → keywords SEO en captions para cuentas profesionales.
- Algorithm premia: watch time en Reels, saves, sends (compartir por DM).
- TIMING: Los horarios dependen del SECTOR y la AUDIENCIA, no del tipo de cuenta.

REGLAS SEGÚN TIPO (determina el tipo basándote en las respuestas):
- PERSONAL: filosofía espontánea/reactiva, comunidad+engagement como KPIs, voz en 1ª persona, scheduling flexible, CTAs de engagement ("¿Qué opinas?", "Guárdalo").
- PROFESIONAL: cadencia planificada, funnel awareness→consideration→conversion como KPI, voz de marca consistente, scheduling fijo, CTAs de conversión ("Contáctanos", "Link en bio").

Un usuario ha respondido estas preguntas:
1. ¿A qué se dedica su cuenta? {", ".join(request.dedica) or "No especificado"}
2. ¿Qué tipo de contenido va a publicar? {", ".join(request.contenido) or "No especificado"}
3. ¿Qué quiere conseguir con Instagram? {", ".join(request.objetivo) or "No especificado"}
4. Cuentas referentes: {referentes_text}

Genera la estrategia completa. Devuelve SOLO este JSON:
{{
  "account_type": "personal" | "professional",
  "sector": "sector en 2-4 palabras",
  "purpose": "objetivo principal en 1 frase concisa",
  "target_audience": "descripción de la audiencia ideal en 1-2 frases",
  "style_guide": "guía de tono y voz con instrucciones concretas en 2-3 frases",
  "default_tone": "energetic" | "professional" | "casual" | "inspirational",
  "default_language": "es" | "en",
  "posting_frequency": "daily" | "few_times_week" | "once_or_twice_week" | "weekly",
  "posts_per_week": <número entre 3 y 7>,
  "best_times": ["HH:MM", "HH:MM"],
  "content_pillars": ["pilar1", "pilar2", "pilar3", "pilar4"],
  "hashtag_strategy": "minimal",
  "scheduling_mode": "flexible" | "fixed",
  "content_type_mix": {{"post": <n>, "reel": <n>, "carousel": <n>, "story": <n>}}
}}

Solo el JSON, sin texto adicional."""

    try:
        text = await generate_gemini_content(prompt)
        return await clean_and_parse_json(text)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="La IA devolvió una respuesta inválida")
    except Exception as e:
        logger.error(f"Error generating strategy: {e}")
        raise HTTPException(status_code=500, detail=f"Error al generar la estrategia: {str(e)}")


# ── Slot-level endpoints ─────────────────────────────────────────────────────

def _get_proposal_and_slot(proposal_id: str, slot_index: int, user_id: str, supabase_client: Client):
    """Shared helper: validates ownership and returns (proposal_row, slot_dict)."""
    proposal_res = supabase_client.table('content_proposals').select('*').eq('id', proposal_id).execute()
    if not proposal_res.data:
        raise HTTPException(status_code=404, detail="Propuesta no encontrada")
    proposal = proposal_res.data[0]
    acc_res = admin_supabase.table('instagram_accounts').select('user_id').eq('id', proposal['account_id']).execute()
    if not acc_res.data or str(acc_res.data[0]['user_id']) != str(user_id):
        raise HTTPException(status_code=403, detail="No tienes acceso a esta propuesta")
    slots = proposal.get('slots', [])
    if slot_index < 0 or slot_index >= len(slots):
        raise HTTPException(status_code=404, detail="Slot no encontrado")
    return proposal, slots


@router.post("/proposals/{proposal_id}/slots/{slot_index}/regenerate")
async def regenerate_slot(
    proposal_id: str,
    slot_index: int,
    current_user: User = Depends(get_current_user),
    supabase: Client = Depends(get_user_supabase_client)
):
    proposal, slots = _get_proposal_and_slot(proposal_id, slot_index, str(current_user.id), supabase)
    slot = slots[slot_index]
    post_id = slot.get('post_id')
    if not post_id:
        raise HTTPException(status_code=400, detail="Este slot no tiene un post asociado")

    image_id = slot.get('image_id')
    description_context = ""
    if image_id:
        va_res = supabase.table('visual_analyses').select('gemini_description').eq('drive_file_id', image_id).execute()
        if va_res.data:
            description_context = str(va_res.data[0].get('gemini_description', ''))

    theme = slot.get('theme', '')
    acc_res = admin_supabase.table('instagram_accounts').select('default_language').eq('id', proposal['account_id']).execute()
    language = acc_res.data[0].get('default_language', 'es') if acc_res.data else 'es'

    try:
        new_caption = await regenerate_slot_caption(
            theme=theme,
            visual_context=description_context,
            language=language
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al regenerar caption: {str(e)}")

    admin_supabase.table('posts').update({'content': new_caption}).eq('id', post_id).execute()
    slots[slot_index]['caption'] = new_caption
    admin_supabase.table('content_proposals').update({'slots': slots}).eq('id', proposal_id).execute()

    return {"caption": new_caption}


@router.post("/proposals/{proposal_id}/slots/{slot_index}/skip")
def skip_slot(
    proposal_id: str,
    slot_index: int,
    current_user: User = Depends(get_current_user),
    supabase: Client = Depends(get_user_supabase_client)
):
    proposal, slots = _get_proposal_and_slot(proposal_id, slot_index, str(current_user.id), supabase)
    slot = slots[slot_index]
    post_id = slot.get('post_id')

    if post_id:
        admin_supabase.table('posts').delete().eq('id', post_id).eq('status', 'draft').execute()

    slots[slot_index]['post_id'] = None
    admin_supabase.table('content_proposals').update({'slots': slots}).eq('id', proposal_id).execute()
    return {"skipped": True}


class SlotTypeRequest(BaseModel):
    post_type: Literal["post", "reel", "carousel", "story"]


@router.post("/proposals/{proposal_id}/slots/{slot_index}/type")
def update_slot_type(
    proposal_id: str,
    slot_index: int,
    request: SlotTypeRequest,
    current_user: User = Depends(get_current_user),
    supabase: Client = Depends(get_user_supabase_client)
):
    proposal, slots = _get_proposal_and_slot(proposal_id, slot_index, str(current_user.id), supabase)
    slot = slots[slot_index]
    post_id = slot.get('post_id')

    if post_id:
        admin_supabase.table('posts').update({'post_type': request.post_type}).eq('id', post_id).execute()

    slots[slot_index]['post_type'] = request.post_type
    admin_supabase.table('content_proposals').update({'slots': slots}).eq('id', proposal_id).execute()
    return {"updated": True}


_WEEKDAY_OFFSET: dict = {
    'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 'Thursday': 3,
    'Friday': 4, 'Saturday': 5, 'Sunday': 6,
}


class SlotReorderRequest(BaseModel):
    from_day: str
    to_day: str


@router.patch("/proposals/{proposal_id}/slots/reorder")
def reorder_proposal_slot(
    proposal_id: str,
    request: SlotReorderRequest,
    current_user: User = Depends(get_current_user),
    supabase: Client = Depends(get_user_supabase_client)
):
    """Move a slot from one day to another (or swap two slots)."""
    proposal_res = supabase.table('content_proposals').select('*').eq('id', proposal_id).execute()
    if not proposal_res.data:
        raise HTTPException(status_code=404, detail="Proposal not found")
    proposal = proposal_res.data[0]
    acc_res = admin_supabase.table('instagram_accounts').select('user_id').eq('id', proposal['account_id']).execute()
    if not acc_res.data or str(acc_res.data[0]['user_id']) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Access denied")

    slots = list(proposal.get('slots', []))
    week_start = str(proposal['week_start'])  # e.g. "2026-06-29"

    from_idx = next((i for i, s in enumerate(slots) if s.get('day') == request.from_day), None)
    to_idx = next((i for i, s in enumerate(slots) if s.get('day') == request.to_day), None)

    if from_idx is None:
        raise HTTPException(status_code=404, detail=f"Slot for {request.from_day} not found")

    def _calc_scheduled_at(day: str, existing_iso: str) -> str:
        base = datetime.fromisoformat(week_start + 'T09:00:00')
        base += timedelta(days=_WEEKDAY_OFFSET.get(day, 0))
        if existing_iso:
            try:
                parsed = datetime.fromisoformat(str(existing_iso).replace('Z', '+00:00'))
                base = base.replace(hour=parsed.hour, minute=parsed.minute)
            except ValueError:
                pass
        return base.replace(tzinfo=timezone.utc).isoformat()

    from_slot = slots[from_idx]

    if to_idx is not None:
        to_slot = slots[to_idx]
        from_post_res = (admin_supabase.table('posts').select('scheduled_at').eq('id', from_slot['post_id']).execute()
                         if from_slot.get('post_id') else None)
        to_post_res = (admin_supabase.table('posts').select('scheduled_at').eq('id', to_slot['post_id']).execute()
                       if to_slot.get('post_id') else None)
        from_sat = (from_post_res.data[0].get('scheduled_at') if from_post_res and from_post_res.data else '')
        to_sat = (to_post_res.data[0].get('scheduled_at') if to_post_res and to_post_res.data else '')

        slots[from_idx]['day'] = request.to_day
        slots[to_idx]['day'] = request.from_day
        if from_slot.get('post_id'):
            admin_supabase.table('posts').update(
                {'scheduled_at': _calc_scheduled_at(request.to_day, from_sat)}
            ).eq('id', from_slot['post_id']).execute()
        if to_slot.get('post_id'):
            admin_supabase.table('posts').update(
                {'scheduled_at': _calc_scheduled_at(request.from_day, to_sat)}
            ).eq('id', to_slot['post_id']).execute()
    else:
        from_post_res = (admin_supabase.table('posts').select('scheduled_at').eq('id', from_slot['post_id']).execute()
                         if from_slot.get('post_id') else None)
        from_sat = (from_post_res.data[0].get('scheduled_at') if from_post_res and from_post_res.data else '')
        slots[from_idx]['day'] = request.to_day
        if from_slot.get('post_id'):
            admin_supabase.table('posts').update(
                {'scheduled_at': _calc_scheduled_at(request.to_day, from_sat)}
            ).eq('id', from_slot['post_id']).execute()

    admin_supabase.table('content_proposals').update({'slots': slots}).eq('id', proposal_id).execute()
    return {'slots': slots}


class SlotImageRequest(BaseModel):
    drive_file_id: str


@router.patch("/proposals/{proposal_id}/slots/{slot_index}/image")
def update_slot_image(
    proposal_id: str,
    slot_index: int,
    request: SlotImageRequest,
    current_user: User = Depends(get_current_user),
    supabase: Client = Depends(get_user_supabase_client)
):
    proposal, slots = _get_proposal_and_slot(proposal_id, slot_index, str(current_user.id), supabase)
    post_id = slots[slot_index].get('post_id')

    if post_id:
        admin_supabase.table('posts').update({'drive_file_id': request.drive_file_id}).eq('id', post_id).execute()

    slots[slot_index]['image_id'] = request.drive_file_id
    admin_supabase.table('content_proposals').update({'slots': slots}).eq('id', proposal_id).execute()
    return {"updated": True}


@router.post("/campaign", response_model=MonthlyCampaign)
def upsert_monthly_campaign(
    campaign: MonthlyCampaign,
    current_user: User = Depends(get_current_user)
):
    try:
        # Verify account exists and belongs to current_user
        acc_res = admin_supabase.table('instagram_accounts').select('user_id').eq('id', campaign.account_id).execute()
        if not acc_res.data:
            raise HTTPException(status_code=404, detail="Cuenta de Instagram no encontrada")
        if str(acc_res.data[0]['user_id']) != str(current_user.id):
            raise HTTPException(status_code=403, detail="No tienes acceso a esta cuenta")

        payload = {
            'account_id': campaign.account_id,
            'month_date': campaign.month_date,
            'strategy_mode': campaign.strategy_mode,
            'title': campaign.title,
            'description': campaign.description,
            'milestones': campaign.milestones,
            'weekly_focus': campaign.weekly_focus
        }
        if campaign.id:
            payload['id'] = campaign.id

        upsert_res = admin_supabase.table('monthly_campaigns').upsert(payload, on_conflict='account_id,month_date').execute()
        if not upsert_res.data:
            raise HTTPException(status_code=500, detail="Error al guardar la campaña mensual")
        
        row = upsert_res.data[0]
        return MonthlyCampaign(
            id=str(row['id']),
            account_id=row['account_id'],
            month_date=str(row['month_date']),
            strategy_mode=row['strategy_mode'],
            title=row['title'],
            description=row['description'],
            milestones=row.get('milestones') or [],
            weekly_focus=row.get('weekly_focus') or {}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error upserting monthly campaign: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al guardar la campaña mensual: {str(e)}")


@router.get("/campaign", response_model=Optional[MonthlyCampaign])
def get_monthly_campaign(
    account_id: int,
    month_date: str,
    current_user: User = Depends(get_current_user),
    supabase: Client = Depends(get_user_supabase_client)
):
    try:
        # Verify account exists and belongs to current_user
        acc_res = admin_supabase.table('instagram_accounts').select('user_id').eq('id', account_id).execute()
        if not acc_res.data:
            raise HTTPException(status_code=404, detail="Cuenta de Instagram no encontrada")
        if str(acc_res.data[0]['user_id']) != str(current_user.id):
            raise HTTPException(status_code=403, detail="No tienes acceso a esta cuenta")

        campaign_res = supabase.table('monthly_campaigns')\
            .select('*')\
            .eq('account_id', account_id)\
            .eq('month_date', month_date)\
            .execute()
            
        if not campaign_res.data:
            return None
            
        row = campaign_res.data[0]
        return MonthlyCampaign(
            id=str(row['id']),
            account_id=row['account_id'],
            month_date=str(row['month_date']),
            strategy_mode=row['strategy_mode'],
            title=row['title'],
            description=row['description'],
            milestones=row.get('milestones') or [],
            weekly_focus=row.get('weekly_focus') or {}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting monthly campaign: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al obtener la campaña mensual: {str(e)}")


def _get_campaign_and_verify_owner(campaign_id: str, user_id: str, supabase: Client) -> dict:
    """Shared helper for the approve/reject/chat campaign endpoints: validates
    ownership through the campaign's account and returns the campaign row."""
    campaign_res = supabase.table('monthly_campaigns').select('*').eq('id', campaign_id).execute()
    if not campaign_res.data:
        raise HTTPException(status_code=404, detail="Campaña no encontrada")
    campaign = campaign_res.data[0]
    acc_res = admin_supabase.table('instagram_accounts').select('user_id').eq('id', campaign['account_id']).execute()
    if not acc_res.data or str(acc_res.data[0]['user_id']) != str(user_id):
        raise HTTPException(status_code=403, detail="No tienes acceso a esta campaña")
    return campaign


@router.post("/campaign/{campaign_id}/approve")
def approve_campaign(
    campaign_id: str,
    current_user: User = Depends(get_current_user),
    supabase: Client = Depends(get_user_supabase_client)
):
    campaign = _get_campaign_and_verify_owner(campaign_id, str(current_user.id), supabase)
    if campaign.get('status') != 'pending_approval':
        raise HTTPException(status_code=409, detail="La campaña no está pendiente de aprobación")

    update_res = admin_supabase.table('monthly_campaigns').update({
        'status': 'approved',
        'resolved_at': datetime.now(timezone.utc).isoformat()
    }).eq('id', campaign_id).execute()

    return update_res.data[0] if update_res.data else {}


@router.post("/campaign/{campaign_id}/reject")
def reject_campaign(
    campaign_id: str,
    current_user: User = Depends(get_current_user),
    supabase: Client = Depends(get_user_supabase_client)
):
    campaign = _get_campaign_and_verify_owner(campaign_id, str(current_user.id), supabase)
    if campaign.get('status') != 'pending_approval':
        raise HTTPException(status_code=409, detail="La campaña no está pendiente de aprobación")

    update_res = admin_supabase.table('monthly_campaigns').update({
        'status': 'rejected',
        'resolved_at': datetime.now(timezone.utc).isoformat()
    }).eq('id', campaign_id).execute()

    return update_res.data[0] if update_res.data else {}


class CampaignChatRequest(BaseModel):
    message: str


@router.post("/campaign/{campaign_id}/chat")
async def chat_with_campaign(
    campaign_id: str,
    request: CampaignChatRequest,
    current_user: User = Depends(get_current_user),
    supabase: Client = Depends(get_user_supabase_client)
):
    """Streams Hermes' progress (tool calls) and final answer as NDJSON while it
    interprets a natural-language adjustment to a monthly campaign. Ownership is
    checked before the stream opens; any error afterwards becomes a 'done' line
    since headers are already sent (design.md §API Changes)."""
    campaign = _get_campaign_and_verify_owner(campaign_id, str(current_user.id), supabase)
    account_id = campaign['account_id']

    async def event_stream():
        queue: asyncio.Queue = asyncio.Queue()
        done_marker = object()

        def on_progress(event):
            queue.put_nowait(event)

        async def run():
            try:
                result = await run_edit_session(
                    account_id=account_id,
                    edit_type="CAMPAIGN_CHAT",
                    context={"campaign_id": campaign_id},
                    user_message=request.message,
                    on_progress=on_progress
                )
                queue.put_nowait({"type": "done", "resolved": result.resolved, "message": result.message})
            except Exception as e:
                queue.put_nowait({"type": "done", "resolved": False, "message": str(e)})
            finally:
                queue.put_nowait(done_marker)

        task = asyncio.create_task(run())
        try:
            while True:
                event = await queue.get()
                if event is done_marker:
                    break
                yield (json.dumps(event) + "\n").encode()
        finally:
            await task

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")

