"""
Supabase Client Module
Cliente Supabase centralizado para toda la aplicación.
"""

import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# Configuración de Supabase
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception(
        "Error: Las variables de entorno SUPABASE_URL y "
        "SUPABASE_KEY son necesarias."
    )

# Clientes globales
_supabase_client: Client = None
_supabase_admin_client: Client = None


def get_supabase_client() -> Client:
    """
    Obtiene instancia singleton del cliente Supabase (anon key).
    Usar para operaciones del frontend/usuario.

    Returns:
        Cliente Supabase configurado con anon key
    """
    global _supabase_client

    if _supabase_client is None:
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)

    return _supabase_client


def get_supabase_admin_client() -> Client:
    """
    Obtiene instancia singleton del cliente Supabase (service_role key).
    Usar SOLO para operaciones administrativas que necesitan bypass RLS.

    IMPORTANTE: Esta key bypasea todas las políticas de seguridad.
    No usar en endpoints públicos.

    Returns:
        Cliente Supabase configurado con service_role key
    """
    global _supabase_admin_client

    if not SUPABASE_SERVICE_ROLE_KEY:
        raise Exception(
            "Error: SUPABASE_SERVICE_ROLE_KEY no está configurada. "
            "Necesaria para operaciones administrativas."
        )

    if _supabase_admin_client is None:
        _supabase_admin_client = create_client(
            SUPABASE_URL,
            SUPABASE_SERVICE_ROLE_KEY
        )

    return _supabase_admin_client
