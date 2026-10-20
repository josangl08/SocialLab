import logging
import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID, uuid4
from database.supabase_client import get_supabase_admin_client
from services.gemini_service import (
    summarize_corrections as _summarize_corrections_llm,
    get_gemini_client,
    DECISION_GEMINI_MODELS,
)
from utils.timezones import utc_now_naive

logger = logging.getLogger(__name__)

_RULE_TYPES = {"tone", "frequency", "format", "topic", "brand_safety", "other"}

def load_session_history(account_id: int, session_id: UUID) -> List[Dict[str, Any]]:
    """Carga los turnos previos de una sesión de agente desde agent_memory."""
    supabase = get_supabase_admin_client()
    response = supabase.table("agent_memory")\
        .select("*")\
        .eq("account_id", account_id)\
        .eq("session_id", str(session_id))\
        .order("id", desc=False)\
        .execute()
    return response.data or []

def append_turn(
    account_id: int,
    session_id: UUID,
    role: str,
    content: Optional[Any] = None,
    tool_name: Optional[str] = None,
    tool_args: Optional[Dict[str, Any]] = None,
    tool_result: Optional[Any] = None
) -> Dict[str, Any]:
    """Guarda un turno en la base de datos agent_memory."""
    supabase = get_supabase_admin_client()
    turn_data = {
        "account_id": account_id,
        "session_id": str(session_id),
        "role": role,
        "content": content,
        "tool_name": tool_name,
        "tool_args": tool_args,
        "tool_result": tool_result
    }
    response = supabase.table("agent_memory").insert(turn_data).execute()
    if response.data and len(response.data) > 0:
        return response.data[0]
    return {}


def append_correction(
    account_id: int,
    edit_type: str,
    user_message: str,
    resolution: str
) -> Dict[str, Any]:
    """Guarda una corrección resuelta de run_edit_session como una fila de memoria de
    largo plazo — a diferencia de append_turn, esto no forma parte del historial de
    una sesión de edición concreta, es la señal que summarize_recent_corrections lee
    para construir el resumen inyectado en futuras sesiones semanales."""
    correction_row = append_turn(
        account_id=account_id,
        session_id=uuid4(),
        role="correction",
        content={
            "edit_type": edit_type,
            "user_message": user_message,
            "resolution": resolution,
        }
    )
    try:
        extract_rule_from_correction(account_id, correction_row)
    except Exception:
        logger.warning("extract_rule_from_correction call failed for account_id=%s", account_id, exc_info=True)
    return correction_row


def get_correction_count_since(account_id: int, since: Optional[datetime]) -> int:
    """Cuenta correcciones nuevas desde la última vez que se recalculó el resumen —
    chequeo barato para evitar gastar una llamada a Gemini cuando no hay nada nuevo."""
    supabase = get_supabase_admin_client()
    query = supabase.table("agent_memory").select("id", count="exact").eq("account_id", account_id).eq("role", "correction")
    if since is not None:
        query = query.gt("created_at", since.isoformat())
    response = query.execute()
    return response.count if isinstance(response.count, int) else 0


async def summarize_recent_corrections(account_id: int, limit: int = 20) -> Optional[str]:
    """Condensa las últimas correcciones del usuario en 2-4 frases vía Gemini. Devuelve
    None si no hay ninguna corrección todavía, para que el caller pueda saltarse el
    resumen sin gastar una llamada."""
    supabase = get_supabase_admin_client()
    response = supabase.table("agent_memory")\
        .select("*")\
        .eq("account_id", account_id)\
        .eq("role", "correction")\
        .order("id", desc=True)\
        .limit(limit)\
        .execute()
    rows = list(reversed(response.data or []))
    if not rows:
        return None
    return await _summarize_corrections_llm(rows)


def get_active_brand_rules(account_id: int) -> List[Dict[str, Any]]:
    """Obtiene las reglas de marca activas para una cuenta."""
    supabase = get_supabase_admin_client()
    response = supabase.table("account_brand_rules")\
        .select("*")\
        .eq("account_id", account_id)\
        .eq("is_active", True)\
        .execute()
    return response.data or []


def _humanize_rule_type(rule_type: str) -> str:
    return rule_type.replace("_", " ").title()


