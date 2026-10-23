"""
Inteligencia de cuentas de referencia (AD-10, AD-11): Business Discovery de la
Graph API, sin LLM. Cada referente se analiza como mucho una vez cada 7 días
(24 h si falló) y el resultado se guarda en reference_account_snapshots.
"""

import json
import logging
from collections import Counter
from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Any, Dict, List, Optional

import requests

from database.supabase_client import get_supabase_admin_client
from services.content_quality import score_hook
from services.gemini_service import generate_gemini_content_sync
from services.hermes.memory import record_agent_decision
from utils.encryption import decrypt_token
from utils.graph_api import graph_url

logger = logging.getLogger(__name__)

MAX_REFERENCES = 5
FRESH_OK = timedelta(days=7)
FRESH_ERROR = timedelta(hours=24)
MEDIA_LIMIT = 25
TOP_POSTS = 3
MAX_NEW_PILLARS = 3
MIX_GAP_PP = 20
HOOK_MAX_CHARS = 125
CAPTION_EXCERPT_CHARS = 300
# Un referente con más de N veces tus seguidores no sirve para comparar mix ni frecuencia
MAX_SIZE_RATIO = 50

_DISCOVERY_FIELDS = (
    "business_discovery.username({username}){{username,followers_count,media_count,"
    f"media.limit({MEDIA_LIMIT}){{{{caption,media_type,media_product_type,like_count,"
    "comments_count,timestamp,permalink}}}}"
)

# Graph API: límites de uso y "usuario no encontrado" de Business Discovery
_RATE_LIMIT_CODES = {4, 17, 32, 613}
_NOT_FOUND_SUBCODE = 2207013

# Formato de Business Discovery → clave del content_type_mix propio
FORMAT_TO_MIX = {"REELS": "reel", "CAROUSEL_ALBUM": "carousel", "IMAGE": "post"}

