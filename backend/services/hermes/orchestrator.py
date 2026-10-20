import os
import re
import uuid
import inspect
import logging
import time
from datetime import datetime
from typing import Optional, Dict, Any, List, Callable
from pydantic import BaseModel
import httpx
from google.genai import types, errors
from database.supabase_client import get_supabase_admin_client
from services.hermes.tool_bridge import ToolBridge
from services.hermes.memory import (
    load_session_history,
    append_turn,
    append_correction,
    get_correction_count_since,
    summarize_recent_corrections,
    record_agent_decision,
)
from services.hermes.prompts import get_system_prompt, get_edit_prompt
from services.gemini_service import PREFERRED_GEMINI_MODELS, EDIT_GEMINI_MODELS, get_gemini_client
from mcp.drive_server import mcp as drive_mcp
from mcp.supabase_server import mcp as supabase_mcp
from mcp.vision_server import mcp as vision_mcp
from mcp.analytics_server import mcp as analytics_mcp
from mcp.skills_server import mcp as skills_mcp
from services.hermes.skills import run_niche_research_for_account, run_visual_performance_skill
from utils.timezones import utc_now_naive

logger = logging.getLogger(__name__)


def _is_transient_gemini_error(e: BaseException) -> bool:
    """Classifies whether an exception from Gemini API is transient (quota exceeded 429,
    server error 5xx, or network/read timeout) and eligible for model fallback.
    Any other error (400, 403, ...) would fail the same way on every model."""
    if isinstance(e, (errors.ServerError, httpx.TimeoutException)):
        return True
    return isinstance(e, errors.ClientError) and e.code == 429


class _FallbackGenerativeModel:
    """Wraps client.models.generate_content, retrying with the next name in
    PREFERRED_GEMINI_MODELS on a transient error (429 quota, any 5xx, or a timeout)
    — e.g. when the preferred (pro) model has no quota or Google's server is
    unavailable but the fallback (flash) one answers. Each call is bounded by
    HERMES_GEMINI_TIMEOUT_S (default 90 s). Once a model name succeeds, later turns
    start from it and only move further down the list — never back up to a
    higher-tier model already discarded."""

    def __init__(self, system_instruction: str, tools: Any, model_names: Optional[List[str]] = None):
        self._system_instruction = system_instruction
        # google.genai's GenerateContentConfig.tools expects Tool objects, not bare
        # FunctionDeclarations — the old google.generativeai SDK auto-wrapped these.
        self._tools = [types.Tool(function_declarations=tools)] if tools else None
        self._model_names = model_names or PREFERRED_GEMINI_MODELS
        self._resolved_name: Optional[str] = None
        self._timeout_ms = int(float(os.environ.get("HERMES_GEMINI_TIMEOUT_S", "90")) * 1000)

    def generate_content(self, history):
        start = self._model_names.index(self._resolved_name) if self._resolved_name else 0
        candidates = self._model_names[start:]
        last_error: Optional[Exception] = None
        client = get_gemini_client()
        config = types.GenerateContentConfig(
            system_instruction=self._system_instruction,
            tools=self._tools,
            # Keep manual control of the turn loop (tool dispatch via ToolBridge) —
            # the SDK's automatic function calling would short-circuit that.
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            http_options=types.HttpOptions(timeout=self._timeout_ms),
        )
        for i, name in enumerate(candidates):
            t0 = time.monotonic()
            try:
                response = client.models.generate_content(model=name, contents=history, config=config)
            except Exception as e:
                if not _is_transient_gemini_error(e):
                    raise
                last_error = e
                next_name = candidates[i + 1] if i + 1 < len(candidates) else None
                logger.warning(
                    "hermes_gemini_fallback model=%s cause=%s latency_ms=%d next=%s",
                    name, type(e).__name__, int((time.monotonic() - t0) * 1000), next_name,
                )
                continue
            logger.info(
                "hermes_gemini_ok model=%s latency_ms=%d",
                name, int((time.monotonic() - t0) * 1000),
            )
            self._resolved_name = name
            return response
        raise last_error

