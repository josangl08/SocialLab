"""
Profile Auditor Module
Deterministic scoring of Instagram profile against 12-item rubric (0-100).
Pure Python, deterministic, no I/O.
"""

import re
from typing import Callable, Dict, Any, List
from urllib.parse import urlparse

from ._data import load_json

THIRD_PARTY_LINK_HOSTS = {
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "linktr.ee",
    "beacons.ai", "lnk.bio", "linkin.bio", "campsite.bio",
}
BUSINESS_ACCOUNT_TYPES = {"business", "creator", "professional"}
MIN_HIGHLIGHTS = 3

_AUTHORITY_RE = re.compile(
    r"\d|%|\b(años|clientes|fundador|fundadora|ceo|autor|autora|certificad\w*|"
    r"premio|years|clients|founder|author|certified|award)\b",
    re.IGNORECASE,
)
_CTA_RE = re.compile(
    r"👇|⬇|⤵|\b(link|enlace|descarga|reserva|gratis|clic|click|aquí|apúntate|"
    r"escríbeme|compra|prueba|free|download|book|shop|join|dm)\b",
    re.IGNORECASE,
)


def _first(data: Dict[str, Any], *keys: str) -> str:
    """Primer valor no vacío entre los alias de campo (Graph API vs. columnas de la tabla)."""
    for key in keys:
        value = data.get(key)
        if value:
            return str(value).strip()
    return ""


def _bio(d: Dict[str, Any]) -> str:
    return _first(d, "biography", "bio")


def _bio_lines(d: Dict[str, Any]) -> List[str]:
    return [line for line in _bio(d).splitlines() if line.strip()]


def _url(d: Dict[str, Any]) -> str:
    return _first(d, "external_url", "website")


def _username_clarity(d: Dict[str, Any]) -> bool:
    username = _first(d, "username")
    return bool(username) and not re.search(r"\d{3,}", username) and len(re.findall(r"[._]", username)) <= 2


def _display_name_seo(d: Dict[str, Any]) -> bool:
    name = _first(d, "full_name", "name")
    return len(name.split()) >= 2 and name.lower() != _first(d, "username").lower()


def _link_clarity(d: Dict[str, Any]) -> bool:
    url = _url(d)
    if not url:
        return False
    host = urlparse(url if "://" in url else f"https://{url}").hostname or ""
    host = host.removeprefix("www.")
    return bool(host) and host not in THIRD_PARTY_LINK_HOSTS


def _contact_options(d: Dict[str, Any]) -> bool:
    return (
        bool(d.get("is_business_account"))
        or _first(d, "account_type").lower() in BUSINESS_ACCOUNT_TYPES
        or bool(_first(d, "business_email", "email", "business_phone_number", "phone"))
    )


CHECKS: Dict[str, Callable[[Dict[str, Any]], bool]] = {
    "username_clarity": _username_clarity,
    "display_name_seo": _display_name_seo,
    "profile_photo": lambda d: bool(_first(d, "profile_pic_url", "profile_picture_url")),
    "bio_value_prop": lambda d: bool(_bio_lines(d)) and len(_bio_lines(d)[0].split()) >= 4,
    "bio_authority": lambda d: bool(_AUTHORITY_RE.search(_bio(d))),
    "bio_readability": lambda d: len(_bio_lines(d)) >= 2,
    "bio_cta": lambda d: bool(_CTA_RE.search(_bio(d))),
    "link_present": lambda d: bool(_url(d)),
    "link_clarity": _link_clarity,
    "category_set": lambda d: bool(_first(d, "category", "category_name", "sector")),
    "highlights_curated": lambda d: len(d.get("highlights") or []) >= MIN_HIGHLIGHTS,
    "contact_options": _contact_options,
}


def audit_profile(account_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluates account profile against profile_rubric.json.
    Returns overall score (0-100) and items breakdown. Missing data → item not passed.
    """
    items = []
    for item in load_json("profile_rubric.json")["rubric"]:
        passed = CHECKS[item["id"]](account_data)
        items.append({
            "id": item["id"],
            "label": item["label"],
            "passed": passed,
            "weight": item["weight"],
            "tip": item["tip"],
        })
    score = sum(i["weight"] for i in items if i["passed"])
    return {"score": score, "items": items}
