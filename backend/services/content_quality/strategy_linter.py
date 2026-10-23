"""
Strategy linter (AD-5): detecta contradicciones y huecos del perfil de estrategia
de una cuenta. Python puro, sin I/O ni LLM; `empirical` es opcional y lo aporta
quien llama (AnalyticsService.get_empirical_scheduling_data).
"""

from typing import Any, Dict, List, Literal, Optional, TypedDict

from .schedule_disagreement import schedule_disagreement

MAX_REFERENCE_ACCOUNTS = 5
LEGACY_DEFAULT_BEST_TIMES = ["09:00", "18:00"]


class StrategyIssue(TypedDict):
    code: str
    severity: Literal["error", "warning", "info"]
    field: str
    tab: Literal["marca", "publicacion", "referentes"]
    message: str


def _issue(code: str, severity: str, field: str, tab: str, message: str) -> StrategyIssue:
    return {"code": code, "severity": severity, "field": field, "tab": tab, "message": message}  # type: ignore[typeddict-item]


def _mix_total(account: Dict[str, Any]) -> int:
    raw_mix = account.get("content_type_mix") or {}
    return sum(v for v in raw_mix.values() if isinstance(v, int) and v > 0)


def lint_strategy(account: Dict[str, Any], empirical: Optional[Dict[str, Any]] = None) -> List[StrategyIssue]:
    issues: List[StrategyIssue] = []
    account_type = account.get("account_type") or "personal"
    caption_voice = account.get("caption_voice")
    preferred_days = account.get("preferred_days") or []
    fixed = account.get("scheduling_mode") == "fixed"
    mix_total = _mix_total(account)

    if fixed and not preferred_days:
        issues.append(_issue(
            "FIXED_NO_DAYS", "error", "preferred_days", "publicacion",
            "Has elegido días específicos pero no has marcado ningún día.",
        ))
    if mix_total == 0:
        issues.append(_issue(
            "MIX_EMPTY", "error", "content_type_mix", "publicacion",
            "El mix de contenido está vacío: el agente no sabe cuántas publicaciones hacer por semana.",
        ))
    if fixed and preferred_days and mix_total > len(preferred_days):
        issues.append(_issue(
            "MIX_EXCEEDS_DAYS", "warning", "content_type_mix", "publicacion",
            f"El mix suma {mix_total} publicaciones por semana pero solo has elegido "
            f"{len(preferred_days)} días: algunos días tendrán dos publicaciones.",
        ))
    if caption_voice and caption_voice != account_type:
        issues.append(_issue(
            "VOICE_TYPE_MISMATCH", "info", "caption_voice", "marca",
            "La voz de los captions no coincide con el tipo de cuenta. Es válido si lo has elegido a propósito.",
        ))
    if not [p for p in (account.get("content_pillars") or []) if str(p).strip()]:
        issues.append(_issue(
            "NO_PILLARS", "warning", "content_pillars", "marca",
            "No hay pilares de contenido: el agente no sabe de qué temas hablar.",
        ))
    if not str(account.get("target_audience") or "").strip():
        issues.append(_issue(
            "NO_AUDIENCE", "warning", "target_audience", "marca",
            "No has definido la audiencia: el agente escribirá para una comunidad genérica.",
        ))

    searchable = " ".join(
        [str(p) for p in (account.get("content_pillars") or [])] + [str(account.get("style_guide") or "")]
    ).lower()
    clashing = [b for b in (account.get("banned_phrases") or []) if str(b).strip() and str(b).strip().lower() in searchable]
    if clashing:
        issues.append(_issue(
            "BANNED_IN_PILLARS", "warning", "banned_phrases", "marca",
            f"Términos vetados que aparecen en tus pilares o guía de estilo: {', '.join(clashing)}.",
        ))

    best_times = account.get("best_times")
    if best_times == LEGACY_DEFAULT_BEST_TIMES:
        issues.append(_issue(
            "DEFAULT_BEST_TIMES", "info", "best_times", "publicacion",
            "Tus horarios son los de por defecto (09:00 y 18:00). Elige los tuyos o usa tus datos.",
        ))
    if empirical and empirical.get("has_data") and best_times:
        reason = schedule_disagreement(best_times, empirical)
        if reason:
            issues.append(_issue("BEST_TIMES_DISAGREE", "info", "best_times", "publicacion", reason))

    references = [r for r in (account.get("reference_accounts") or []) if str(r).strip()]
    if len(references) > MAX_REFERENCE_ACCOUNTS:
        issues.append(_issue(
            "TOO_MANY_REFERENCES", "error", "reference_accounts", "referentes",
            f"Tienes {len(references)} cuentas de referencia; el máximo es {MAX_REFERENCE_ACCOUNTS}.",
        ))
    if (caption_voice or account_type) == "personal" and account.get("hashtag_strategy") == "maximum":
        issues.append(_issue(
            "PERSONAL_MAX_HASHTAGS", "info", "hashtag_strategy", "publicacion",
            "Con voz personal, 5 hashtags suelen restar naturalidad. Prueba con Mínimos o Moderados.",
        ))
    return issues
