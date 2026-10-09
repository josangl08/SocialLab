"""
Humanizer Module
Detects synthetic AI slop, removes zero-width characters, collapses em-dashes,
and replaces clichés with natural phrasing. Idempotent.
Pure Python, deterministic, no I/O.
"""

import re
from functools import lru_cache
from typing import Optional, List, Dict, Any, Tuple

from ._data import load_json

EM_DASH = "—"
_EM_DASH_RE = re.compile(r"[ \t]*—[ \t]*")
_MAX_PASSES = 3


def _lexicon(language: str) -> Dict[str, str]:
    data = load_json("slop_lexicon.json")
    return data.get(language) or data["es"]


def _invisible_chars() -> List[str]:
    return load_json("slop_lexicon.json")["invisible_chars"]


@lru_cache(maxsize=64)
def _terms_regex(terms: Tuple[str, ...]) -> Optional[re.Pattern[str]]:
    """Regex de alternancia, términos más largos primero, con límites de palabra."""
    if not terms:
        return None
    ordered = sorted(terms, key=len, reverse=True)
    alternation = "|".join(re.escape(t) for t in ordered)
    return re.compile(rf"(?<!\w)({alternation})(?!\w)", re.IGNORECASE)


def _replacements(language: str, extra_banned: Optional[List[str]]) -> Dict[str, str]:
    """término (minúsculas) → reemplazo. Los vetados por la cuenta se eliminan ('')."""
    table = {k.lower(): v for k, v in _lexicon(language).items()}
    for term in extra_banned or []:
        term = term.strip().lower()
        if term and term not in table:
            table[term] = ""
    return table


def detect_slop(
    text: str,
    language: str = "es",
    extra_banned: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Detects slop terms, zero-width characters, and repeated em-dashes.
    Returns score (0 = limpio, 100 = máximo slop), hits, invisible_chars count
    and em_dash_count.
    """
    table = _replacements(language, extra_banned)
    pattern = _terms_regex(tuple(table))
    hits = []
    if pattern:
        for m in pattern.finditer(text):
            term = m.group(1).lower()
            hits.append({"term": term, "index": m.start(), "suggestion": table[term]})

    invisible = sum(text.count(ch) for ch in _invisible_chars())
    em_dashes = text.count(EM_DASH)

    score = 15 * len(hits) + 10 * invisible + (10 * em_dashes if em_dashes >= 2 else 0)
    return {
        "score": min(100, score),
        "hits": hits,
        "invisible_chars": invisible,
        "em_dash_count": em_dashes,
    }


def _match_case(original: str, replacement: str) -> str:
    if replacement and original[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def humanize(
    text: str,
    language: str = "es",
    extra_banned: Optional[List[str]] = None
) -> Tuple[str, List[Dict[str, str]]]:
    """
    Removes invisible characters, collapses em dashes (if >= 2),
    and substitutes synthetic lexicon.
    Returns (cleaned_text, list_of_changes). Idempotent.
    """
    changes: List[Dict[str, str]] = []

    for ch in _invisible_chars():
        if ch in text:
            text = text.replace(ch, "")
            changes.append({"from": ch, "to": "", "rule": "invisible_char"})

    if text.count(EM_DASH) >= 2:
        text = _EM_DASH_RE.sub(", ", text)
        changes.append({"from": EM_DASH, "to": ", ", "rule": "em_dash"})

    table = _replacements(language, extra_banned)
    pattern = _terms_regex(tuple(table))
    if pattern:
        # Un reemplazo nunca debería generar otro término, pero se itera hasta
        # estabilizar para garantizar humanize(humanize(x)) == humanize(x).
        for _ in range(_MAX_PASSES):
            pass_changes: List[Dict[str, str]] = []

            def _sub(m: re.Match[str]) -> str:
                original = m.group(1)
                replacement = _match_case(original, table[original.lower()])
                rule = "lexicon" if replacement else "banned_phrase"
                pass_changes.append({"from": original, "to": replacement, "rule": rule})
                return replacement

            text = pattern.sub(_sub, text)
            if not pass_changes:
                break
            changes.extend(pass_changes)
        # Limpia los huecos que dejan los términos vetados eliminados.
        if any(c["rule"] == "banned_phrase" for c in changes):
            text = re.sub(r"[ \t]{2,}", " ", text)
            text = re.sub(r"[ \t]+([,.;:!?])", r"\1", text)

    return text, changes