class BusinessDiscoveryError(Exception):
    def __init__(self, status: str, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


# --- Graph API -------------------------------------------------------------

def _fetch_business_discovery(ig_user_id: str, token: str, username: str) -> Dict[str, Any]:
    resp = requests.get(
        graph_url(ig_user_id),
        params={"fields": _DISCOVERY_FIELDS.format(username=username), "access_token": token},
        timeout=15,
    )
    if resp.ok:
        data = resp.json().get("business_discovery")
        if not data:
            raise BusinessDiscoveryError("not_found", f"@{username} no existe")
        return data

    error = (resp.json() if resp.content else {}).get("error", {})
    code, subcode = error.get("code"), error.get("error_subcode")
    if code in _RATE_LIMIT_CODES:
        raise BusinessDiscoveryError("error", "Límite de llamadas de Instagram alcanzado; se reintentará más tarde")
    if subcode == _NOT_FOUND_SUBCODE or "cannot be found" in str(error.get("message", "")).lower():
        raise BusinessDiscoveryError("not_found", f"@{username} no existe o no es una cuenta profesional")
    if code in (100, 110):
        raise BusinessDiscoveryError(
            "not_professional", f"@{username} no es una cuenta profesional: Instagram no permite analizarla"
        )
    raise BusinessDiscoveryError("error", error.get("message") or f"Error {resp.status_code} de Instagram")


# --- Métricas (puras) ------------------------------------------------------

def _format_of(media: Dict[str, Any]) -> str:
    if media.get("media_product_type") == "REELS" or media.get("media_type") == "VIDEO":
        return "REELS"
    if media.get("media_type") == "CAROUSEL_ALBUM":
        return "CAROUSEL_ALBUM"
    return "IMAGE"


def _first_line(caption: Optional[str]) -> str:
    """Primera línea del caption, cortada a lo que se ve antes del "… más" (125)."""
    line = next((line.strip() for line in (caption or "").splitlines() if line.strip()), "")
    return line if len(line) <= HOOK_MAX_CHARS else line[:HOOK_MAX_CHARS].rstrip() + "…"


def compute_reference_metrics(data: Dict[str, Any], now: Optional[datetime] = None) -> Dict[str, Any]:
    """Métricas de AD-10 a partir de la respuesta de Business Discovery."""
    now = now or datetime.now(timezone.utc)
    followers = int(data.get("followers_count") or 0)
    media = (data.get("media") or {}).get("data") or []

    def _when(m: Dict[str, Any]) -> Optional[datetime]:
        try:
            return datetime.fromisoformat(str(m.get("timestamp")).replace("+0000", "+00:00").replace("Z", "+00:00"))
        except ValueError:
            return None

    recent = [m for m in media if (_when(m) or datetime.min.replace(tzinfo=timezone.utc)) >= now - timedelta(days=28)]
    formats = Counter(_format_of(m) for m in media)
    format_mix = {f: round(100 * formats.get(f, 0) / len(media)) if media else 0 for f in FORMAT_TO_MIX}

    def _rate(m: Dict[str, Any]) -> float:
        interactions = int(m.get("like_count") or 0) + int(m.get("comments_count") or 0)
        return round(100 * interactions / followers, 2) if followers else 0.0

    ranked = sorted(media, key=_rate, reverse=True)
    top = ranked[:TOP_POSTS]
    top_posts = []
    for m in top:
        line = _first_line(m.get("caption"))
        top_posts.append({
            "caption_first_line": line,
            "media_type": _format_of(m),
            "engagement_rate": _rate(m),
            "permalink": m.get("permalink"),
            "timestamp": m.get("timestamp"),
            "hook_formula": score_hook(line)["formula_name"] if line else None,
        })

    formulas = Counter(p["hook_formula"] for p in top_posts if p["hook_formula"])
    return {
        "followers": followers,
        "posts_per_week": round(len(recent) / 4, 1),
        "format_mix": format_mix,
        "top_posts": top_posts,
        "hook_formulas": [name for name, _ in formulas.most_common(3)],
        "median_engagement_rate": round(median([_rate(m) for m in media]), 2) if media else None,
        # Captions de los top posts para extraer temas con Gemini (AD-11)
        "top_captions": [(m.get("caption") or "")[:CAPTION_EXCERPT_CHARS] for m in top if m.get("caption")],
    }


# --- Caché + análisis -------------------------------------------------------

def _is_fresh(snapshot: Dict[str, Any], now: datetime) -> bool:
    fetched = datetime.fromisoformat(str(snapshot["fetched_at"]).replace("Z", "+00:00"))
    ttl = FRESH_OK if snapshot.get("status") == "ok" else FRESH_ERROR
    return now - fetched < ttl


def _is_comparable(followers: Optional[int], own_followers: Optional[int]) -> Optional[bool]:
    if not followers or not own_followers:
        return None
    return followers <= own_followers * MAX_SIZE_RATIO


def _to_analysis(snapshot: Dict[str, Any], own_followers: Optional[int] = None) -> Dict[str, Any]:
    payload = snapshot.get("payload") or {}
    return {
        "username": snapshot["username"],
        "status": snapshot["status"],
        "error_message": snapshot.get("error_message"),
        "fetched_at": snapshot.get("fetched_at"),
        **{k: payload.get(k) for k in (
            "followers", "posts_per_week", "format_mix", "top_posts", "hook_formulas", "median_engagement_rate",
        )},
        "comparable": _is_comparable(payload.get("followers"), own_followers),
        "top_captions": payload.get("top_captions") or [],
    }


def analyze_reference_accounts(account_id: int, force_refresh: bool = False) -> Dict[str, Any]:
    """Analiza los referentes de la cuenta respetando la caché. Devuelve
    {references, summary, refreshed}; refreshed indica si hubo llamadas a la API."""
    supabase = get_supabase_admin_client()
    acc_res = supabase.table("instagram_accounts").select(
        "id, reference_accounts, content_pillars, content_type_mix, instagram_business_account_id, "
        "long_lived_access_token, login_type, followers_count, default_language"
    ).eq("id", account_id).execute()
    account = acc_res.data[0] if acc_res.data else {}
    usernames = [str(u).strip().lstrip("@") for u in (account.get("reference_accounts") or []) if str(u).strip()]
    usernames = list(dict.fromkeys(usernames))[:MAX_REFERENCES]
    if not usernames:
        return {"references": [], "summary": "", "refreshed": False}

    snap_res = supabase.table("reference_account_snapshots").select("*").eq("account_id", account_id).execute()
    snapshots = {s["username"]: s for s in (snap_res.data or [])}
    now = datetime.now(timezone.utc)

    stale = [u for u in usernames if force_refresh or u not in snapshots or not _is_fresh(snapshots[u], now)]
    if stale:
        token = decrypt_token(account["long_lived_access_token"]) if account.get("long_lived_access_token") else None
        for username in stale:  # en serie: como mucho MAX_REFERENCES llamadas
            row: Dict[str, Any] = {"account_id": account_id, "username": username, "fetched_at": now.isoformat()}
            try:
                if not token or account.get("login_type") == "instagram":
                    raise BusinessDiscoveryError(
                        "error", "Business Discovery necesita la cuenta conectada con Facebook Login"
                    )
                data = _fetch_business_discovery(str(account.get("instagram_business_account_id")), token, username)
                row.update(status="ok", error_message=None, payload=compute_reference_metrics(data, now))
            except BusinessDiscoveryError as e:
                row.update(status=e.status, error_message=e.message, payload=None)
            except Exception as e:  # red, JSON inesperado...
                logger.warning(f"Business Discovery falló para @{username} (cuenta {account_id}): {e}")
                row.update(status="error", error_message="No se pudo consultar Instagram", payload=None)
            supabase.table("reference_account_snapshots").upsert(row, on_conflict="account_id,username").execute()
            snapshots[username] = row

    analysis = {
        "references": [_to_analysis(snapshots[u], account.get("followers_count")) for u in usernames],
        "refreshed": bool(stale),
    }
    analysis["summary"] = summarize_references(analysis)
    if stale:
        try:
            suggest_from_references(account, analysis)
        except Exception as e:
            logger.warning(f"Sugerencias de referentes fallidas para cuenta {account_id}: {e}")
    return analysis


def summarize_references(analysis: Dict[str, Any]) -> str:
    """Resumen de 3-6 líneas para los prompts semanal y mensual; vacío si no hay datos."""
    ok = [r for r in analysis.get("references", []) if r.get("status") == "ok"]
    if not ok:
        return ""
    lines = []
    for r in ok[:5]:
        mix = ", ".join(f"{k.lower()} {v}%" for k, v in (r.get("format_mix") or {}).items() if v)
        hooks = ", ".join(r.get("hook_formulas") or []) or "sin fórmula clara"
        size_note = " (mucho más grande que tu cuenta: tómalo como inspiración, no como ritmo)" \
            if r.get("comparable") is False else ""
        lines.append(
            f"- @{r['username']}: {r.get('followers') or 0} seguidores{size_note}, {r.get('posts_per_week')} posts/semana "
            f"({mix or 'sin datos de formato'}); ganchos que mejor le funcionan: {hooks}."
        )
    best = max(
        (p for r in ok for p in (r.get("top_posts") or [])),
        key=lambda p: p.get("engagement_rate") or 0, default=None,
    )
    if best and best.get("caption_first_line"):
        lines.append(f"Gancho con más engagement entre tus referentes: \"{best['caption_first_line']}\".")
    return "\n".join(lines)


def delete_stale_snapshots(account_id: int, usernames: List[str]) -> None:
    """Borra los snapshots de referentes que ya no están en la lista de la cuenta."""
    keep = {str(u).strip().lstrip("@") for u in usernames}
    supabase = get_supabase_admin_client()
    res = supabase.table("reference_account_snapshots").select("id, username").eq("account_id", account_id).execute()
    stale_ids = [s["id"] for s in (res.data or []) if s["username"] not in keep]
    if stale_ids:
        supabase.table("reference_account_snapshots").delete().in_("id", stale_ids).execute()


# --- Sugerencias (AD-11) ----------------------------------------------------

def _pending_suggestions(account_id: int, decision_type: str) -> List[Dict[str, Any]]:
    res = get_supabase_admin_client().table("agent_decisions").select("tool_args")\
        .eq("account_id", account_id).eq("status", "suggested").eq("decision_type", decision_type).execute()
    return res.data or []


def _already_pending(account_id: int, decision_type: str, key: str, value: Any) -> bool:
    return any((d.get("tool_args") or {}).get(key) == value for d in _pending_suggestions(account_id, decision_type))


def _redistribute(total: int, shares: Dict[str, float]) -> Dict[str, int]:
    """Reparte `total` según `shares` (%) por el método del mayor resto."""
    raw = {k: total * v / 100 for k, v in shares.items()}
    result = {k: int(v) for k, v in raw.items()}
    for k in sorted(raw, key=lambda k: raw[k] - result[k], reverse=True)[: total - sum(result.values())]:
        result[k] += 1
    return result


def _new_pillars_from_captions(pillars: List[str], refs: List[Dict[str, Any]], language: str) -> List[str]:
    """Hasta MAX_NEW_PILLARS temas recurrentes en los top posts de los referentes que
    no cubren los pilares actuales, en el idioma de la cuenta. Una llamada a Gemini por
    análisis (solo cuando se ha refrescado); si falla, no se sugiere nada."""
    captions = [f"@{r['username']}: {c}" for r in refs for c in (r.get("top_captions") or [])]
    if not captions:
        return []
    lang = {"es": "español", "en": "inglés"}.get(language, language)
    prompt = (
        "Eres estratega de contenido de Instagram. Estos son los captions de las publicaciones "
        "con más engagement de las cuentas de referencia de un usuario:\n"
        + "\n".join(f"- {c}" for c in captions)
        + f"\n\nPilares de contenido actuales del usuario: {', '.join(pillars) or 'ninguno'}.\n"
        f"Identifica como máximo {MAX_NEW_PILLARS} temas que se repitan en varias publicaciones y que "
        "NO estén ya cubiertos por los pilares actuales (ni con otras palabras). Cada tema en 1-4 "
        f"palabras, en {lang}, con formato de pilar de contenido. Si no hay ninguno claro, devuelve "
        'una lista vacía. Devuelve SOLO este JSON: {"pillars": ["tema", ...]}'
    )
    try:
        data = json.loads(generate_gemini_content_sync(prompt, json_mode=True))
    except Exception as e:
        logger.warning(f"Temas de referentes sin Gemini: {e}")
        return []
    lowered = [p.lower() for p in pillars]
    themes = [str(t).strip() for t in (data.get("pillars") or []) if str(t).strip()]
    return [t for t in themes if t.lower() not in lowered][:MAX_NEW_PILLARS]


def suggest_from_references(account: Dict[str, Any], analysis: Dict[str, Any]) -> List[str]:
    """Registra sugerencias de pilares y mix derivadas de los referentes (status
    'suggested'), sin duplicar una igual pendiente. Devuelve los tipos creados."""
    account_id = account["id"]
    ok = [r for r in analysis.get("references", []) if r.get("status") == "ok"]
    if not ok:
        return []
    created: List[str] = []

    # Pilares: temas recurrentes en los top posts que no cubren los pilares actuales
    pillars = [str(p) for p in (account.get("content_pillars") or []) if str(p).strip()]
    new = _new_pillars_from_captions(pillars, ok, account.get("default_language") or "es")
    if new:
        suggested_pillars = pillars + new
        if not _already_pending(account_id, "suggest_pillars_change", "suggested_content_pillars", suggested_pillars):
            record_agent_decision(
                account_id=account_id, session_id=None, decision_type="suggest_pillars_change",
                status="suggested", confidence_score=0.5,
                rationale=f"Tus referentes tratan a menudo {', '.join(new)} en sus publicaciones con más engagement.",
                tool_args={
                    "source": "reference_accounts",
                    "configured_content_pillars": pillars,
                    "suggested_content_pillars": suggested_pillars,
                },
            )
            created.append("suggest_pillars_change")

    # Mix y frecuencia: solo referentes de un tamaño comparable
    ok = [r for r in ok if r.get("comparable") is not False]
    if not ok:
        return created

    # Mix: formato medio de los referentes vs. el propio (sin stories)
    mix = {k: v for k, v in (account.get("content_type_mix") or {}).items() if isinstance(v, int)}
    feed_total = sum(mix.get(k, 0) for k in FORMAT_TO_MIX.values())
    ref_shares = {
        FORMAT_TO_MIX[f]: sum((r.get("format_mix") or {}).get(f, 0) for r in ok) / len(ok) for f in FORMAT_TO_MIX
    }
    own_shares = {k: (100 * mix.get(k, 0) / feed_total if feed_total else 0) for k in FORMAT_TO_MIX.values()}
    gap = max(abs(ref_shares[k] - own_shares[k]) for k in ref_shares)
    ref_freq = sum(r.get("posts_per_week") or 0 for r in ok) / len(ok)
    raise_total = ref_freq >= feed_total + 2
    if feed_total and (gap > MIX_GAP_PP or raise_total):
        new_total = feed_total + 1 if raise_total else feed_total
        suggested_mix = {**mix, **_redistribute(new_total, ref_shares)}
        if suggested_mix != mix and not _already_pending(
            account_id, "suggest_mix_change", "suggested_content_type_mix", suggested_mix
        ):
            reasons = []
            if gap > MIX_GAP_PP:
                reasons.append(
                    "reparten sus formatos así: "
                    + ", ".join(f"{k} {round(v)}%" for k, v in ref_shares.items())
                )
            if raise_total:
                reasons.append(
                    f"publican de media {round(ref_freq, 1)} veces por semana frente a tus {feed_total}; "
                    "se propone subir solo una publicación"
                )
            record_agent_decision(
                account_id=account_id, session_id=None, decision_type="suggest_mix_change",
                status="suggested", confidence_score=0.5,
                rationale=("Tus referentes " + "; ".join(reasons) + ".")[:500],
                tool_args={
                    "source": "reference_accounts",
                    "configured_mix": mix,
                    "suggested_content_type_mix": suggested_mix,
                },
            )
            created.append("suggest_mix_change")
    return created


def reference_summary_for_prompt(account_id: int) -> Optional[str]:
    """Resumen para las sesiones semanal y mensual; respeta la caché (puede refrescar)."""
    return analyze_reference_accounts(account_id).get("summary") or None
