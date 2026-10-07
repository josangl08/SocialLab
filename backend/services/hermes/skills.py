"""
Hermes Skills
Capacidades dinámicas que Hermes puede invocar bajo demanda: generan (o reutilizan)
un análisis vía Gemini y lo persisten como una "skill" reutilizable por cuenta.

Diseño de seguridad: el código que Gemini escribe se ejecuta en el sandbox propio
de Google (Tool(code_execution=...)), nunca en nuestro backend — solo recibimos el
código generado (para auditoría) y su resultado. No hay ejecución de código
arbitrario en nuestra infraestructura.
"""

import re
import unicodedata
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from google.genai import types

from database.supabase_client import get_supabase_admin_client
from services.analytics.analytics_service import AnalyticsService
from services.gemini_service import SKILL_GEMINI_MODELS, get_gemini_client

logger = logging.getLogger(__name__)

VISUAL_PERFORMANCE_SKILL = "visual_performance_correlation"
_DEFAULT_FRESHNESS_DAYS = 14
_NICHE_INSIGHT_FRESHNESS_DAYS = 30


def get_skill(account_id: int, name: str) -> Optional[Dict[str, Any]]:
    supabase = get_supabase_admin_client()
    res = supabase.table("agent_skills").select("*").eq("account_id", account_id).eq("name", name).execute()
    return res.data[0] if res.data else None


def save_skill(account_id: int, name: str, generated_code: str, summary: str) -> Dict[str, Any]:
    supabase = get_supabase_admin_client()
    payload = {
        "account_id": account_id,
        "name": name,
        "generated_code": generated_code,
        "last_result_summary": summary,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    res = supabase.table("agent_skills").upsert(payload, on_conflict="account_id,name").execute()
    return res.data[0] if res.data else payload


def _is_fresh(skill_row: Dict[str, Any], freshness_days: int) -> bool:
    updated_at_raw = skill_row.get("updated_at")
    if not isinstance(updated_at_raw, str):
        return False
    updated_at = datetime.fromisoformat(updated_at_raw.replace("Z", "+00:00"))
    return datetime.now(timezone.utc) - updated_at < timedelta(days=freshness_days)


def _run_code_execution(prompt: str) -> Dict[str, str]:
    """Isolated Gemini call using only the code_execution tool — deliberately not
    mixed with the account's normal MCP function-declaration tools (confirmed via
    a real API call that mixing built-in tools with function calling requires an
    extra tool_config flag; keeping this call isolated avoids that entirely and
    is the right separation of concerns regardless)."""
    client = get_gemini_client()
    last_error: Optional[Exception] = None
    config = types.GenerateContentConfig(tools=[types.Tool(code_execution=types.ToolCodeExecution())])

    for model_name in SKILL_GEMINI_MODELS:
        try:
            response = client.models.generate_content(model=model_name, contents=prompt, config=config)
            break
        except Exception as e:
            last_error = e
            continue
    else:
        raise last_error or Exception("No SKILL_GEMINI_MODELS configured")

    code_parts = []
    result_parts = []
    text_parts = []
    for part in response.candidates[0].content.parts:
        if getattr(part, "executable_code", None) and part.executable_code.code:
            code_parts.append(part.executable_code.code)
        if getattr(part, "code_execution_result", None) and part.code_execution_result.output:
            result_parts.append(part.code_execution_result.output)
        if getattr(part, "text", None):
            text_parts.append(part.text)

    return {
        "generated_code": "\n\n".join(code_parts),
        "execution_result": "\n".join(result_parts),
        "summary": "\n".join(text_parts).strip(),
    }


def _run_search_grounding(prompt: str) -> Dict[str, Any]:
    """Isolated Gemini call using only the google_search tool — same isolation
    rationale as _run_code_execution."""
    client = get_gemini_client()
    last_error: Optional[Exception] = None
    config = types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())])

    for model_name in SKILL_GEMINI_MODELS:
        try:
            response = client.models.generate_content(model=model_name, contents=prompt, config=config)
            break
        except Exception as e:
            last_error = e
            continue
    else:
        raise last_error or Exception("No SKILL_GEMINI_MODELS configured")

    try:
        brief = response.text or ""
    except ValueError:
        brief = ""

    sources = []
    grounding_metadata = getattr(response.candidates[0], "grounding_metadata", None)
    for chunk in getattr(grounding_metadata, "grounding_chunks", None) or []:
        web = getattr(chunk, "web", None)
        if web and web.uri:
            sources.append({"title": web.title, "uri": web.uri})

    return {"brief": brief.strip(), "sources": sources}


