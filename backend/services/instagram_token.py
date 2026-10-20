"""
Fecha real de reconexión de las cuentas de Instagram (AD-4).

Con Facebook Login el token de usuario no caduca (`expires_at: 0` en debug_token): lo que obliga
a reconectar es la caducidad del acceso a datos (90 días desde el último login), que Meta solo
renueva con un nuevo login. `instagram_accounts.expires_at` guarda esa fecha.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Optional

import requests

import config
from database.supabase_client import get_supabase_admin_client
from utils.encryption import decrypt_token
from utils.graph_api import GRAPH_BASE_URL

logger = logging.getLogger(__name__)

# Días antes de la fecha de reconexión en los que se avisa por Telegram (el job corre a diario)
REMINDER_DAYS = (7, 3, 1)


def get_reconnect_deadline(access_token: str) -> Optional[Dict]:
    """
    Estado del token según debug_token.

    Returns:
        {'is_valid': bool, 'reconnect_by': datetime | None} — reconnect_by es la menor de las
        caducidades distintas de 0 (token y acceso a datos). None si no se puede consultar.
    """
    try:
        response = requests.get(
            f"{GRAPH_BASE_URL}/debug_token",
            params={
                'input_token': access_token,
                'access_token': f"{config.INSTAGRAM_APP_ID}|{config.INSTAGRAM_APP_SECRET}",
            },
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()['data']
        stamps = [data.get(key) for key in ('expires_at', 'data_access_expires_at') if data.get(key)]
        return {
            'is_valid': bool(data.get('is_valid')),
            'reconnect_by': datetime.fromtimestamp(min(stamps), tz=timezone.utc) if stamps else None,
        }
    except Exception as e:
        logger.warning(f"No se pudo consultar debug_token: {e}")
        return None


def check_account_tokens() -> None:
    """Job diario: actualiza la fecha de reconexión, marca los tokens inválidos y avisa por
    Telegram a 7, 3 y 1 días. Idempotente; un fallo en una cuenta no afecta a las demás."""
    db = get_supabase_admin_client()
    accounts = db.table('instagram_accounts')\
        .select('id, username, long_lived_access_token, telegram_chat_id, is_active')\
        .execute().data or []
    today = datetime.now(timezone.utc).date()

    for account in accounts:
        if account.get('is_active') is False:
            continue
        try:
            status = get_reconnect_deadline(decrypt_token(account['long_lived_access_token']))
            if status is None:
                continue

            reconnect_by = status['reconnect_by']
            update = {}
            if not status['is_valid']:
                update['token_invalid'] = True
            if reconnect_by:
                update['expires_at'] = reconnect_by.isoformat()
            if update:
                db.table('instagram_accounts').update(update).eq('id', account['id']).execute()

            if not (status['is_valid'] and reconnect_by and account.get('telegram_chat_id')):
                continue
            days_left = (reconnect_by.date() - today).days
            if days_left in REMINDER_DAYS:
                from services.telegram_service import TelegramService
                asyncio.run(TelegramService().send_reconnect_reminder(
                    account['telegram_chat_id'], account.get('username') or '', days_left
                ))
        except Exception as e:
            logger.error(f"❌ Error comprobando el token de la cuenta {account.get('id')}: {e}")