def _generate_decision_rationale(
    decision_type: str,
    tool_args: Optional[Dict[str, Any]],
    active_rules: List[Dict[str, Any]],
) -> Tuple[float, str]:
    """Pide a Gemini un confidence_score (0-1) y un rationale de una frase para una
    decisión de Hermes. Best-effort: cualquier fallo o respuesta no parseable cae a
    (0.5, rationale genérico) — nunca debe bloquear el registro de la decisión."""
    try:
        rules_text = "; ".join(r["rule_text"] for r in active_rules if r.get("rule_text")) or "ninguna"
        prompt = (
            f"Un agente de IA (Hermes) acaba de ejecutar la acción '{decision_type}' con "
            f"estos argumentos: {tool_args or {}}. Reglas de marca activas de la cuenta en "
            f"ese momento: {rules_text}.\n\n"
            "Responde EXACTAMENTE en este formato de dos líneas:\n"
            "CONFIDENCE: <número entre 0 y 1>\n"
            "RATIONALE: <una frase en español explicando por qué esta decisión encaja con "
            "el perfil y las reglas de la cuenta>"
        )
        client = get_gemini_client()
        response = client.models.generate_content(model=DECISION_GEMINI_MODELS[0], contents=prompt)
        text = (response.text or "").strip()

        confidence_match = re.search(r"CONFIDENCE:\s*([0-9]*\.?[0-9]+)", text)
        rationale_match = re.search(r"RATIONALE:\s*(.+)", text, re.DOTALL)
        confidence = max(0.0, min(1.0, float(confidence_match.group(1)))) if confidence_match else 0.5
        rationale = rationale_match.group(1).strip() if rationale_match else (
            text or "Decisión registrada sin rationale detallado."
        )
        return confidence, rationale
    except Exception:
        return 0.5, f"Decisión '{decision_type}' registrada automáticamente (rationale no disponible)."


def record_agent_decision(
    account_id: int,
    session_id: Optional[UUID],
    decision_type: str,
    tool_args: Optional[Dict[str, Any]] = None,
    tool_result: Optional[Any] = None,
    related_post_id: Optional[int] = None,
    related_proposal_id: Optional[str] = None,
    campaign_id: Optional[str] = None,
    status: str = "active",
    rationale: Optional[str] = None,
    confidence_score: Optional[float] = None,
) -> Dict[str, Any]:
    """Registra una decisión tomada por el agente Hermes con su confidence_score y
    rationale (best-effort vía Gemini). Nunca propaga una excepción — un fallo aquí
    no debe abortar la sesión de Hermes que originó la decisión (design.md).

    `campaign_id` enlaza la decisión a la campaña mensual consultada en la sesión.
    Para decisiones `status="suggested"` (sugerencias de horario/mix), el caller pasa
    su propio `rationale`/`confidence_score` y se salta la llamada a Gemini."""
    try:
        active_rules = get_active_brand_rules(account_id)
        applied_rule_ids = [r["id"] for r in active_rules if r.get("id") is not None]
        # Dedupe labels: two active rules of the same rule_type (a conflict pair)
        # would otherwise repeat the label and render as duplicate chips in the UI.
        # applied_rule_ids keeps both so the conflict detail is still available.
        applied_rule_labels = list(dict.fromkeys(
            _humanize_rule_type(r["rule_type"]) for r in active_rules if r.get("rule_type")
        ))

        if rationale is None and confidence_score is None:
            confidence_score, rationale = _generate_decision_rationale(decision_type, tool_args, active_rules)

        decision_data = {
            "account_id": account_id,
            "session_id": str(session_id) if session_id else None,
            "decision_type": decision_type,
            "related_post_id": related_post_id,
            "related_proposal_id": related_proposal_id,
            "campaign_id": campaign_id,
            "status": status,
            "applied_rule_ids": applied_rule_ids,
            "applied_rule_labels": applied_rule_labels,
            "confidence_score": confidence_score if confidence_score is not None else 0.5,
            "rationale": rationale,
            "tool_args": tool_args,
            "tool_result": tool_result if isinstance(tool_result, dict) else None,
        }
        supabase = get_supabase_admin_client()
        response = supabase.table("agent_decisions").insert(decision_data).execute()
        return response.data[0] if response.data else {}
    except Exception:
        logger.warning("record_agent_decision failed for account_id=%s", account_id, exc_info=True)
        return {}


