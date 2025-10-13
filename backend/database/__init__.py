"""
Database module - Exporta cliente de Supabase
"""
from database.supabase_client import get_supabase_client

# Exportar cliente como 'supabase' para compatibilidad
supabase = get_supabase_client()

__all__ = ['supabase', 'get_supabase_client']
