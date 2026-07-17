import os
import logging
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from database.supabase_client import get_supabase_client, SUPABASE_URL, SUPABASE_KEY
from models.schemas import User
from supabase import create_client, Client, ClientOptions

logger = logging.getLogger(__name__)
supabase = get_supabase_client()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """Obtiene el usuario actual de Supabase (modelo Pydantic User) usando el token JWT."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        user_response = supabase.auth.get_user(token)
        user_data = user_response.user

        if not user_data:
            raise credentials_exception
        
        return User(id=user_data.id, email=user_data.email, created_at=user_data.created_at)
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
        user_response = supabase.auth.get_user(token)
        user_data = user_response.user

        if not user_data:
            logger.error("❌ Token inválido: usuario no encontrado")
            raise credentials_exception

        return User(id=user_data.id, email=user_data.email, created_at=user_data.created_at)
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