# Tool names whose dispatch results get recorded as agent_decisions (design.md
# §Architecture Decisions #2) — the real content-creation calls, not every tool in
# the weekly session's 13-tool set.
_DECISION_TOOL_NAMES = {"supabase_create_post", "supabase_create_proposal"}


class HermesSessionResult(BaseModel):
    images_scanned: int = 0
    images_analyzed: int = 0
    posts_drafted: int = 0
    proposal_id: Optional[str] = None
    error: Optional[str] = None


class EditSessionResult(BaseModel):
    resolved: bool
    message: str

async def _emit_progress(on_progress: Optional[Callable], event: Dict[str, Any]) -> None:
    """Invokes on_progress with a single progress event, awaiting it if it's a
    coroutine function — lets callers pass either a plain callback (e.g. queueing
    into an asyncio.Queue for NDJSON streaming) or an async one."""
    if on_progress is None:
        return
    if inspect.iscoroutinefunction(on_progress):
        await on_progress(event)
    else:
        on_progress(event)


def _safe_response_text(response: Any) -> str:
    """google.genai's response.text raises ValueError (not just returns None) when
    any part of the response isn't a plain text part — e.g. a function_call-only
    turn, which is the normal case most turns in this loop. Swallow that and
    treat it the same as "no text this turn"."""
    try:
        return response.text or ""
    except ValueError:
        return ""


async def _dispatch_turn(
    response: Any,
    bridge: ToolBridge,
    account_id: int,
    on_progress: Optional[Callable] = None,
    campaign_focus: str = "",
    exclude_used_media: bool = False,
) -> tuple:
    """Parses a Gemini response into function_calls/text, dispatches each function call
    through the ToolBridge, and builds the response Part list for the next turn's
    history. Shared by run_session and run_edit_session — a single turn is processed
    identically in both; only the stopping condition and result aggregation differ.
    """
    function_calls = []
    model_parts = []
    if response.candidates and response.candidates[0].content:
        for part in response.candidates[0].content.parts:
            # Re-send the original Part as-is (not just its .function_call) — newer
            # "thinking" models attach a thought_signature to the Part alongside
            # function_call, and the API rejects a later turn that replays the bare
            # FunctionCall without it ("Function call is missing a thought_signature").
            model_parts.append(part)
            if getattr(part, "function_call", None):
                function_calls.append(part.function_call)

    tool_responses = []
    dispatched = []
    for fc in function_calls:
        tool_name = fc.name
        # google.genai's FunctionCall.args is already a plain native dict (pydantic
        # model, not the old proto-plus MapComposite/RepeatedComposite that needed
        # a recursive to_dict() conversion) — safe to use directly.
        tool_args = fc.args or {}

        await _emit_progress(on_progress, {"type": "tool_call", "tool": tool_name})

        try:
            result = await bridge.dispatch(tool_name, tool_args, account_id)
            ok = not (isinstance(result, dict) and "error" in result)
        except Exception as e:
            result = {"error": str(e)}
            ok = False

        # Deduplicación y ranking de archivos de Drive
        if tool_name == "drive_list_files" and isinstance(result, list):
            if exclude_used_media:
                count_from_drive = len(result)
                result = _filter_unavailable_drive_files(result, account_id)
                if not result:
                    _log_empty_drive_result(count_from_drive, account_id)
            result = _rank_drive_files(result, campaign_focus, account_id)

        dispatched.append((tool_name, tool_args, result))

        await _emit_progress(on_progress, {"type": "tool_result", "tool": tool_name, "ok": ok})

        try:
            part = types.Part.from_function_response(
                name=tool_name,
                response={"result": result}
            )
        except Exception:
            part = {"function_response": {"name": tool_name, "response": {"result": result}}}
        tool_responses.append(part)

    return function_calls, model_parts, tool_responses, dispatched


