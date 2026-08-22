# backend/utils/oauth_state.py

import json
from typing import Optional, TypedDict

from cryptography.fernet import Fernet, InvalidToken

from utils.encryption import get_fernet_key


class OAuthStatePayload(TypedDict):
    user_id: str
    account_id: Optional[str]


def generate_state_token(user_id: str, account_id: Optional[str] = None) -> str:
    fernet = Fernet(get_fernet_key())
    payload = json.dumps({"user_id": user_id, "account_id": account_id})
    return fernet.encrypt(payload.encode("utf-8")).decode("utf-8")


def verify_state_token(state_token: str, ttl: int = 600) -> OAuthStatePayload:
    fernet = Fernet(get_fernet_key())
    try:
        decrypted = fernet.decrypt(state_token.encode("utf-8"), ttl=ttl).decode("utf-8")
    except (InvalidToken, ValueError) as e:
        raise ValueError("Parámetro state inválido o expirado.") from e
    try:
        payload = json.loads(decrypted)
        return {"user_id": payload["user_id"], "account_id": payload.get("account_id")}
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        raise ValueError("Parámetro state inválido o expirado.") from e