def run_visual_performance_skill(account_id: int, force_refresh: bool = False, freshness_days: int = _DEFAULT_FRESHNESS_DAYS) -> Dict[str, Any]:
    """Correlates the visual theme/content of an account's posts (from Gemini
    Vision analysis) with their real Instagram performance, via Gemini's own
    code_execution sandbox. Reuses the last stored result unless it's stale or
    force_refresh is requested — the calling session decides which, based on the
    user's language ("actualiza esto" vs. just asking the same question again)."""
    existing = get_skill(account_id, VISUAL_PERFORMANCE_SKILL)
    if existing and not force_refresh and _is_fresh(existing, freshness_days):
        return {
            "summary": existing["last_result_summary"],
            "fresh": True,
            "regenerated": False,
        }

    supabase = get_supabase_admin_client()
    rows = AnalyticsService(db_client=supabase).get_visual_performance_data(account_id)
    if not rows:
        return {
            "summary": "Todavía no hay suficientes posts publicados con análisis visual e "
                       "interacciones reales para esta cuenta como para sacar una correlación fiable.",
            "fresh": False,
            "regenerated": False,
        }

    prompt = (
        "Estas son filas de datos de una cuenta de Instagram: cada una trae el tema/objetos/mood "
        "de la foto del post (de un análisis visual con IA) y sus métricas reales de rendimiento.\n\n"
        f"{rows}\n\n"
        "Escribe y ejecuta código Python (puedes usar pandas si lo necesitas) que calcule qué "
        "temas, objetos o moods visuales se correlacionan con mejor rendimiento (usa "
        "total_interactions como métrica principal). Luego resume el hallazgo en 2-3 frases en "
        "español, concreto y accionable — qué tipo de contenido visual le funciona mejor a esta cuenta."
    )

    try:
        result = _run_code_execution(prompt)
    except Exception as e:
        logger.error(f"Error ejecutando skill de rendimiento visual para cuenta {account_id}: {e}")
        return {
            "summary": "No pude completar el análisis de rendimiento visual esta vez.",
            "fresh": False,
            "regenerated": False,
        }

    save_skill(account_id, VISUAL_PERFORMANCE_SKILL, result["generated_code"], result["summary"])

    return {
        "summary": result["summary"],
        "fresh": False,
        "regenerated": True,
    }


def build_niche_key(account: Dict[str, Any]) -> str:
    """Construye un slug único como clave de nicho a partir de sector y purpose."""
    sector = (account.get("sector") or "").strip()
    purpose = (account.get("purpose") or "").strip()
    if not sector and not purpose:
        return ""
    combined = f"{sector}_{purpose}".strip("_")
    normalized = unicodedata.normalize("NFKD", combined).encode("ascii", "ignore").decode("utf-8")
    return re.sub(r"[^a-z0-9]+", "_", normalized.lower()).strip("_")


def resolve_niche(account: Dict[str, Any]) -> List[str]:
    """Compatibilidad retroactiva: devuelve una lista con la clave de nicho si existe."""
    key = build_niche_key(account)
    return [key] if key else []


def get_niche_insight(niche: str) -> Optional[Dict[str, Any]]:
    supabase = get_supabase_admin_client()
    res = supabase.table("niche_insights").select("*").eq("niche", niche).execute()
    return res.data[0] if res.data else None


def save_niche_insight(niche: str, brief: str, sources: List[Dict[str, str]], freshness_days: int = _NICHE_INSIGHT_FRESHNESS_DAYS) -> Dict[str, Any]:
    supabase = get_supabase_admin_client()
    now = datetime.now(timezone.utc)
    payload = {
        "niche": niche,
        "brief": brief,
        "sources": sources,
        "generated_at": now.isoformat(),
        "expires_at": (now + timedelta(days=freshness_days)).isoformat(),
    }
    res = supabase.table("niche_insights").upsert(payload, on_conflict="niche").execute()
    return res.data[0] if res.data else payload


def _is_niche_insight_fresh(insight_row: Dict[str, Any]) -> bool:
    expires_at_raw = insight_row.get("expires_at")
    if not isinstance(expires_at_raw, str):
        return False
    try:
        expires_at = datetime.fromisoformat(expires_at_raw.replace("Z", "+00:00"))
        return datetime.now(timezone.utc) < expires_at
    except Exception:
        return False


def run_niche_research_skill(niche: str, label: str = "", force_refresh: bool = False) -> Dict[str, Any]:
    """Investiga tendencias y mejores prácticas actuales en Instagram para el nicho
    indicado mediante búsqueda web real."""
    if not niche:
        return {"brief": "", "fresh": False, "regenerated": False}

    existing = get_niche_insight(niche)
    if existing and not force_refresh and _is_niche_insight_fresh(existing):
        return {"brief": existing["brief"], "fresh": True, "regenerated": False}

    search_label = label or niche.replace("_", " ")
    prompt = (
        f"Busca en la web información actual sobre tendencias, formatos y mejores prácticas "
        f"de contenido en Instagram para cuentas de {search_label}. Resume en 2-3 frases en español, "
        "concreto y accionable, qué tipo de contenido, formato o timing está funcionando mejor "
        "ahora mismo para este nicho."
    )

    try:
        result = _run_search_grounding(prompt)
    except Exception as e:
        logger.error(f"Error ejecutando skill de investigación de nicho '{niche}': {e}")
        return {
            "brief": "No pude completar la investigación de tendencias esta vez.",
            "fresh": False,
            "regenerated": False,
        }

    save_niche_insight(niche, result["brief"], result["sources"])

    return {"brief": result["brief"], "fresh": False, "regenerated": True}


def run_niche_research_for_account(account_id: int, force_refresh: bool = False) -> Dict[str, Any]:
    """Resuelve el nicho de la cuenta a partir de sector, purpose y target_audience,
    e investiga sus tendencias. Devuelve {'niche': str, 'brief': str}."""
    supabase = get_supabase_admin_client()
    res = supabase.table("instagram_accounts").select("sector,purpose,target_audience").eq("id", account_id).execute()
    account = res.data[0] if res.data else {}

    niche_key = build_niche_key(account)
    if not niche_key:
        return {"niche": "", "brief": ""}

    parts = [account.get("sector"), account.get("purpose"), account.get("target_audience")]
    label = " ".join(str(p).strip() for p in parts if p and str(p).strip())

    skill_result = run_niche_research_skill(niche_key, label=label, force_refresh=force_refresh)
    return {"niche": niche_key, "brief": skill_result.get("brief", "")}