def _correct_content_type_mix(account_id: int, post_ids: List[int]) -> None:
    """Deterministic post-session correction: if the number of posts created this
    session matches the account's configured content_type_mix quota exactly, correct
    each post's post_type so the distribution matches that quota — same rule as
    HEAD's _validate_content_type_mix (design.md §Architecture Decisions #4), now
    applied as an UPDATE on already-persisted posts instead of in-memory slots."""
    if not post_ids:
        return

    supabase = get_supabase_admin_client()
    account_res = supabase.table("instagram_accounts").select("content_type_mix").eq("id", account_id).execute()
    raw_mix = (account_res.data[0].get("content_type_mix") if account_res.data else None) or {}
    quota = {k: v for k, v in raw_mix.items() if isinstance(v, int) and v > 0}
    if sum(quota.values()) != len(post_ids):
        return

    posts_res = supabase.table("posts").select("id, post_type").in_("id", post_ids).execute()
    posts_by_id = {p["id"]: p.get("post_type") for p in (posts_res.data or [])}

    remaining = dict(quota)
    for post_id in post_ids:
        current_type = posts_by_id.get(post_id)
        if remaining.get(current_type, 0) > 0:
            remaining[current_type] -= 1
            continue
        new_type = next(t for t, count in remaining.items() if count > 0)
        remaining[new_type] -= 1
        supabase.table("posts").update({"post_type": new_type}).eq("id", post_id).execute()


_WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _backfill_slot_media(proposal_id: Optional[str], created_posts: List[Dict[str, Any]]) -> None:
    """Deterministic post-session safety net: fills any slot missing post_id/image_id
    by matching it to a post created this session with the same scheduled weekday.
    Never overwrites a value Hermes already provided — the prompt is the primary
    mechanism (see design.md/prompts.py steps 6-7), this only catches what it misses."""
    if not proposal_id or not created_posts:
        return

    supabase = get_supabase_admin_client()
    res = supabase.table("content_proposals").select("slots").eq("id", proposal_id).execute()
    if not res.data:
        return
    slots = res.data[0].get("slots") or []

    posts_by_day: Dict[str, Dict[str, Any]] = {}
    for post in created_posts:
        sched = post.get("scheduled_publish_time")
        if not sched:
            continue
        try:
            weekday = _WEEKDAY_NAMES[datetime.fromisoformat(sched.replace("Z", "+00:00")).weekday()]
        except ValueError:
            continue
        posts_by_day[weekday] = post

    changed = False
    for slot in slots:
        match = posts_by_day.get(slot.get("day"))
        if not match:
            continue
        if slot.get("post_id") is None:
            slot["post_id"] = match["post_id"]
            changed = True
        if slot.get("image_id") is None and match.get("drive_file_id"):
            slot["image_id"] = match["drive_file_id"]
            changed = True

    if changed:
        supabase.table("content_proposals").update({"slots": slots}).eq("id", proposal_id).execute()


def _compress_history(history: List[Dict[str, Any]], keep_last: int = 8) -> List[Dict[str, Any]]:
    """Caps how much in-session turn history gets resent to Gemini every turn, once
    a session runs long enough for it to matter. At the point this is called
    (right before model.generate_content), history always looks like
    [initial_user_trigger] + N complete (model, user) pairs — the "user" entries
    are function-response turns (see run_session/run_edit_session), so slicing by
    whole pairs preserves strict role alternation. Keeps the initial trigger and
    the last `keep_last` pairs verbatim; older pairs collapse into one synthetic
    marker pair instead of a single entry, for the same alternation reason."""
    if not history:
        return history
    body = history[1:]
    if len(body) <= keep_last * 2:
        return history

    tail = body[-(keep_last * 2):]
    omitted_pairs = (len(body) - len(tail)) // 2
    marker_model = {"role": "model", "parts": [{"text": f"[Resumen: se omiten {omitted_pairs} pasos anteriores de esta sesión.]"}]}
    marker_user = {"role": "user", "parts": [{"text": f"[...{omitted_pairs} turnos anteriores omitidos...]"}]}
    return [history[0], marker_model, marker_user] + tail


