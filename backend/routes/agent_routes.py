from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, status
from pydantic import BaseModel
from typing import Literal, Optional
from database.supabase_client import get_supabase_admin_client
from models.schemas import User, AgentConfig, ContentProposal, MonthlyCampaign
from auth.dependencies import get_current_user, get_user_supabase_client
from supabase import Client
from datetime import datetime, timezone, timedelta
import uuid
import json
import os
import logging
import google.generativeai as genai

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/agent", tags=["Agent"])
admin_supabase = get_supabase_admin_client()

class TriggerRequest(BaseModel):
    account_id: int

@router.post("/trigger")
async def trigger_agent(
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

@router.get("/proposals", response_model=list[ContentProposal])
async def list_proposals(
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
            proposals.append(ContentProposal(
                id=str(row['id']),
                account_id=str(row['account_id']),
                week_start=str(row['week_start']),
                slots=row['slots'],
                status=row['status']
            ))
        return proposals
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing proposals: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al obtener las propuestas: {str(e)}")

@router.post("/proposals/{proposal_id}/approve")
async def approve_proposal(
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
async def reject_proposal(
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
    'content_pillars, hashtag_strategy, reference_accounts, '
    'posts_per_week, scheduling_mode, preferred_days, content_type_mix, last_agent_sync'
)

@router.get("/config/{account_id}")
async def get_agent_config(
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
async def update_agent_config(
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


@router.post("/suggest-times")
async def suggest_times(
    request: SuggestTimesRequest,
    current_user: User = Depends(get_current_user)
):
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GOOGLE_API_KEY no configurado")
    genai.configure(api_key=api_key)

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
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return json.loads(text)
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
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GOOGLE_API_KEY no configurado")
    genai.configure(api_key=api_key)

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
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return json.loads(text)
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

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GOOGLE_API_KEY no configurado")
    genai.configure(api_key=api_key)

    image_id = slot.get('image_id')
    description_context = ""
    if image_id:
        va_res = supabase.table('visual_analyses').select('gemini_description').eq('drive_file_id', image_id).execute()
        if va_res.data:
            description_context = str(va_res.data[0].get('gemini_description', ''))

    theme = slot.get('theme', '')
    prompt = (
        f"Genera un nuevo caption creativo para Instagram sobre el tema: '{theme}'. "
        f"Contexto visual: {description_context or 'imagen inspiradora'}. "
        f"Tono: auténtico e inspirador. Termina con una pregunta de engagement. "
        f"Incluye 3-5 hashtags relevantes. Solo el caption, sin explicaciones."
    )

    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        new_caption = response.text.strip()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al regenerar caption: {str(e)}")

    admin_supabase.table('posts').update({'content': new_caption}).eq('id', post_id).execute()
    slots[slot_index]['caption'] = new_caption
    admin_supabase.table('content_proposals').update({'slots': slots}).eq('id', proposal_id).execute()

    return {"caption": new_caption}


@router.post("/proposals/{proposal_id}/slots/{slot_index}/skip")
async def skip_slot(
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
async def update_slot_type(
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
async def reorder_proposal_slot(
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
async def update_slot_image(
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
async def upsert_monthly_campaign(
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
async def get_monthly_campaign(
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

