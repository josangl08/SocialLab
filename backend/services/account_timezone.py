"""Zona horaria efectiva de una cuenta para procesos sin navegador (AD-2, AD-15)."""
from database.supabase_client import get_supabase_admin_client
from utils.timezones import effective_timezone


def get_account_timezone(account_id: int) -> str:
    """primary_timezone ?? detected_timezone ?? 'UTC' de la cuenta indicada."""
    res = get_supabase_admin_client().table('instagram_accounts')\
        .select('primary_timezone, detected_timezone')\
        .eq('id', account_id)\
        .execute()
    return effective_timezone(res.data[0] if res.data else None)
