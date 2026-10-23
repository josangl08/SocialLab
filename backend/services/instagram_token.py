"""
Tokens de las cuentas de Instagram.

Facebook Login: el token de usuario no caduca (`expires_at: 0` en debug_token):
lo que obliga a reconectar es la caducidad del acceso a datos (90 días desde el último login), que
Meta solo renueva con un nuevo login. `instagram_accounts.expires_at` guarda esa fecha.

Instagram Login: token largo de 60 días que se renueva con `ig_refresh_token` antes de caducar.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

import requests

import config
from database.supabase_client import get_supabase_admin_client
from utils.encryption import decrypt_token, encrypt_token
from utils.graph_api import GRAPH_BASE_URL, graph_base_url

logger = logging.getLogger(__name__)

# Días antes de la fecha de reconexión en los que se avisa por Telegram (el job corre a diario)
REMINDER_DAYS = (7, 3, 1)

INSTAGRAM_OAUTH_TOKEN_URL = "https://api.instagram.com/oauth/access_token"
INSTAGRAM_GRAPH_HOST = "https://graph.instagram.com"
DEFAULT_TOKEN_SECONDS = 60 * 24 * 60 * 60
# Meta solo renueva tokens con más de 24 h; a 15 días de caducar siempre se cumple
REFRESH_WINDOW_DAYS = 15


class NoLinkedInstagramAccountError(ValueError):
    """Facebook Login sin ninguna Página con cuenta profesional de Instagram vinculada."""


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
    # debug_token solo sirve para tokens de Facebook Login; las de Instagram Login se renuevan aparte
    accounts = db.table('instagram_accounts')\
        .select('id, username, long_lived_access_token, telegram_chat_id, is_active')\
        .eq('login_type', 'facebook')\
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


def exchange_code_for_account(code: str, state_data: Dict) -> None:
    """
    Callback de Instagram Login: code → token corto → token largo (60 días) → /me, y guarda la
    cuenta con login_type='instagram'. `user_id` de /me es el mismo ID que
    `instagram_business_account_id` con Facebook Login, así reconectar actualiza la misma fila.

    Raises:
        ValueError: si Instagram no devuelve token o ID de cuenta.
        requests.RequestException: si falla alguna llamada a Instagram.
    """
    response = requests.post(INSTAGRAM_OAUTH_TOKEN_URL, data={
        'client_id': config.INSTAGRAM_LOGIN_APP_ID,
        'client_secret': config.INSTAGRAM_LOGIN_APP_SECRET,
        'grant_type': 'authorization_code',
        'redirect_uri': config.INSTAGRAM_REDIRECT_URI,
        'code': code,
    }, timeout=10)
    response.raise_for_status()
    short_lived_token = response.json().get('access_token')
    if not short_lived_token:
        raise ValueError("No se pudo obtener el token de acceso de corta duración de Instagram.")

    response = requests.get(f"{INSTAGRAM_GRAPH_HOST}/access_token", params={
        'grant_type': 'ig_exchange_token',
        'client_secret': config.INSTAGRAM_LOGIN_APP_SECRET,
        'access_token': short_lived_token,
    }, timeout=10)
    response.raise_for_status()
    long_lived_data = response.json()
    long_lived_token = long_lived_data.get('access_token')
    if not long_lived_token:
        raise ValueError("No se pudo obtener el token de acceso de larga duración de Instagram.")
    expires_in = long_lived_data.get('expires_in')
    if expires_in is None:
        expires_in = DEFAULT_TOKEN_SECONDS
        logger.warning("'expires_in' no recibido para el token de larga duración. Usando 60 días por defecto.")

    response = requests.get(f"{graph_base_url('instagram')}/me", params={
        'fields': 'user_id,username,account_type',
        'access_token': long_lived_token,
    }, timeout=10)
    response.raise_for_status()
    ig_account_id = response.json().get('user_id')
    if not ig_account_id:
        raise ValueError("No se pudo obtener el ID de la cuenta profesional de Instagram.")
    ig_account_id = str(ig_account_id)

    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    _save_account(state_data, {
        'instagram_business_account_id': ig_account_id,
        'long_lived_access_token': encrypt_token(long_lived_token),
        'expires_at': expires_at.isoformat(),
        'token_invalid': False,
        'login_type': 'instagram',
    })
    logger.info(f"Cuenta de Instagram {ig_account_id} guardada con Instagram Login.")


def exchange_facebook_code_for_account(code: str, state_data: Dict) -> None:
    """
    Callback de Facebook Login: code → token corto → token largo → cuenta de Instagram de la
    primera Página con una vinculada, y guarda la cuenta con login_type='facebook'. La fecha de
    reconexión es la caducidad del acceso a datos según debug_token (AD-4).

    Raises:
        ValueError: si Facebook no devuelve token.
        NoLinkedInstagramAccountError: si ninguna Página tiene cuenta de Instagram.
        requests.RequestException: si falla alguna llamada a la Graph API.
    """
    response = requests.post(f"{GRAPH_BASE_URL}/oauth/access_token", data={
        'client_id': config.INSTAGRAM_APP_ID,
        'client_secret': config.INSTAGRAM_APP_SECRET,
        'grant_type': 'authorization_code',
        'redirect_uri': config.INSTAGRAM_REDIRECT_URI,
        'code': code,
    }, timeout=10)
    response.raise_for_status()
    short_lived_token = response.json().get('access_token')
    if not short_lived_token:
        raise ValueError("No se pudo obtener el token de acceso de corta duración de Facebook.")

    response = requests.get(f"{GRAPH_BASE_URL}/oauth/access_token", params={
        'grant_type': 'fb_exchange_token',
        'client_id': config.INSTAGRAM_APP_ID,
        'client_secret': config.INSTAGRAM_APP_SECRET,
        'fb_exchange_token': short_lived_token,
    }, timeout=10)
    response.raise_for_status()
    long_lived_data = response.json()
    long_lived_token = long_lived_data.get('access_token')
    if not long_lived_token:
        raise ValueError("No se pudo obtener el token de acceso de larga duración de Facebook.")

    expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=long_lived_data.get('expires_in') or DEFAULT_TOKEN_SECONDS
    )
    token_status = get_reconnect_deadline(long_lived_token)
    if token_status and token_status['reconnect_by']:
        expires_at = token_status['reconnect_by']

    response = requests.get(f"{GRAPH_BASE_URL}/me/accounts", params={
        'fields': 'instagram_business_account',
        'access_token': long_lived_token,
    }, timeout=10)
    response.raise_for_status()
    ig_account_id = next((
        page['instagram_business_account']['id']
        for page in response.json().get('data', []) if page.get('instagram_business_account')
    ), None)
    if not ig_account_id:
        raise NoLinkedInstagramAccountError(
            "Ninguna Página de Facebook autorizada tiene una cuenta profesional de Instagram vinculada."
        )

    _save_account(state_data, {
        'instagram_business_account_id': str(ig_account_id),
        'long_lived_access_token': encrypt_token(long_lived_token),
        'expires_at': expires_at.isoformat(),
        'token_invalid': False,
        'login_type': 'facebook',
    })
    logger.info(f"Cuenta de Instagram {ig_account_id} guardada con Facebook Login.")


def _save_account(state_data: Dict, row: Dict) -> None:
    """Reconexión (state con account_id) → actualiza esa fila exacta aunque el usuario haya
    elegido otra cuenta en la pantalla de Meta; conexión nueva → upsert por cuenta de Instagram.
    Así cambiar de tipo de login conserva la fila y sus posts."""
    sociallab_user_id = state_data['user_id']
    target_account_id = state_data.get('account_id')
    ig_account_id = row['instagram_business_account_id']
    db = get_supabase_admin_client()
    if target_account_id:
        stored = db.table('instagram_accounts').select('instagram_business_account_id')\
            .eq('id', target_account_id).eq('user_id', sociallab_user_id).execute().data or []
        if stored and stored[0].get('instagram_business_account_id') != ig_account_id:
            logger.warning(
                f"Reconexión de la cuenta {target_account_id}: Meta devolvió {ig_account_id}, "
                f"distinto del ID guardado {stored[0].get('instagram_business_account_id')}"
            )
        db.table('instagram_accounts').update(row)\
            .eq('id', target_account_id).eq('user_id', sociallab_user_id).execute()
    else:
        db.table('instagram_accounts').upsert(
            {'user_id': sociallab_user_id, **row},
            on_conflict='user_id,instagram_business_account_id'
        ).execute()


def refresh_expiring_tokens() -> Dict[str, int]:
    """
    Job diario: renueva los tokens de Instagram Login que caducan en menos de REFRESH_WINDOW_DAYS.
    Error OAuth 190 → token_invalid; error de red o 5xx → sin cambios (se reintenta mañana).
    Idempotente: una cuenta renovada sale del filtro. Un fallo en una cuenta no corta las demás.
    """
    counts = {'refreshed': 0, 'invalidated': 0, 'skipped': 0}
    db = get_supabase_admin_client()
    threshold = datetime.now(timezone.utc) + timedelta(days=REFRESH_WINDOW_DAYS)
    accounts = db.table('instagram_accounts')\
        .select('id, long_lived_access_token')\
        .eq('login_type', 'instagram')\
        .eq('token_invalid', False)\
        .eq('is_active', True)\
        .lt('expires_at', threshold.isoformat())\
        .execute().data or []

    for account in accounts:
        try:
            response = requests.get(f"{INSTAGRAM_GRAPH_HOST}/refresh_access_token", params={
                'grant_type': 'ig_refresh_token',
                'access_token': decrypt_token(account['long_lived_access_token']),
            }, timeout=10)
            data = response.json() if response.status_code < 500 else {}

            if response.status_code == 200 and data.get('access_token'):
                expires_in = data.get('expires_in') or DEFAULT_TOKEN_SECONDS
                db.table('instagram_accounts').update({
                    'long_lived_access_token': encrypt_token(data['access_token']),
                    'expires_at': (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat(),
                }).eq('id', account['id']).execute()
                counts['refreshed'] += 1
            elif (data.get('error') or {}).get('code') == 190:
                db.table('instagram_accounts').update({'token_invalid': True}).eq('id', account['id']).execute()
                counts['invalidated'] += 1
                logger.warning(f"Token de la cuenta {account['id']} rechazado por Instagram: pendiente de reconectar")
            else:
                counts['skipped'] += 1
                logger.warning(f"No se pudo renovar el token de la cuenta {account['id']}: status {response.status_code}")
        except Exception as e:
            counts['skipped'] += 1
            logger.error(f"❌ Error renovando el token de la cuenta {account.get('id')}: {e}")

    logger.info(f"Renovación de tokens de Instagram: {counts}")
    return counts
