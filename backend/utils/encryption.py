# backend/utils/encryption.py

import base64
import hashlib
import logging
import os

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)


def get_fernet_key() -> bytes:
    """Return a valid Fernet key: TOKENS_ENCRYPTION_KEY if set, else derived from SUPABASE_KEY."""
    explicit_key = os.environ.get("TOKENS_ENCRYPTION_KEY")
    if explicit_key:
        return explicit_key.encode("utf-8")

    supabase_key = os.environ.get("SUPABASE_KEY", "")
    digest = hashlib.sha256(supabase_key.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_token(value: str) -> str:
    if not value:
        return value
    fernet = Fernet(get_fernet_key())
    return fernet.encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_token(value: str) -> str:
    if not value:
        return value
    fernet = Fernet(get_fernet_key())
    try:
        return fernet.decrypt(value.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError) as e:
        logger.debug("Token decryption failed, treating as legacy plain-text: %s", e)
        return value
