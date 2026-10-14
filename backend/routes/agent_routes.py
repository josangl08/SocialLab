from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator
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
from utils.timezones import effective_timezone, get_zone_info, local_to_utc, to_local
from services.gemini_service import generate_gemini_content, clean_and_parse_json, regenerate_slot_caption
from services.analytics.analytics_service import AnalyticsService
from services.hermes.orchestrator import run_edit_session
from services.hermes.memory import append_correction

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

        # Instante real de cada post enlazado: el panel coloca el slot por esta
        # fecha (en la zona de la cuenta), igual que el calendario (AD-7)
        post_ids = list({
            slot['post_id'] for row in proposals_res.data for slot in (row.get('slots') or [])
            if isinstance(slot, dict) and slot.get('post_id')
        })
        scheduled_by_post: dict = {}
        if post_ids:
            posts_res = admin_supabase.table('posts').select('id, scheduled_at').in_('id', post_ids).execute()
            scheduled_by_post = {p['id']: p.get('scheduled_at') for p in (posts_res.data or [])}

        proposals = []
        for row in proposals_res.data:
            try:
                proposals.append(ContentProposal(
                    id=str(row['id']),
                    account_id=str(row['account_id']),
                    week_start=str(row['week_start']),
                    slots=[
                        {**slot, 'scheduled_at': scheduled_by_post.get(slot.get('post_id'))}
                        for slot in row['slots']
                    ],
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
        posts_res = admin_supabase.table('posts').select('id, scheduled_at, media_url, drive_file_id').in_('id', post_ids).execute()
        for post in (posts_res.data or []):
            admin_supabase.table('posts').update({'status': 'scheduled'}).eq('id', post['id']).execute()
            if post.get('media_url') or post.get('drive_file_id'):
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
    'posts_per_week, scheduling_mode, preferred_days, content_type_mix, last_agent_sync, '
    'humanizer_enabled, banned_phrases'
)

@router.get("/config/{account_id}")
def get_agent_config(
    account_id: int,
    current_user: User = Depends(get_current_user)
):
    try:
        acc_res = admin_supabase.table('instagram_accounts').select(f'user_id, {STRATEGY_FIELDS}').eq('id', account_id).execute()
        if not acc_res.data:
            raise HTTPException(status_code=404, detail="Cuenta no encontrada")
        row = acc_res.data[0]
        if str(row.get('user_id')) != str(current_user.id):
            raise HTTPException(status_code=403, detail="No tienes acceso a esta cuenta")
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
            'humanizer_enabled': row.get('humanizer_enabled', True) is not False,
            'banned_phrases': row.get('banned_phrases') or [],
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

        update_data = {
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
        }
        # Solo si se envían: clientes que no conocen el filtro no lo resetean
        if config.humanizer_enabled is not None:
            update_data['humanizer_enabled'] = config.humanizer_enabled
        if config.banned_phrases is not None:
            update_data['banned_phrases'] = list(dict.fromkeys(
                p.strip() for p in config.banned_phrases if p.strip()
            ))
        admin_supabase.table('instagram_accounts').update(update_data).eq('id', account_id).execute()

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


class SlotHookRequest(BaseModel):
    hook: str


@router.patch("/proposals/{proposal_id}/slots/{slot_index}/hook")
def select_slot_hook(
    proposal_id: str,
    slot_index: int,
    request: SlotHookRequest,
    current_user: User = Depends(get_current_user),
    supabase: Client = Depends(get_user_supabase_client)
):
    """Swap the caption's first line for one of the slot's hook_candidates (Reels)."""
    proposal, slots = _get_proposal_and_slot(proposal_id, slot_index, str(current_user.id), supabase)
    slot = slots[slot_index]
    if request.hook not in (slot.get('hook_candidates') or []):
        raise HTTPException(status_code=422, detail="El gancho no es uno de los candidatos del slot")

    rest = (slot.get('caption') or '').split('\n', 1)
    caption = request.hook + (f"\n{rest[1]}" if len(rest) > 1 else '')

    post_id = slot.get('post_id')
    if post_id:
        admin_supabase.table('posts').update({'content': caption}).eq('id', post_id).execute()

    slots[slot_index]['caption'] = caption
    admin_supabase.table('content_proposals').update({'slots': slots}).eq('id', proposal_id).execute()
    return {"caption": caption}


_WEEKDAY_OFFSET: dict = {
    'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 'Thursday': 3,
    'Friday': 4, 'Saturday': 5, 'Sunday': 6,
}


class SlotReorderRequest(BaseModel):
    from_day: str
    to_day: str
    timezone: Optional[str] = None  # zona en la que el usuario ve la propuesta (AD-8)

    @field_validator('timezone')
    @classmethod
    def _validate_timezone(cls, value: Optional[str]) -> Optional[str]:
        return get_zone_info(value).key if value else None


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
    acc_res = admin_supabase.table('instagram_accounts').select(
        'user_id, primary_timezone, detected_timezone'
    ).eq('id', proposal['account_id']).execute()
    if not acc_res.data or str(acc_res.data[0]['user_id']) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Access denied")
    tz = effective_timezone(acc_res.data[0], request.timezone)

    slots = list(proposal.get('slots', []))
    week_start = str(proposal['week_start'])  # e.g. "2026-06-29"

    from_idx = next((i for i, s in enumerate(slots) if s.get('day') == request.from_day), None)
    to_idx = next((i for i, s in enumerate(slots) if s.get('day') == request.to_day), None)

    if from_idx is None:
        raise HTTPException(status_code=404, detail=f"Slot for {request.from_day} not found")

    def _calc_scheduled_at(day: str, existing_iso: str) -> str:
        # Día de la semana en la zona de la cuenta conservando la hora de pared del
        # post en esa zona, también si se cruza un cambio de horario (AD-8)
        base = datetime.fromisoformat(week_start + 'T09:00:00')
        base += timedelta(days=_WEEKDAY_OFFSET.get(day, 0))
        if existing_iso:
            try:
                parsed = to_local(datetime.fromisoformat(str(existing_iso).replace('Z', '+00:00')), tz)
                base = base.replace(hour=parsed.hour, minute=parsed.minute)
            except ValueError:
                pass
        return local_to_utc(base, tz).isoformat()

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
        # La imagen elegida sustituye a una foto adjuntada antes (media_url manda al publicar)
        admin_supabase.table('posts').update({'drive_file_id': request.drive_file_id, 'media_url': None}).eq('id', post_id).execute()

    slots[slot_index]['image_id'] = request.drive_file_id
    slots[slot_index]['media_url'] = None
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


# ==============================================================================
# HERMES MIND — DECISION INTELLIGENCE ENDPOINTS
# ==============================================================================

def _verify_account_owner(account_id: int, user_id: str) -> None:
    """Ownership check reused verbatim by all Hermes Mind endpoints (design.md §API
    Changes) — matches the pattern already used across this file's other routes."""
    acc_res = admin_supabase.table('instagram_accounts').select('user_id').eq('id', account_id).execute()
    if not acc_res.data:
        raise HTTPException(status_code=404, detail="Cuenta de Instagram no encontrada")
    if str(acc_res.data[0]['user_id']) != str(user_id):
        raise HTTPException(status_code=403, detail="No tienes acceso a esta cuenta")


def _get_decision_and_verify_owner(decision_id: int, user_id: str) -> dict:
    """Shared helper: fetches an agent_decisions row and validates ownership via its
    account_id, same 403/404 shape as _verify_account_owner."""
    dec_res = admin_supabase.table('agent_decisions').select('*').eq('id', decision_id).execute()
    if not dec_res.data:
        raise HTTPException(status_code=404, detail="Decisión no encontrada")
    decision = dec_res.data[0]
    account_id = decision.get('account_id')
    if account_id is None:
        raise HTTPException(status_code=404, detail="Decisión no encontrada")
    _verify_account_owner(account_id, user_id)
    return decision


def _proposal_scope(account_id: int, proposal_id: Optional[str]):
    """Given a proposal_id, returns (proposal_id, [post_ids in its slots]) so a
    decisions query can be scoped to that week. Returns (None, None) when no
    proposal_id is passed — callers then don't filter."""
    if not proposal_id:
        return None, None
    res = admin_supabase.table('content_proposals')\
        .select('id, slots').eq('id', proposal_id).eq('account_id', account_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Propuesta no encontrada")
    slots = res.data[0].get('slots') or []
    return proposal_id, [s['post_id'] for s in slots if s.get('post_id')]


def _apply_proposal_filter(query, proposal_id: Optional[str], post_ids):
    """Adds `related_proposal_id == proposal_id OR related_post_id IN post_ids` to a
    Supabase decisions query. No-op when proposal_id is falsy."""
    if not proposal_id:
        return query
    ors = [f"related_proposal_id.eq.{proposal_id}"]
    if post_ids:
        ors.append(f"related_post_id.in.({','.join(str(p) for p in post_ids)})")
    return query.or_(",".join(ors))


_ARTIFACT_DECISION_TYPES = ("supabase_create_post", "supabase_create_proposal")


def _orphan_decision_ids(account_id: int) -> list[int]:
    """IDs of 'artifact' decisions (created a post or a proposal) whose artifact is
    gone: the post no longer exists AND the proposal is null or rejected. These pile
    up in Hermes Mind after a proposal is rejected (its draft posts are deleted,
    `related_post_id` becomes NULL via ON DELETE SET NULL). Suggestions are never
    orphaned."""
    rows = admin_supabase.table('agent_decisions')\
        .select('id, decision_type, related_post_id, related_proposal_id')\
        .eq('account_id', account_id).execute().data or []
    candidates = [r for r in rows if r.get('decision_type') in _ARTIFACT_DECISION_TYPES]
    if not candidates:
        return []

    post_ids = [r['related_post_id'] for r in candidates if r.get('related_post_id')]
    live_post_ids: set = set()
    if post_ids:
        live = admin_supabase.table('posts').select('id').in_('id', post_ids).execute().data or []
        live_post_ids = {p['id'] for p in live}

    prop_ids = [r['related_proposal_id'] for r in candidates if r.get('related_proposal_id')]
    prop_status: dict = {}
    if prop_ids:
        pr = admin_supabase.table('content_proposals').select('id, status').in_('id', prop_ids).execute().data or []
        prop_status = {p['id']: p.get('status') for p in pr}

    orphans: list[int] = []
    for r in candidates:
        has_live_post = r.get('related_post_id') in live_post_ids
        pid = r.get('related_proposal_id')
        proposal_ok = pid is not None and prop_status.get(pid) not in (None, 'rejected')
        if not has_live_post and not proposal_ok:
            orphans.append(r['id'])
    return orphans


@router.get("/decisions")
async def list_decisions(
    account_id: int,
    page: int = 1,
    per_page: int = 20,
    proposal_id: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    _verify_account_owner(account_id, str(current_user.id))
    scoped_proposal_id, scoped_post_ids = _proposal_scope(account_id, proposal_id)

    offset = (page - 1) * per_page
    query = admin_supabase.table('agent_decisions')\
        .select(
            'id, decision_type, confidence_score, applied_rule_labels, rationale, status, '
            'created_at, related_post_id, related_proposal_id, campaign_id',
            count='exact',
        )\
        .eq('account_id', account_id)
    query = _apply_proposal_filter(query, scoped_proposal_id, scoped_post_ids)
    orphan_ids = _orphan_decision_ids(account_id)
    if orphan_ids:
        query = query.not_.in_('id', orphan_ids)
    res = query\
        .order('created_at', desc=True)\
        .range(offset, offset + per_page - 1)\
        .execute()

    decisions = res.data or []

    # Enrich each decision with a short human label for what it targeted (post
    # type + date, or "Propuesta", or the campaign title) so the card can say
    # what it refers to without a second request.
    post_ids = [d['related_post_id'] for d in decisions if d.get('related_post_id')]
    posts_by_id = {}
    if post_ids:
        posts_res = admin_supabase.table('posts')\
            .select('id, post_type, scheduled_at, media_url, drive_file_id').in_('id', post_ids).execute()
        posts_by_id = {p['id']: p for p in (posts_res.data or [])}
    campaign_ids = list({d['campaign_id'] for d in decisions if d.get('campaign_id')})
    campaigns_by_id = {}
    if campaign_ids:
        camp_res = admin_supabase.table('monthly_campaigns').select('id, title').in_('id', campaign_ids).execute()
        campaigns_by_id = {c['id']: c for c in (camp_res.data or [])}

    for d in decisions:
        target = None
        d['media_url'] = None
        d['post_type'] = None
        d['drive_file_id'] = None
        if d.get('related_post_id') and d['related_post_id'] in posts_by_id:
            p = posts_by_id[d['related_post_id']]
            ptype = (p.get('post_type') or 'post').capitalize()
            sched = p.get('scheduled_at')
            target = f"{ptype} · {sched[:10]}" if sched else f"{ptype} #{d['related_post_id']}"
            d['media_url'] = p.get('media_url')
            d['post_type'] = p.get('post_type')
            d['drive_file_id'] = p.get('drive_file_id')
        elif d.get('related_proposal_id'):
            target = "Propuesta semanal"
        d['target_label'] = target
        d['campaign_label'] = campaigns_by_id.get(d.get('campaign_id'), {}).get('title') if d.get('campaign_id') else None

    total = res.count if isinstance(res.count, int) else 0
    return {
        "data": decisions,
        "meta": {"total": total, "page": page, "per_page": per_page},
    }


@router.get("/decisions/{decision_id}")
async def get_decision_detail(decision_id: int, current_user: User = Depends(get_current_user)):
    decision = _get_decision_and_verify_owner(decision_id, str(current_user.id))

    applied_rules = []
    rule_ids = decision.get("applied_rule_ids") or []
    if rule_ids:
        rules_res = admin_supabase.table('account_brand_rules').select('*').in_('id', rule_ids).execute()
        applied_rules = rules_res.data or []

    # The post/proposal this decision produced, so the Órbita panel can preview it
    # without a second request.
    post = None
    if decision.get("related_post_id"):
        post_res = admin_supabase.table('posts')\
            .select('id, post_type, scheduled_at, content, media_url, status, drive_file_id')\
            .eq('id', decision['related_post_id']).execute()
        post = post_res.data[0] if post_res.data else None

    proposal = None
    if decision.get("related_proposal_id"):
        prop_res = admin_supabase.table('content_proposals')\
            .select('id, week_start, status, slots')\
            .eq('id', decision['related_proposal_id']).execute()
        if prop_res.data:
            row = prop_res.data[0]
            proposal = {
                "id": row["id"], "week_start": row.get("week_start"), "status": row.get("status"),
                "slots": len(row.get("slots") or []),
            }

    return {"decision": decision, "applied_rules": applied_rules, "post": post, "proposal": proposal}


@router.get("/decisions/{decision_id}/audit-trail")
async def get_decision_audit_trail(decision_id: int, current_user: User = Depends(get_current_user)):
    decision = _get_decision_and_verify_owner(decision_id, str(current_user.id))

    applied_rules = []
    rule_ids = decision.get("applied_rule_ids") or []
    if rule_ids:
        rules_res = admin_supabase.table('account_brand_rules').select('*').in_('id', rule_ids).execute()
        applied_rules = rules_res.data or []

    correction_ids = [r['source_correction_id'] for r in applied_rules if r.get('source_correction_id') is not None]
    source_corrections = []
    if correction_ids:
        corrections_res = admin_supabase.table('agent_memory').select('*').in_('id', correction_ids).execute()
        source_corrections = corrections_res.data or []

    return {
        "decision": decision,
        "applied_rules": applied_rules,
        "source_corrections": source_corrections,
    }


@router.get("/context-graph")
async def get_context_graph(
    account_id: int,
    proposal_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    acc_res = admin_supabase.table('instagram_accounts').select('*').eq('id', account_id).execute()
    if not acc_res.data:
        raise HTTPException(status_code=404, detail="Cuenta de Instagram no encontrada")
    account = acc_res.data[0]
    if str(account['user_id']) != str(current_user.id):
        raise HTTPException(status_code=403, detail="No tienes acceso a esta cuenta")
    account_label = account.get('username') or f"Cuenta {account_id}"
    scoped_proposal_id, scoped_post_ids = _proposal_scope(account_id, proposal_id)

    nodes = [{"id": f"account-{account_id}", "type": "account", "data": {"label": account_label}}]
    edges = []

    # --- Strategy node: always present (spec: aparece con o sin reglas activas) ---
    strategy_node_id = f"strategy-{account_id}"
    nodes.append({
        "id": strategy_node_id,
        "type": "strategy",
        "data": {
            "label": "Estrategia de cuenta",
            "tone": account.get("default_tone"),
            "style_guide": account.get("style_guide"),
            "target_audience": account.get("target_audience"),
            "hashtag_strategy": account.get("hashtag_strategy"),
            "posting_frequency": account.get("posting_frequency"),
            "best_times": account.get("best_times"),
            "content_type_mix": account.get("content_type_mix"),
            "memory_summary": account.get("agent_memory_summary"),
        },
    })
    edges.append({
        "id": f"e-account-strategy-{account_id}",
        "source": f"account-{account_id}",
        "target": strategy_node_id,
    })

    # --- Rule nodes: version-aware. Fetch ALL rules (incl. inactive) so version
    # chains can be walked; only active rules become graph nodes. `.order('id')`
    # keeps this from matching the single-.eq() chain some tests stub. ---
    all_rules = admin_supabase.table('account_brand_rules')\
        .select('*').eq('account_id', account_id).order('id').execute().data or []
    rules_by_id = {r["id"]: r for r in all_rules if r.get("id") is not None}
    active_rules = [r for r in all_rules if r.get("is_active")]
    active_rule_ids = {r["id"] for r in active_rules}

    def _version_chain(rule: dict) -> list:
        chain, seen, cur = [], set(), rule
        while cur and cur.get("id") not in seen:
            seen.add(cur.get("id"))
            chain.append({
                "id": cur.get("id"),
                "rule_text": cur.get("rule_text"),
                "created_at": cur.get("created_at"),
            })
            pv = cur.get("previous_version_id")
            cur = rules_by_id.get(pv) if pv else None
        return list(reversed(chain))

    for rule in active_rules:
        rid = rule["id"]
        rule_node_id = f"rule-{rid}"
        cwid = rule.get("conflicts_with_id")
        conflicts_with = None
        if cwid and cwid in rules_by_id:
            conflicts_with = {"id": cwid, "rule_text": rules_by_id[cwid].get("rule_text")}
        nodes.append({
            "id": rule_node_id,
            "type": "rule",
            "data": {
                "label": rule.get("rule_text", ""),
                "rule_type": rule.get("rule_type"),
                "rule_text": rule.get("rule_text", ""),
                "version_chain": _version_chain(rule),
                "conflicts_with": conflicts_with,
            },
        })
        edges.append({"id": f"e-account-{rid}", "source": f"account-{account_id}", "target": rule_node_id})
        if conflicts_with and cwid in active_rule_ids:
            edges.append({
                "id": f"e-conflict-rule-{rid}-rule-{cwid}",
                "source": rule_node_id,
                "target": f"rule-{cwid}",
                "type": "conflict",
            })

    decisions_query = admin_supabase.table('agent_decisions')\
        .select('id, decision_type, related_post_id, campaign_id, applied_rule_ids, created_at')\
        .eq('account_id', account_id)
    decisions_query = _apply_proposal_filter(decisions_query, scoped_proposal_id, scoped_post_ids)
    orphan_ids = _orphan_decision_ids(account_id)
    if orphan_ids:
        decisions_query = decisions_query.not_.in_('id', orphan_ids)
    decisions_res = decisions_query\
        .order('created_at', desc=True)\
        .limit(30)\
        .execute()
    decisions = decisions_res.data or []

    post_ids = list({d["related_post_id"] for d in decisions if d.get("related_post_id") is not None})
    posts_by_id = {}
    if post_ids:
        posts_res = admin_supabase.table('posts')\
            .select('id, post_type, scheduled_at, content, media_url, status, drive_file_id')\
            .in_('id', post_ids).execute()
        posts_by_id = {p['id']: p for p in (posts_res.data or [])}

    seen_post_ids = set()
    for decision in decisions:
        post_id = decision.get("related_post_id")
        if post_id is None or post_id in seen_post_ids:
            continue
        seen_post_ids.add(post_id)
        post_node_id = f"post-{post_id}"
        post_row = posts_by_id.get(post_id, {})
        post_type = (post_row.get("post_type") or "post").capitalize()
        scheduled_at = post_row.get("scheduled_at")
        date_label = scheduled_at[:10] if scheduled_at else f"#{post_id}"
        nodes.append({"id": post_node_id, "type": "post", "data": {
            "label": f"{post_type} · {date_label}",
            "post_id": post_id,
            "post_type": post_row.get("post_type"),
            "scheduled_at": scheduled_at,
            "status": post_row.get("status"),
            "caption": post_row.get("content"),
            "media_url": post_row.get("media_url"),
            "drive_file_id": post_row.get("drive_file_id"),
        }})
        for rule_id in (decision.get("applied_rule_ids") or []):
            edges.append({
                "id": f"e-rule-{rule_id}-post-{post_id}",
                "source": f"rule-{rule_id}",
                "target": post_node_id,
            })

    # --- Campaign nodes: one per DISTINCT campaign_id among the decisions shown ---
    campaign_ids = list({d["campaign_id"] for d in decisions if d.get("campaign_id")})

    # Always surface the current month's campaign as strategy context, even when no
    # decision links it yet (e.g. it's still pending_approval) — otherwise Hermes
    # Mind can't say which campaign is in play.
    from datetime import date
    current_month = date.today().replace(day=1).isoformat()
    cur_res = admin_supabase.table('monthly_campaigns')\
        .select('id, title, description, strategy_mode, weekly_focus, milestones, status')\
        .eq('account_id', account_id).eq('month_date', current_month).execute()
    current_campaign = cur_res.data[0] if cur_res.data else None
    if current_campaign and current_campaign['id'] not in campaign_ids:
        campaign_ids.append(current_campaign['id'])

    campaigns_by_id = {}
    if campaign_ids:
        camp_res = admin_supabase.table('monthly_campaigns')\
            .select('id, title, description, strategy_mode, weekly_focus, milestones, status')\
            .in_('id', campaign_ids).execute()
        campaigns_by_id = {c["id"]: c for c in (camp_res.data or [])}

    for cid in campaign_ids:
        c = campaigns_by_id.get(cid, {})
        campaign_node_id = f"campaign-{cid}"
        nodes.append({
            "id": campaign_node_id,
            "type": "campaign",
            "data": {
                "label": c.get("title") or "Campaña",
                "title": c.get("title"),
                "description": c.get("description"),
                "strategy_mode": c.get("strategy_mode"),
                "weekly_focus": c.get("weekly_focus"),
                "milestones": c.get("milestones") or [],
                "status": c.get("status"),
            },
        })
        edges.append({
            "id": f"e-account-campaign-{cid}",
            "source": f"account-{account_id}",
            "target": campaign_node_id,
        })

    for decision in decisions:
        cid = decision.get("campaign_id")
        post_id = decision.get("related_post_id")
        if cid and post_id and post_id in seen_post_ids:
            edges.append({
                "id": f"e-campaign-{cid}-post-{post_id}",
                "source": f"campaign-{cid}",
                "target": f"post-{post_id}",
            })

    return {"nodes": nodes, "edges": edges}


class DecisionOverrideRequest(BaseModel):
    user_message: str


@router.post("/decisions/{decision_id}/override")
async def override_decision(
    decision_id: int,
    request: DecisionOverrideRequest,
    current_user: User = Depends(get_current_user)
):
    decision = _get_decision_and_verify_owner(decision_id, str(current_user.id))

    correction = append_correction(
        account_id=decision['account_id'],
        edit_type="HERMES_MIND_OVERRIDE",
        user_message=request.user_message,
        resolution=f"Usuario anuló la decisión #{decision_id} ({decision.get('decision_type')})",
    )

    admin_supabase.table('agent_decisions').update({
        "status": "overridden",
        "overridden_at": datetime.now(timezone.utc).isoformat(),
        "override_correction_id": correction.get("id"),
    }).eq('id', decision_id).execute()

    return {"overridden": True, "correction_id": correction.get("id")}


# Which account-config column each suggestion type writes when accepted, and the
# key inside the decision's tool_args holding the value to write.
_SUGGESTION_APPLY = {
    "suggest_schedule_change": ("best_times", "suggested_best_times"),
    "suggest_mix_change": ("content_type_mix", "suggested_content_type_mix"),
}


@router.post("/decisions/{decision_id}/accept-suggestion")
async def accept_suggestion(decision_id: int, current_user: User = Depends(get_current_user)):
    """Accepts a Hermes schedule/mix suggestion: writes the suggested value into the
    account's configuration and marks the decision `accepted`. Only valid on a
    `suggested`-status decision of a known suggestion type."""
    decision = _get_decision_and_verify_owner(decision_id, str(current_user.id))

    if decision.get("status") != "suggested":
        raise HTTPException(status_code=409, detail="Esta decisión no es una sugerencia pendiente")

    apply = _SUGGESTION_APPLY.get(decision.get("decision_type"))
    if apply is None:
        raise HTTPException(status_code=422, detail="Este tipo de sugerencia no se puede aplicar automáticamente")

    config_column, args_key = apply
    suggested_value = (decision.get("tool_args") or {}).get(args_key)
    if not suggested_value:
        raise HTTPException(status_code=422, detail="La sugerencia no incluye un valor aplicable")

    admin_supabase.table('instagram_accounts').update({
        config_column: suggested_value,
    }).eq('id', decision['account_id']).execute()

    admin_supabase.table('agent_decisions').update({
        "status": "accepted",
        "accepted_at": datetime.now(timezone.utc).isoformat(),
    }).eq('id', decision_id).execute()

    return {"accepted": True, "config_column": config_column, "applied_value": suggested_value}


class VisualBackfillRequest(BaseModel):
    batch_size: int = 10


@router.post("/visual-analyses/backfill")
async def backfill_visual_analyses(
    account_id: int,
    request: Optional[VisualBackfillRequest] = None,
    current_user: User = Depends(get_current_user),
):
    """Completa en lotes las filas de visual_analyses de la cuenta que aún no tienen
    aesthetic_score (re-analiza la imagen con Gemini Vision y fusiona solo los campos
    nuevos). Idempotente: re-ejecutar continúa donde lo dejó."""
    _verify_account_owner(account_id, str(current_user.id))
    batch_size = request.batch_size if request else 10
    from services.hermes.visual_backfill import backfill_visual_scores
    return await backfill_visual_scores(account_id, batch_size=batch_size)


@router.get("/capabilities")
def get_agent_capabilities(current_user: User = Depends(get_current_user)):
    """Catálogo estático de las capacidades de Hermes (playbooks, skills runtime y
    cálculos deterministas) con su perfil de coste. Para Hermes Mind."""
    from services.hermes.capabilities import HERMES_CAPABILITIES
    return HERMES_CAPABILITIES