async def _maybe_refresh_memory_summary(account_id: int) -> None:
    """Recomputes instagram_accounts.agent_memory_summary if there are correction
    rows newer than the last computed summary — keeps run_session's prompt fresh
    without paying for a Gemini summarization call on every single weekly run when
    nothing has changed since the last one."""
    supabase = get_supabase_admin_client()
    acc_res = supabase.table("instagram_accounts").select("agent_memory_summary_updated_at").eq("id", account_id).execute()
    rows = acc_res.data if isinstance(acc_res.data, list) else []
    if not rows:
        return
    updated_at_raw = rows[0].get("agent_memory_summary_updated_at")
    since = datetime.fromisoformat(updated_at_raw.replace("Z", "+00:00")) if isinstance(updated_at_raw, str) else None

    if get_correction_count_since(account_id, since) == 0:
        return

    summary = await summarize_recent_corrections(account_id)
    if summary is None:
        return
    supabase.table("instagram_accounts").update({
        "agent_memory_summary": summary,
        "agent_memory_summary_updated_at": utc_now_naive().isoformat(),
    }).eq("id", account_id).execute()


def _drive_file_id(f: Any) -> Optional[str]:
    """Extrae el id de Drive de un dict de archivo."""
    if not isinstance(f, dict):
        return None
    return f.get("id") or f.get("file_id") or f.get("drive_file_id")


def _filter_unavailable_drive_files(files: List[Any], account_id: int) -> List[Any]:
    """Filtra imágenes de Drive ya comprometidas en posts (draft/scheduled/published)
    o en slots de propuestas (pending_approval/approved). Nunca lanza excepción."""
    try:
        if not isinstance(files, list):
            return files
        supabase = get_supabase_admin_client()

        # Posts comprometidos
        post_rows = supabase.table("posts")\
            .select("drive_file_id")\
            .eq("instagram_account_id", account_id)\
            .in_("status", ["draft", "scheduled", "published"])\
            .not_.is_("drive_file_id", "null")\
            .execute().data or []
        used_ids = {r["drive_file_id"] for r in post_rows if r.get("drive_file_id")}

        # Propuestas activas (pending/approved)
        prop_rows = supabase.table("content_proposals")\
            .select("slots")\
            .eq("account_id", str(account_id))\
            .in_("status", ["pending_approval", "approved"])\
            .execute().data or []
        for prop in prop_rows:
            slots = prop.get("slots") or []
            for slot in slots:
                if isinstance(slot, dict) and slot.get("image_id"):
                    used_ids.add(slot["image_id"])

        return [f for f in files if _drive_file_id(f) not in used_ids]
    except Exception as e:
        logger.warning(f"Error filtering unavailable drive files for account {account_id}: {e}")
        return files


def _log_empty_drive_result(count_from_drive: int, account_id: int) -> None:
    """Se llama cuando, en una sesión de planificación, la lista de Drive queda vacía
    tras el filtro de deduplicación. Distingue dos causas para que el operador pueda
    diagnosticar por qué Hermes no propuso nada esta semana:
      - no había imágenes en la carpeta de Drive
      - había imágenes, pero todas ya están comprometidas en posts o propuestas activas
    No cambia el flujo: el modelo termina limpio con una lista vacía en cualquier caso."""
    if count_from_drive == 0:
        logger.info("hermes_drive_empty=no_images_in_drive account_id=%s", account_id)
    else:
        logger.info(
            "hermes_drive_empty=all_images_already_used account_id=%s filtered_out=%s",
            account_id,
            count_from_drive,
        )


def _rank_drive_files(files: List[Any], focus_text: Optional[str], account_id: int) -> List[Any]:
    """Reordena una lista de archivos de Drive combinando el solapamiento léxico con el foco
    de campaña y el aesthetic_score (1-10) del análisis visual. Orden estable. Nunca lanza."""
    try:
        if not isinstance(files, list) or len(files) < 2:
            return files
        supabase = get_supabase_admin_client()
        rows = supabase.table("visual_analyses")\
            .select("drive_file_id, gemini_description")\
            .eq("account_id", account_id)\
            .execute().data or []

        info_by_file: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            desc = row.get("gemini_description") or {}
            blob = " ".join(
                str(desc.get(k, "")) for k in ("theme", "raw_description", "mood")
            ).lower()
            aesthetic = desc.get("aesthetic_score", 5)
            try:
                aesthetic_score = int(aesthetic)
            except (ValueError, TypeError):
                aesthetic_score = 5
            info_by_file[row.get("drive_file_id")] = {
                "blob": blob,
                "aesthetic_score": aesthetic_score,
            }

        focus_tokens = set(re.findall(r"\w{4,}", focus_text.lower())) if focus_text else set()

        def _score(f: Any) -> int:
            file_id = _drive_file_id(f)
            info = info_by_file.get(file_id, {"blob": "", "aesthetic_score": 5})
            blob = info.get("blob", "")
            overlap = sum(1 for t in focus_tokens if t in blob) if blob and focus_tokens else 0
            return (overlap * 2) + info.get("aesthetic_score", 5)

        return [f for _, f in sorted(enumerate(files), key=lambda pair: (-_score(pair[1]), pair[0]))]
    except Exception:
        return files