def _classify_correction(
    user_message: str,
    resolution: str,
    existing_rules: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Dict[str, str]]:
    """Llama a Gemini para clasificar una corrección en rule_type + rule_text +
    relation, o None si no expresa una preferencia de marca reutilizable (p. ej. un
    ajuste puntual de horario). `relation` (new | reinforce | conflict) describe la
    corrección respecto a las reglas activas del MISMO rule_type que se le pasan en
    `existing_rules`. Best-effort: cualquier fallo o respuesta no parseable cae a
    None."""
    try:
        existing_rules = existing_rules or []
        rules_block = "\n".join(
            f"- [{r.get('rule_type')}] {r.get('rule_text')}"
            for r in existing_rules if r.get("rule_text")
        ) or "ninguna"
        prompt = (
            "Un usuario corrigió una decisión de un agente de contenido para Instagram. "
            f"Mensaje del usuario: \"{user_message}\". Resolución aplicada: \"{resolution}\".\n\n"
            f"Reglas de marca ya activas de esta cuenta:\n{rules_block}\n\n"
            "1) ¿Esta corrección expresa una preferencia de marca reutilizable (no un ajuste "
            "puntual de una sola vez, como cambiar la hora de un post concreto)? Si no lo es, "
            "responde exactamente: NONE\n"
            "2) Si sí lo es, responde EXACTAMENTE estas tres líneas:\n"
            "RULE_TYPE: <uno de tone|frequency|format|topic|brand_safety|other>\n"
            "RULE_TEXT: <una frase corta y accionable con la regla>\n"
            "RELATION: <new|reinforce|conflict>\n"
            "   - reinforce = dice lo mismo (más fuerte o específico) que una regla activa "
            "del MISMO rule_type.\n"
            "   - conflict = contradice una regla activa del MISMO rule_type.\n"
            "   - new = no hay regla activa de ese rule_type, o trata otro aspecto."
        )
        client = get_gemini_client()
        response = client.models.generate_content(model=DECISION_GEMINI_MODELS[0], contents=prompt)
        text = (response.text or "").strip()
        if text.upper().startswith("NONE"):
            return None

        type_match = re.search(r"RULE_TYPE:\s*(\w+)", text)
        text_match = re.search(r"RULE_TEXT:\s*(.+)", text)
        if not type_match or not text_match:
            return None

        rule_type = type_match.group(1).strip().lower()
        if rule_type not in _RULE_TYPES:
            return None
        rule_text = text_match.group(1).strip()

        relation_match = re.search(r"RELATION:\s*(new|reinforce|conflict)", text, re.IGNORECASE)
        relation = relation_match.group(1).lower() if relation_match else "new"
        # Sin una regla activa del mismo rule_type no hay nada que reforzar ni
        # contradecir — fuerza "new" pase lo que diga Gemini.
        if not any(r.get("rule_type") == rule_type for r in existing_rules):
            relation = "new"
        return {"rule_type": rule_type, "rule_text": rule_text, "relation": relation}
    except Exception:
        return None


def extract_rule_from_correction(account_id: int, correction_row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Clasifica una corrección del usuario en una regla de marca estructurada y la
    persiste en account_brand_rules, versionando en vez de mutar en sitio:
      - new       → INSERT como fila activa nueva.
      - reinforce → INSERT nueva versión (previous_version_id = regla reforzada); la
                    versión anterior pasa a is_active=false pero sigue consultable como
                    historial.
      - conflict  → INSERT nueva versión (conflicts_with_id = regla contradicha); ambas
                    filas quedan activas — el sistema no elige un ganador.
    Nunca propaga una excepción: llamada desde append_correction, un fallo aquí no
    debe romper el registro de la corrección misma."""
    try:
        content = correction_row.get("content") or {}
        user_message = content.get("user_message", "")
        resolution = content.get("resolution", "")

        active_rules = get_active_brand_rules(account_id)
        classification = _classify_correction(user_message, resolution, existing_rules=active_rules)
        if classification is None:
            return None

        rule_type = classification["rule_type"]
        rule_text = classification["rule_text"]
        relation = classification.get("relation", "new")

        # Sin embeddings (fuera de alcance v1), "mismo rule_type" se trata como el mismo
        # concepto de marca; la fila más aplicada es el proxy de "la que Hermes más usa".
        same_type = [r for r in active_rules if r.get("rule_type") == rule_type]
        target = max(same_type, key=lambda r: r.get("times_applied", 0)) if same_type else None

        supabase = get_supabase_admin_client()
        base_insert = {
            "account_id": account_id,
            "rule_type": rule_type,
            "rule_text": rule_text,
            "source_correction_id": correction_row.get("id"),
        }

        if target is None or relation == "new":
            response = supabase.table("account_brand_rules").insert(base_insert).execute()
            return response.data[0] if response.data else None

        if relation == "conflict":
            insert_data = {
                **base_insert,
                "conflicts_with_id": target["id"],
                "confidence": float(target.get("confidence", 1.0)),
            }
            response = supabase.table("account_brand_rules").insert(insert_data).execute()
            return response.data[0] if response.data else None

        # relation == "reinforce": nueva versión enlazada hacia atrás; la anterior se
        # desactiva pero no se borra. Misma aritmética que la vieja mutación en sitio.
        insert_data = {
            **base_insert,
            "previous_version_id": target["id"],
            "confidence": min(1.0, float(target.get("confidence", 1.0)) + 0.1),
            "times_applied": target.get("times_applied", 0) + 1,
        }
        response = supabase.table("account_brand_rules").insert(insert_data).execute()
        supabase.table("account_brand_rules").update(
            {"is_active": False, "updated_at": utc_now_naive().isoformat()}
        ).eq("id", target["id"]).execute()
        return response.data[0] if response.data else {**target, **insert_data}
    except Exception:
        logger.warning("extract_rule_from_correction failed for account_id=%s", account_id, exc_info=True)
        return None

