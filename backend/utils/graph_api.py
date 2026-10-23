"""
Versión única de la Instagram/Facebook Graph API (env `INSTAGRAM_GRAPH_API_VERSION`).

Las URLs de OAuth (`oauth/authorize`, `oauth/access_token`) van sin versión y no usan esto.
"""
import logging
import re
from typing import Literal

import config

logger = logging.getLogger(__name__)

GRAPH_API_VERSION: str = config.INSTAGRAM_GRAPH_API_VERSION
GRAPH_BASE_URL: str = f"https://graph.facebook.com/{GRAPH_API_VERSION}"
# Las versiones anteriores ya han caducado o caducan pronto: Meta reenvía a la más antigua disponible
MIN_SUPPORTED_MAJOR = 24

LoginType = Literal['facebook', 'instagram']


def graph_base_url(login_type: LoginType) -> str:
    """Host de la Graph API según cómo se conectó la cuenta (Instagram Login o Facebook Login)."""
    host = 'graph.instagram.com' if login_type == 'instagram' else 'graph.facebook.com'
    return f"https://{host}/{GRAPH_API_VERSION}"


def graph_url(path: str) -> str:
    """graph_url("me/accounts") → "https://graph.facebook.com/v26.0/me/accounts"."""
    return f"{GRAPH_BASE_URL}/{path.lstrip('/')}"


def warn_if_outdated() -> None:
    """Avisa en logs si la versión configurada es anterior a v{MIN_SUPPORTED_MAJOR}.0."""
    match = re.fullmatch(r"v(\d+)\.\d+", GRAPH_API_VERSION)
    if not match:
        logger.warning(f"INSTAGRAM_GRAPH_API_VERSION con formato inesperado: {GRAPH_API_VERSION}")
    elif int(match.group(1)) < MIN_SUPPORTED_MAJOR:
        logger.warning(
            f"Graph API {GRAPH_API_VERSION} caducada o próxima a caducar: "
            f"usa v{MIN_SUPPORTED_MAJOR}.0 o posterior en INSTAGRAM_GRAPH_API_VERSION"
        )
