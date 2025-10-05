"""
JWT Handler Module
Manejo de autenticación y validación de tokens JWT.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from database.supabase_client import get_supabase_client

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


async def get_current_user(token: str = Depends(oauth2_scheme)):
    """
    Obtiene el usuario actual desde el token JWT.

    Args:
        token: Token JWT de Supabase

    Returns:
        Diccionario con datos del usuario

    Raises:
        HTTPException: Si el token es inválido
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        supabase = get_supabase_client()
        user_response = supabase.auth.get_user(token)
        user_data = user_response.user

        if not user_data:
            raise credentials_exception

        return {
            'id': user_data.id,
            'email': user_data.email,
            'created_at': user_data.created_at
        }

    except Exception as e:
        print(f"Error al obtener usuario: {e}")
        raise credentials_exception