_rank_drive_files_by_focus = _rank_drive_files


def _schedule_disagreement(configured_best_times: List[Any], empirical: Dict[str, Any]) -> Optional[str]:
    """Decide si los horarios reales del histórico difieren *de forma significativa*
    de los que el usuario configuró a mano, y devuelve la razón concreta (para el
    rationale de la sugerencia) o None si no hay discrepancia relevante.

    `empirical` es el dict de AnalyticsService.get_empirical_scheduling_data:
    {has_data, top_times: ["HH:00", ...], best_times_by_weekday, summary_text}.
    La configuración manual del usuario NO se toca — esto solo alimenta una
    sugerencia visible en el timeline.

    Criterio: se sugiere solo cuando NINGUNA de las horas top del histórico cae a
    ±1h de alguna hora configurada — así "09:00 vs 10:00" no dispara nada, pero
    "mañanas configuradas vs. histórico que rinde de noche" sí. Barra alta a
    propósito: pocas sugerencias, todas con señal real."""
    def _hour(hhmm: Any) -> Optional[int]:
        try:
            return int(str(hhmm).split(":")[0])
        except (ValueError, IndexError):
            return None

    configured_hours = {h for h in (_hour(t) for t in configured_best_times) if h is not None}
    empirical_hours = [h for h in (_hour(t) for t in empirical.get("top_times", [])) if h is not None]
    if not configured_hours or not empirical_hours:
        return None

    if any(min(abs(eh - ch) for ch in configured_hours) <= 1 for eh in empirical_hours):
        return None

    configured_label = ", ".join(str(t) for t in configured_best_times)
    empirical_label = empirical.get("summary_text") or ", ".join(
        f"{h:02d}:00" for h in empirical_hours
    )
    return (
        f"Tus horarios configurados ({configured_label}) no coinciden con las mejores "
        f"horas de tu histórico real ({empirical_label}). Considera revisarlos en "
        "Ajustes. Esta sesión respetó tu configuración sin cambios."
    )


