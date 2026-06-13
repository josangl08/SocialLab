from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, status
from pydantic import BaseModel
from database.supabase_client import get_supabase_client
from models.schemas import User, AgentConfig, ContentProposal
from auth.dependencies import get_current_user
import uuid
import json
import os
import logging
import google.generativeai as genai

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/agent", tags=["Agent"])
supabase = get_supabase_client()

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
        acc_res = supabase.table('instagram_accounts').select('user_id').eq('id', request.account_id).execute()
        if not acc_res.data:
            raise HTTPException(status_code=404, detail="Cuenta de Instagram no encontrada")
        if str(acc_res.data[0]['user_id']) != str(current_user.id):
            raise HTTPException(status_code=403, detail="No tienes acceso a esta cuenta")

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
    current_user: User = Depends(get_current_user)
):
    """
    Lists all content proposals for the authenticated user's Instagram account.
    """
    try:
        # Verify account exists and belongs to current_user
        acc_res = supabase.table('instagram_accounts').select('user_id').eq('id', account_id).execute()
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
        acc_res = supabase.table('instagram_accounts').select(STRATEGY_FIELDS).eq('id', account_id).execute()
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
        acc_res = supabase.table('instagram_accounts').select('user_id').eq('id', account_id).execute()
        if not acc_res.data:
            raise HTTPException(status_code=404, detail="Cuenta de Instagram no encontrada")
        if str(acc_res.data[0]['user_id']) != str(current_user.id):
            raise HTTPException(status_code=403, detail="No tienes acceso a esta cuenta")

        supabase.table('instagram_accounts').update({
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
