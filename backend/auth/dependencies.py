import asyncio
import base64
import hashlib
import json
import os
import logging
import time
from typing import Dict, Optional, Tuple
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from database.supabase_client import get_supabase_client, SUPABASE_URL, SUPABASE_KEY
from models.schemas import User
from supabase import create_client, Client, ClientOptions

logger = logging.getLogger(__name__)
supabase = get_supabase_client()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Tokens ya validados contra Supabase Auth: evita una llamada de red (~350 ms) por
# petición, p. ej. en cada miniatura del calendario. Un token revocado (logout) sigue
# aceptándose como mucho TOKEN_CACHE_TTL_SECONDS.
TOKEN_CACHE_TTL_SECONDS = 60
TOKEN_CACHE_MAX_ENTRIES = 1000
_validated_tokens: Dict[str, Tuple[User, float]] = {}


async def _user_from_token(token: str) -> Optional[User]:
    """Usuario del token (validado en Supabase Auth o desde la caché); None si no es válido.
    Lanza la excepción de Supabase si la validación falla."""
    key = hashlib.sha256(token.encode()).hexdigest()
    now = time.monotonic()
    cached = _validated_tokens.get(key)
    if cached and cached[1] > now:
        return cached[0]

    # get_user es una llamada de red síncrona: en un hilo para no bloquear el event loop
    user_response = await asyncio.to_thread(supabase.auth.get_user, token)
    user_data = user_response.user
    if not user_data:
        return None
    user = User(id=user_data.id, email=user_data.email, created_at=user_data.created_at)

    if len(_validated_tokens) >= TOKEN_CACHE_MAX_ENTRIES:
        for expired in [k for k, (_, exp) in _validated_tokens.items() if exp <= now]:
            del _validated_tokens[expired]
        if len(_validated_tokens) >= TOKEN_CACHE_MAX_ENTRIES:
            del _validated_tokens[next(iter(_validated_tokens))]  # la más antigua
    ttl = min(TOKEN_CACHE_TTL_SECONDS, _seconds_until_expiry(token))
    if ttl > 0:
        _validated_tokens[key] = (user, now + ttl)
    return user


def _seconds_until_expiry(token: str) -> float:
    """Segundos hasta el `exp` del JWT (ya validado por Supabase), para no cachear más allá."""
    try:
        payload = token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        return float(claims["exp"]) - time.time()
    except Exception:
        return 0.0

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """Obtiene el usuario actual de Supabase (modelo Pydantic User) usando el token JWT."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        user = await _user_from_token(token)

        if not user:
            raise credentials_exception

        return user
    except Exception as e:
        logger.error(f"Error al obtener usuario: {e}")
        raise credentials_exception

async def get_current_user_from_query_token(token: str) -> User:
    """Obtiene el usuario actual desde un token proporcionado en el parámetro de consulta."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales desde el query token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        user = await _user_from_token(token)

        if not user:
            logger.error("❌ Token inválido: usuario no encontrado")
            raise credentials_exception

        return user
    except Exception as e:
        logger.error(f"❌ Error al autenticar usuario desde query token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado. Por favor vuelve a iniciar sesión en SocialLab.",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_user_supabase_client(token: str = Depends(oauth2_scheme)) -> Client:
    """
    Dependency that builds a fresh Supabase client scoped to the user's JWT,
    so RLS policies evaluate auth.uid() for this request. Never reuse the
    shared singleton here: mutating its postgrest headers would leak one
    user's session into other concurrent requests.
    """
    options = ClientOptions(
        postgrest_client_timeout=30,
        storage_client_timeout=30
    )
    client = create_client(SUPABASE_URL, SUPABASE_KEY, options=options)
    client.postgrest.auth(token)
    return client



async def get_user_supabase_client_from_query_token(token: str) -> Client:
    """Same as get_user_supabase_client but with the JWT from ?token= (for <img> requests,
    which cannot send an Authorization header)."""
    return await get_user_supabase_client(token)
