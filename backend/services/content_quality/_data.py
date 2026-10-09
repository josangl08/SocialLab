"""
Carga perezosa (una vez por proceso) de los JSON de datos del motor de calidad.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

_DATA_DIR = Path(__file__).parent


@lru_cache(maxsize=None)
def load_json(filename: str) -> Dict[str, Any]:
    with open(_DATA_DIR / filename, encoding="utf-8") as f:
        return json.load(f)


def utf16_len(text: str) -> int:
    """Longitud como la cuenta Instagram: emojis fuera del BMP (par sustituto) cuentan 2."""
    return sum(2 if ord(ch) > 0xFFFF else 1 for ch in text)


def utf16_prefix(text: str, limit: int) -> str:
    """Prefijo más largo de `text` cuya longitud UTF-16 no supera `limit`."""
    total = 0
    for i, ch in enumerate(text):
        total += 2 if ord(ch) > 0xFFFF else 1
        if total > limit:
            return text[:i]
    return text