def _maybe_record_schedule_mix_suggestions(
    account_id: int,
    session_id: uuid.UUID,
    campaign_id: Optional[str],
    model: Any,
    created_post_types: List[str],
) -> None:
    """Fase 5: al final de la sesión, si los datos empíricos (horario) o el propio
    razonamiento de Hermes (mezcla de tipos) sugieren algo distinto a lo que el
    usuario configuró a mano, lo registra como una decisión `status="suggested"` con
    su rationale. Best-effort y no bloqueante: un fallo aquí nunca cambia el
    HermesSessionResult ni la programación/mezcla real de la sesión (que sigue
    respetando la config manual sin cambios)."""
    try:
        supabase = get_supabase_admin_client()
        cfg_res = supabase.table("instagram_accounts")\
            .select("best_times, content_type_mix")\
            .eq("id", account_id).execute()
        cfg = cfg_res.data[0] if cfg_res.data else {}
        best_times = cfg.get("best_times") or []
        raw_mix = cfg.get("content_type_mix") or {}
        mix_quota = {k: v for k, v in raw_mix.items() if isinstance(v, int) and v > 0}

        # --- Horario: fuente empírica determinista ---
        if best_times:
            from services.analytics.analytics_service import AnalyticsService
            empirical = AnalyticsService(db_client=supabase).get_empirical_scheduling_data(account_id)
            if empirical.get("has_data"):
                reason = _schedule_disagreement(best_times, empirical)
                if reason:
                    record_agent_decision(
                        account_id=account_id,
                        session_id=session_id,
                        decision_type="suggest_schedule_change",
                        status="suggested",
                        campaign_id=campaign_id,
                        confidence_score=0.5,
                        rationale=reason,
                        tool_args={
                            "configured_best_times": best_times,
                            "suggested_best_times": empirical.get("top_times") or [],
                            "empirical": empirical,
                        },
                    )

        # --- Mezcla de tipos: juicio del propio modelo (no hay fuente empírica) ---
        if mix_quota and created_post_types:
            actual = {t: created_post_types.count(t) for t in set(created_post_types) if t}
            # The suggested quota keeps every configured content type (0 for the
            # ones this week's content didn't use) so it's a drop-in replacement.
            suggested_mix = {**{k: 0 for k in mix_quota}, **actual}
            if actual and actual != mix_quota:
                prompt = (
                    f"Mezcla de tipos de contenido configurada por el usuario: {mix_quota}. "
                    f"Mezcla que encajaba mejor con el contenido real de esta semana: {actual}. "
                    "Si de verdad crees que la configurada debería revisarse, responde "
                    "'SUGGEST_MIX: <razón breve y concreta>'. Si la diferencia es menor o "
                    "circunstancial, responde 'NONE'."
                )
                text = _safe_response_text(
                    model.generate_content([{"role": "user", "parts": [{"text": prompt}]}])
                )
                match = re.search(r"SUGGEST_MIX:\s*(.+)", text, re.DOTALL)
                if match:
                    record_agent_decision(
                        account_id=account_id,
                        session_id=session_id,
                        decision_type="suggest_mix_change",
                        status="suggested",
                        campaign_id=campaign_id,
                        confidence_score=0.5,
                        rationale=match.group(1).strip()[:500],
                        tool_args={
                            "configured_mix": mix_quota,
                            "session_mix": actual,
                            "suggested_content_type_mix": suggested_mix,
                        },
                    )
    except Exception:
        logger.warning(
            "end-of-session suggestion generation failed for account_id=%s", account_id, exc_info=True
        )


