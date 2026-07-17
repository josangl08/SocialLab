# backend/utils/oauth_state.py

from cryptography.fernet import Fernet, InvalidToken

from utils.encryption import get_fernet_key


def generate_state_token(user_id: str) -> str:
    fernet = Fernet(get_fernet_key())
    return fernet.encrypt(user_id.encode("utf-8")).decode("utf-8")


def verify_state_token(state_token: str, ttl: int = 600) -> str:
    fernet = Fernet(get_fernet_key())
    try:
        return fernet.decrypt(state_token.encode("utf-8"), ttl=ttl).decode("utf-8")
    except (InvalidToken, ValueError) as e:
        raise ValueError("Parámetro state inválido o expirado.") from e
