import os
import uuid
import inspect
from datetime import datetime
from typing import Optional, Dict, Any, List, Callable
from pydantic import BaseModel
from google.genai import types, errors
from database.supabase_client import get_supabase_admin_client
from services.hermes.tool_bridge import ToolBridge
from services.hermes.memory import (
    load_session_history,
    append_turn,
    append_correction,
    get_correction_count_since,
    summarize_recent_corrections,
)
from services.hermes.prompts import get_system_prompt, get_edit_prompt
from services.gemini_service import PREFERRED_GEMINI_MODELS, EDIT_GEMINI_MODELS, get_gemini_client
from mcp.drive_server import mcp as drive_mcp
from mcp.supabase_server import mcp as supabase_mcp
from mcp.vision_server import mcp as vision_mcp
from mcp.analytics_server import mcp as analytics_mcp
from mcp.skills_server import mcp as skills_mcp


class _FallbackGenerativeModel:
    """Wraps client.models.generate_content, retrying with the next name in
    PREFERRED_GEMINI_MODELS on a 429 (quota exceeded) ClientError — e.g. when
    the preferred (pro) model has no free-tier quota on a given project but the
    fallback (flash) one does. Once a model name succeeds, sticks with it for the
    rest of the turn loop instead of re-trying the higher-tier model every turn."""

    def __init__(self, system_instruction: str, tools: Any, model_names: Optional[List[str]] = None):
        self._system_instruction = system_instruction
        # google.genai's GenerateContentConfig.tools expects Tool objects, not bare
        # FunctionDeclarations — the old google.generativeai SDK auto-wrapped these.
        self._tools = [types.Tool(function_declarations=tools)] if tools else None
        self._model_names = model_names or PREFERRED_GEMINI_MODELS
        self._resolved_name: Optional[str] = None

    def generate_content(self, history):
        candidates = [self._resolved_name] if self._resolved_name else self._model_names
        last_error: Optional[Exception] = None
        client = get_gemini_client()
        config = types.GenerateContentConfig(
            system_instruction=self._system_instruction,
            tools=self._tools,
            # Keep manual control of the turn loop (tool dispatch via ToolBridge) —
            # the SDK's automatic function calling would short-circuit that.
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        for name in candidates:
            try:
                response = client.models.generate_content(model=name, contents=history, config=config)
                self._resolved_name = name
                return response
            except errors.ClientError as e:
                last_error = e
                if e.code == 429:
                    continue
                raise
        raise last_error

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
    on_progress: Optional[Callable] = None
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
        "agent_memory_summary_updated_at": datetime.utcnow().isoformat(),
    }).eq("id", account_id).execute()


async def run_session(account_id: int) -> HermesSessionResult:
    session_id = uuid.uuid4()
    max_turns = int(os.environ.get("HERMES_MAX_TURNS", "12"))

    # 1. Initialize tool bridge with MCP instances
    bridge = ToolBridge([drive_mcp, supabase_mcp, vision_mcp, analytics_mcp, skills_mcp])
    declarations = await bridge.discover_tools()

    # Refresh the persistent-memory summary (if stale) before building the prompt,
    # so this same session benefits from the latest corrections immediately.
    await _maybe_refresh_memory_summary(account_id)

    # 2. Get system prompt (prompts.py)
    system_prompt = get_system_prompt(account_id)
    
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
    proposal_created = False
    proposal_id: Optional[str] = None

    history_window = int(os.environ.get("HERMES_HISTORY_WINDOW", "8"))

    while turns < max_turns:
        try:
            # We mock the generate_content call in tests
            response = model.generate_content(_compress_history(history, history_window))
            turns += 1
        except Exception as e:
            return HermesSessionResult(error=f"gemini_error: {str(e)}")
            
        function_calls, model_parts, tool_responses, dispatched = await _dispatch_turn(
            response, bridge, account_id
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

        # Gemini's own SDK sends function responses back with role="user" (see
        # generative_models.py's ChatSession._USER_ROLE), not "tool" — the API
        # rejects "tool" as an unsupported role for at least some model versions.
        history.append({"role": "user", "parts": tool_responses})

    else:
        # Exceeded limit
        if proposal_created:
            _correct_content_type_mix(account_id, post_ids)
            _backfill_slot_media(proposal_id, created_posts)
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

