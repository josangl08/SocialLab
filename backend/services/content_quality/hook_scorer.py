"""
Hook Scorer Module
Extracts first sentence, matches against 26 hook formulas, detects dealbreakers,
and scores retention potential (0-100).
Pure Python, deterministic, no I/O.
"""

import re
from functools import lru_cache
from typing import Optional, List, Dict, Any, Tuple

from ._data import load_json, utf16_len

MOBILE_FOLD = 125
DEALBREAKER_CAP = 20
MAX_ALTERNATIVES = 3

# Puntuación: base + fórmula + longitud + especificidad numérica + encaje con estrategia = 100
SCORE_BASE = 20
SCORE_FORMULA = 35
SCORE_LENGTH = 15
SCORE_NUMERIC = 15
SCORE_STRATEGY_FIT = 15

_SENTENCE_END_RE = re.compile(r"(?<=[.!?…])\s+|\n")
_LEADING_NOISE_RE = re.compile(r"^[^\w¿¡]+")
_DIGIT_RE = re.compile(r"\d")


@lru_cache(maxsize=1)
def _compiled() -> Tuple[List[Tuple[Dict[str, Any], List[re.Pattern[str]]]], List[Tuple[str, re.Pattern[str]]]]:
    data = load_json("hooks_data.json")
    formulas = [
        (f, [re.compile(p, re.IGNORECASE) for p in f["patterns"]])
        for f in data["formulas"]
    ]
    dealbreakers = [
        (d, re.compile(rf"^[¿¡]?{re.escape(d)}(?!\w)", re.IGNORECASE))
        for d in data["dealbreakers"]
    ]
    return formulas, dealbreakers


def extract_first_sentence(text: str) -> str:
    """Primera frase no vacía, sin emojis ni símbolos iniciales."""
    for part in _SENTENCE_END_RE.split(text.strip()):
        part = _LEADING_NOISE_RE.sub("", part.strip())
        if part:
            return part
    return ""


def _public(formula: Dict[str, Any]) -> Dict[str, Any]:
    return {k: formula[k] for k in ("id", "name", "template", "best_for")}


def get_hook_formulas(strategy_mode: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Returns the catalog of 26 hook formulas. With `strategy_mode`, the ones
    recommended for that strategy come first (stable order by id otherwise).
    """
    formulas = [_public(f) for f, _ in _compiled()[0]]
    if strategy_mode:
        formulas.sort(key=lambda f: strategy_mode not in f["best_for"])
    return formulas


def score_hook(
    hook: str,
    strategy_mode: Optional[str] = None
) -> Dict[str, Any]:
    """
    Evaluates first sentence against 26 hook formulas, checks length,
    numbers, and penalizes dealbreakers (score capped at 20).
    """
    formulas, dealbreakers = _compiled()
    sentence = extract_first_sentence(hook)

    matched: Optional[Dict[str, Any]] = None
    for formula, patterns in formulas:
        if any(p.search(sentence) for p in patterns):
            matched = formula
            break

    found_dealbreakers = [d for d, p in dealbreakers if p.search(sentence)]

    score = 0
    if sentence:
        score = SCORE_BASE
        if matched:
            score += SCORE_FORMULA
            if strategy_mode and strategy_mode in matched["best_for"]:
                score += SCORE_STRATEGY_FIT
        if utf16_len(sentence) <= MOBILE_FOLD:
            score += SCORE_LENGTH
        if _DIGIT_RE.search(sentence):
            score += SCORE_NUMERIC
    if found_dealbreakers:
        score = min(score, DEALBREAKER_CAP)

    alternatives = [
        {"formula_id": f["id"], "name": f["name"], "template": f["template"]}
        for f in get_hook_formulas(strategy_mode)
        if not matched or f["id"] != matched["id"]
    ][:MAX_ALTERNATIVES]

    return {
        "formula_id": matched["id"] if matched else None,
        "formula_name": matched["name"] if matched else None,
        "score": min(100, score),
        "dealbreakers": found_dealbreakers,
        "alternatives": alternatives,
    }