async def run_session(account_id: int) -> HermesSessionResult:
    session_id = uuid.uuid4()
    max_turns = int(os.environ.get("HERMES_MAX_TURNS", "12"))

    # 1. Initialize tool bridge with MCP instances
    bridge = ToolBridge([drive_mcp, supabase_mcp, vision_mcp, analytics_mcp, skills_mcp])
    declarations = await bridge.discover_tools()

    # Refresh the persistent-memory summary (if stale) before building the prompt,
    # so this same session benefits from the latest corrections immediately.
    await _maybe_refresh_memory_summary(account_id)

    # Auto-inyección de inteligencia previa (nicho y rendimiento visual)
    niche_brief = None
    try:
        niche_res = run_niche_research_for_account(account_id)
        if isinstance(niche_res, dict):
            niche_brief = niche_res.get("brief")
    except Exception as e:
        logger.warning(f"Error auto-inyectando investigación de nicho para cuenta {account_id}: {e}")

    visual_perf_summary = None
    try:
        visual_res = run_visual_performance_skill(account_id)
        if isinstance(visual_res, dict):
            visual_perf_summary = visual_res.get("summary")
    except Exception as e:
        logger.warning(f"Error auto-inyectando rendimiento visual para cuenta {account_id}: {e}")

    # 2. Get system prompt (prompts.py)
    system_prompt = get_system_prompt(
        account_id,
        niche_brief=niche_brief,
        visual_perf_summary=visual_perf_summary,
    )
    
    # 3. Save system prompt to memory
    append_turn(account_id, session_id, "system", content=system_prompt)
    
    # Configure genai model
    model = _FallbackGenerativeModel(system_prompt, declarations)

    history = []
    
    # User trigger
    user_content = "Comienza la generación de propuestas de contenido de esta semana."
    append_turn(account_id, session_id, "user", content=user_content)
    history.append({"role": "user", "parts": [{"text": user_content}]})
    
    turns = 0
    images_scanned = 0
    images_analyzed = 0
    posts_drafted = 0
    post_ids: List[int] = []
    created_posts: List[Dict[str, Any]] = []
    created_post_types: List[str] = []
    proposal_created = False
    proposal_id: Optional[str] = None

    # Campaña consultada durante la sesión (Fase 2): se captura del tool-dispatch loop
    # y se enlaza a cada decisión posterior + alimenta el ranking de imágenes (Fase 6).
    session_campaign_id: Optional[str] = None
    session_campaign_focus: str = ""

    history_window = int(os.environ.get("HERMES_HISTORY_WINDOW", "8"))

    while turns < max_turns:
        try:
            # We mock the generate_content call in tests
            response = model.generate_content(_compress_history(history, history_window))
            turns += 1
        except Exception as e:
            return HermesSessionResult(error=f"gemini_error: {str(e)}")
            
        function_calls, model_parts, tool_responses, dispatched = await _dispatch_turn(
            response, bridge, account_id,
            campaign_focus=session_campaign_focus,
            exclude_used_media=True,
        )

        append_turn(
            account_id=account_id,
            session_id=session_id,
            role="model",
            content=_safe_response_text(response),
            tool_name=function_calls[0].name if function_calls else None,
            # Reuse the tool_args _dispatch_turn already extracted instead of
            # re-deriving from function_calls[0].args.
            tool_args=dispatched[0][1] if dispatched else None
        )

        history.append({"role": "model", "parts": model_parts})

        if not function_calls:
            break

        for tool_name, tool_args, result in dispatched:
            # Fase 2: captura la campaña activa consultada en la sesión.
            if tool_name == "supabase_get_campaign" and isinstance(result, dict) and result.get("has_campaign"):
                if result.get("campaign_id"):
                    session_campaign_id = str(result["campaign_id"])
                if result.get("context_text"):
                    session_campaign_focus = result["context_text"]

            # Track counts
            if tool_name == "drive_list_files":
                if isinstance(result, list):
                    images_scanned += len(result)
                else:
                    images_scanned += 1
            elif tool_name == "vision_analyze_image":
                images_analyzed += 1
            elif tool_name == "supabase_create_post":
                posts_drafted += 1
                if tool_args.get("post_type"):
                    created_post_types.append(tool_args.get("post_type"))
                if isinstance(result, dict) and result.get("id") is not None:
                    post_ids.append(result["id"])
                    created_posts.append({
                        "post_id": result["id"],
                        "drive_file_id": tool_args.get("drive_file_id"),
                        "scheduled_publish_time": tool_args.get("scheduled_publish_time"),
                    })
            elif tool_name == "supabase_create_proposal":
                proposal_created = True
                if isinstance(result, dict) and result.get("id") is not None:
                    proposal_id = str(result["id"])

            append_turn(
                account_id=account_id,
                session_id=session_id,
                role="tool",
                tool_name=tool_name,
                tool_args=tool_args,
                tool_result=result
            )

            if tool_name in _DECISION_TOOL_NAMES:
                try:
                    record_agent_decision(
                        account_id=account_id,
                        session_id=session_id,
                        decision_type=tool_name,
                        tool_args=tool_args,
                        tool_result=result,
                        campaign_id=session_campaign_id,
                        related_post_id=result.get("id") if tool_name == "supabase_create_post" and isinstance(result, dict) else None,
                        related_proposal_id=str(result["id"]) if tool_name == "supabase_create_proposal" and isinstance(result, dict) and result.get("id") is not None else None,
                    )
                except Exception:
                    logger.warning(
                        "record_agent_decision failed for tool=%s account_id=%s", tool_name, account_id, exc_info=True
                    )

        # Gemini's own SDK sends function responses back with role="user" (see
        # generative_models.py's ChatSession._USER_ROLE), not "tool" — the API
        # rejects "tool" as an unsupported role for at least some model versions.
        history.append({"role": "user", "parts": tool_responses})

    else:
        # Exceeded limit
        if proposal_created:
            _correct_content_type_mix(account_id, post_ids)
            _backfill_slot_media(proposal_id, created_posts)
        _maybe_record_schedule_mix_suggestions(
            account_id, session_id, session_campaign_id, model, created_post_types
        )
        return HermesSessionResult(
            images_scanned=images_scanned,
            images_analyzed=images_analyzed,
            posts_drafted=posts_drafted,
            proposal_id=proposal_id,
            error="hermes_max_turns_exceeded"
        )

    if proposal_created:
        _correct_content_type_mix(account_id, post_ids)
        _backfill_slot_media(proposal_id, created_posts)

    _maybe_record_schedule_mix_suggestions(
        account_id, session_id, session_campaign_id, model, created_post_types
    )

    return HermesSessionResult(
        images_scanned=images_scanned,
        images_analyzed=images_analyzed,
        posts_drafted=posts_drafted,
        proposal_id=proposal_id
    )


