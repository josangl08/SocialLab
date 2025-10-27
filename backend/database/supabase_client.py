"""
Supabase Client Module
Cliente Supabase centralizado para toda la aplicación.
"""

import os
import time
from pathlib import Path
from typing import Callable, Any
from supabase import create_client, Client, ClientOptions
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

# Cargar variables de entorno desde el directorio raíz del backend
backend_root = Path(__file__).parent.parent
dotenv_path = backend_root / '.env'
load_dotenv(dotenv_path=dotenv_path)

# Configuración de Supabase
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    if not dotenv_path.is_file():
        raise Exception(
            f"Error de Configuración: No se encontró el fichero .env en la ruta esperada: {dotenv_path}. "
            "Por favor, asegúrate de que el fichero existe en el directorio 'backend' y contiene las "
            "variables SUPABASE_URL y SUPABASE_KEY."
        )
    else:
        raise Exception(
            "Error de Configuración: El fichero .env fue encontrado, pero no contiene "
            "las variables SUPABASE_URL y/o SUPABASE_KEY. Por favor, verifica el contenido del fichero."
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
        # Configurar timeouts más largos y mejor manejo de conexiones
        options = ClientOptions(
            postgrest_client_timeout=30,  # 30 segundos para queries
            storage_client_timeout=30
        )
        _supabase_client = create_client(
            SUPABASE_URL,
            SUPABASE_KEY,
            options=options
        )

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
        # Configurar timeouts más largos
        options = ClientOptions(
            postgrest_client_timeout=30,
            storage_client_timeout=30
        )
        _supabase_admin_client = create_client(
            SUPABASE_URL,
            SUPABASE_SERVICE_ROLE_KEY,
            options=options
        )

    return _supabase_admin_client


def retry_on_network_error(func: Callable, max_retries: int = 3, initial_delay: float = 1.0) -> Any:
    """
    Reintenta una función en caso de errores de red transitorios.

    Args:
        func: Función a ejecutar
        max_retries: Número máximo de reintentos (default: 3)
        initial_delay: Delay inicial en segundos (default: 1.0)

    Returns:
        Resultado de la función

    Raises:
        La última excepción si todos los reintentos fallan
    """
    last_exception = None

    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            last_exception = e
            error_msg = str(e).lower()

            # Solo reintentar en errores de red transitorios
            if any(keyword in error_msg for keyword in [
                'temporarily unavailable',
                'connection reset',
                'connection refused',
                'timeout',
                'timed out'
            ]):
                if attempt < max_retries - 1:
                    delay = initial_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(
                        f"⚠️  Error de red (intento {attempt + 1}/{max_retries}), "
                        f"reintentando en {delay}s: {str(e)[:100]}"
                    )
                    time.sleep(delay)
                    continue

            # Si no es un error de red o es el último intento, lanzar
            raise

    # Si llegamos aquí, todos los reintentos fallaron
    raise last_exception
