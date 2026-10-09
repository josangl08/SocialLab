"""
Caption Linter Module
Emulates mobile preview cut (125 chars), hashtag auditing, and keyword visibility.
Pure Python, deterministic, no I/O.
"""

import re
from typing import Optional, List, Dict, Any

from ._data import utf16_len, utf16_prefix
from .humanizer import detect_slop
from .hook_scorer import score_hook

MOBILE_FOLD = 125
HASHTAG_LIMIT = 5
HOOK_WEAK_THRESHOLD = 40

_HASHTAG_RE = re.compile(r"(?<![\w#])#(\w+)")
# Hashtag con el espacio que lo precede, para recortarlo sin dejar huecos.
_HASHTAG_WITH_SPACE_RE = re.compile(r"[ \t]*(?<![\w#])#\w+")


def extract_hashtags(caption: str) -> List[str]:
    return [f"#{tag}" for tag in _HASHTAG_RE.findall(caption)]


def lint_caption(
    caption: str,
    keywords: Optional[List[str]] = None,
    format: str = "post",
    language: str = "es",
    extra_banned: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Evaluates a caption against 125-char mobile fold, hashtag limit (5 max),
    SEO keywords visibility, and slop/hook analysis.
    `format` is accepted for API symmetry; the rules are the same for every format.
    """
    visible = utf16_prefix(caption, MOBILE_FOLD)
    truncated = len(visible) < len(caption)

    hashtags = extract_hashtags(caption)
    over_limit = hashtags[HASHTAG_LIMIT:]

    visible_lower = visible.lower()
    missing = [k for k in (keywords or []) if k.strip() and k.lower() not in visible_lower]

    slop = detect_slop(caption, language=language, extra_banned=extra_banned)
    hook = score_hook(caption)
    hook.pop("alternatives", None)

    warnings: List[Dict[str, str]] = []
    if over_limit:
        warnings.append({
            "code": "HASHTAGS_OVER_LIMIT",
            "message": f"{len(hashtags)} / {HASHTAG_LIMIT} máx. Sobran: {' '.join(over_limit)}",
        })
    if missing:
        warnings.append({
            "code": "KEYWORDS_NOT_VISIBLE",
            "message": f"No visibles antes del '… más': {', '.join(missing)}",
        })
    if slop["hits"]:
        warnings.append({
            "code": "SLOP_DETECTED",
            "message": f"{len(slop['hits'])} expresiones con sonido a IA",
        })
    if slop["invisible_chars"]:
        warnings.append({
            "code": "INVISIBLE_CHARS",
            "message": f"{slop['invisible_chars']} caracteres invisibles",
        })
    if slop["em_dash_count"] >= 2:
        warnings.append({
            "code": "EM_DASHES",
            "message": f"{slop['em_dash_count']} em dashes; usa comas o puntos",
        })
    if hook["dealbreakers"]:
        warnings.append({
            "code": "HOOK_DEALBREAKER",
            "message": f"Apertura genérica: {', '.join(hook['dealbreakers'])}",
        })
    elif caption.strip() and hook["score"] < HOOK_WEAK_THRESHOLD:
        warnings.append({
            "code": "HOOK_WEAK",
            "message": f"Gancho débil ({hook['score']}/100)",
        })

    return {
        "visible_text": visible,
        "visible_length": utf16_len(visible),
        "truncated": truncated,
        "hashtag_count": len(hashtags),
        "hashtag_limit": HASHTAG_LIMIT,
        "hashtags_over_limit": over_limit,
        "keywords_missing_in_visible": missing,
        "slop": slop,
        "hook": hook,
        "warnings": warnings,
    }


def enforce_hashtag_limit(caption: str, max_hashtags: int = HASHTAG_LIMIT) -> str:
    """
    Enforces maximum hashtag limit by trimming excess hashtags from the end
    (the community layer goes last, so it is the first to be dropped).
    Idempotent: a caption already within the limit is returned unchanged.
    """
    if len(extract_hashtags(caption)) <= max_hashtags:
        return caption

    kept = 0

    def _sub(m: re.Match[str]) -> str:
        nonlocal kept
        kept += 1
        return m.group(0) if kept <= max_hashtags else ""

    trimmed = _HASHTAG_WITH_SPACE_RE.sub(_sub, caption)
    # Quita líneas que quedaron vacías al final por los hashtags eliminados.
    return trimmed.rstrip()
