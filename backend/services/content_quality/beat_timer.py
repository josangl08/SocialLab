"""
Beat Timer Module
Calculates timecodes for reel scripts at 165 WPM, detects OVER_4S retention risk,
and checks for hook loop closing.
Pure Python, deterministic, no I/O.
"""

import re
from typing import List, Dict, Any, Set

DEFAULT_WPM = 165
MAX_BEAT_SECONDS = 4.0
MIN_KEYWORD_LEN = 4

_WORD_RE = re.compile(r"\w+")
_STOPWORDS = {
    # es
    "este", "esta", "esto", "estos", "estas", "ese", "esa", "eso", "como", "para",
    "pero", "porque", "cuando", "donde", "desde", "hasta", "sobre", "entre", "todo",
    "todos", "toda", "todas", "muy", "más", "menos", "aquí", "ahora", "cada", "otro",
    "otra", "verdadero", "verdadera", "siempre", "nunca", "tiene", "tienes", "hace",
    # en
    "this", "that", "with", "from", "have", "your", "what", "when", "where", "about",
    "just", "they", "them", "then", "there", "here", "into", "really",
}


def _keywords(text: str) -> Set[str]:
    return {
        w for w in (m.lower() for m in _WORD_RE.findall(text))
        if len(w) >= MIN_KEYWORD_LEN and w not in _STOPWORDS and not w.isdigit()
    }


def time_beats(
    beats: List[Dict[str, str]],
    wpm: int = DEFAULT_WPM
) -> Dict[str, Any]:
    """
    Calculates start_s, end_s, duration_s, OVER_4S alert, and loops_to_hook.
    `loops_to_hook` is True when the last beat reuses a keyword of the first one.
    """
    if wpm <= 0:
        raise ValueError("wpm must be positive")

    words_per_second = wpm / 60
    timed = []
    cursor = 0.0
    for beat in beats:
        text = beat.get("text", "")
        duration = round(len(text.split()) / words_per_second, 2)
        start = round(cursor, 2)
        cursor += duration
        timed.append({
            "label": beat.get("label", ""),
            "text": text,
            "start_s": start,
            "end_s": round(cursor, 2),
            "duration_s": duration,
            "alert": "OVER_4S" if duration > MAX_BEAT_SECONDS else None,
        })

    loops = len(beats) >= 2 and bool(
        _keywords(beats[0].get("text", "")) & _keywords(beats[-1].get("text", ""))
    )

    return {"beats": timed, "total_s": round(cursor, 2), "loops_to_hook": loops}