# Tool set exposed to Gemini per edit_type (design.md §Architecture Decisions #2) —
# a fraction of the 13 tools the weekly session sees, since an edit only ever touches
# one field.
_EDIT_TOOL_SETS = {
    "TIME": ([supabase_mcp], ["supabase_update_post_schedule"]),
    "DATE": ([supabase_mcp], ["supabase_update_post_schedule"]),
    "IMAGE_SELECT": ([drive_mcp, supabase_mcp], ["supabase_get_account", "drive_list_files", "supabase_update_post_image"]),
    "CAMPAIGN_CHAT": ([supabase_mcp], [
        "supabase_update_campaign_focus",
        "supabase_update_campaign_milestones",
        "supabase_update_campaign_details",
    ]),
}


async def run_edit_session(
    account_id: int,
    edit_type: str,
    context: Dict[str, Any],
    user_message: str,
    on_progress: Optional[Callable] = None
) -> EditSessionResult:
    """Run a light, single-purpose Hermes session to resolve one ambiguous edit
    (schedule time or image selection) on an existing post. Unlike run_session, this
    doesn't persist the full turn-by-turn history to agent_memory (design.md
    §Architecture Decisions #5) — only the fact that a correction was resolved gets
    persisted (via append_correction), as a signal for future weekly sessions, not a
    replay log. Only considers the edit resolved once a tool call actually succeeded
    — a text-only reply, however conversational, is treated as Hermes still trying
    to understand.
    """
    # 4, not 3: IMAGE_SELECT needs supabase_get_account -> drive_list_files ->
    # supabase_update_post_image -> final text (confirmed live against account 7).
    max_turns = int(os.environ.get("HERMES_EDIT_MAX_TURNS", "4"))

    mcp_servers, allowed_tools = _EDIT_TOOL_SETS[edit_type]
    bridge = ToolBridge(mcp_servers, allowed_tools=allowed_tools)
    declarations = await bridge.discover_tools()

    system_prompt = get_edit_prompt(edit_type, context, account_id)
    model = _FallbackGenerativeModel(system_prompt, declarations, model_names=EDIT_GEMINI_MODELS)

    history = [{"role": "user", "parts": [{"text": user_message}]}]

    turns = 0
    tool_called = False
    last_text = ""

    history_window = int(os.environ.get("HERMES_HISTORY_WINDOW", "8"))

    while turns < max_turns:
        try:
            response = model.generate_content(_compress_history(history, history_window))
            turns += 1
        except Exception as e:
            return EditSessionResult(resolved=False, message=f"Error de Hermes: {str(e)}")

        function_calls, model_parts, tool_responses, _dispatched = await _dispatch_turn(
            response, bridge, account_id, on_progress
        )
        last_text = _safe_response_text(response)
        history.append({"role": "model", "parts": model_parts})

        if function_calls:
            tool_called = True
            # See run_session's identical fix — Gemini expects role="user" for
            # function-response turns, not "tool".
            history.append({"role": "user", "parts": tool_responses})
            continue

        if tool_called:
            append_correction(account_id, edit_type, user_message, resolution=last_text)
            return EditSessionResult(resolved=True, message=last_text)

        # Plain text with no tool call and nothing resolved yet — there's no new
        # user input to continue the conversation with, and looping back would
        # re-send a history ending in a "model" turn, which Gemini's API rejects
        # outright ("Requests ending with a model turn are not supported").
        break

    return EditSessionResult(
        resolved=False,
        message=last_text or "No entendí el cambio que querías hacer. ¿Podrías intentarlo de otra forma?"
    )

