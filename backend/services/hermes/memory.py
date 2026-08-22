from datetime import datetime
from typing import List, Dict, Any, Optional
from uuid import UUID, uuid4
from database.supabase_client import get_supabase_admin_client
from services.gemini_service import summarize_corrections as _summarize_corrections_llm

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
    return append_turn(
        account_id=account_id,
        session_id=uuid4(),
        role="correction",
        content={
            "edit_type": edit_type,
            "user_message": user_message,
            "resolution": resolution,
        }
    )


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
