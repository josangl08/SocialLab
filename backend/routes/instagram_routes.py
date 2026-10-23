from __future__ import annotations
import os
import time
import logging
import requests
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks
from starlette.responses import RedirectResponse, JSONResponse

from database.supabase_client import get_supabase_client
from database.supabase_client import get_supabase_admin_client
from models.schemas import User, InstagramAccountConfigUpdate
from auth.dependencies import get_current_user, get_current_user_from_query_token
from services.instagram_insights import InstagramInsightsService
from services.publisher.instagram_publisher import fetch_publishing_quota
from services.instagram_token import (
    NoLinkedInstagramAccountError,
    exchange_code_for_account,
    exchange_facebook_code_for_account,
)
from utils.encryption import decrypt_token
from utils.oauth_state import generate_state_token, verify_state_token
from utils.graph_api import GRAPH_API_VERSION, LoginType, graph_base_url
import config

logger = logging.getLogger(__name__)
supabase = get_supabase_client()
admin_supabase = get_supabase_admin_client()
from utils.timezones import utc_now_naive

INSTAGRAM_LOGIN_SCOPES = (
    "instagram_business_basic,instagram_business_content_publish,"
    "instagram_business_manage_insights,instagram_business_manage_comments"
)


FACEBOOK_LOGIN_SCOPES = (
    "business_management,instagram_basic,instagram_content_publish,pages_show_list,"
    "pages_read_engagement,instagram_manage_insights,instagram_manage_comments"
)


def _build_authorize_url(login_type: LoginType, state: str) -> str:
    """URL de autorización de Instagram Login (sin Página de Facebook) o de Facebook Login
    (Página con cuenta de Instagram vinculada; da Stories y colaboraciones)."""
    if login_type == 'facebook':
        if not config.INSTAGRAM_APP_ID:
            raise HTTPException(status_code=500, detail="INSTAGRAM_APP_ID no configurado.")
        return (
            f"https://www.facebook.com/{GRAPH_API_VERSION}/dialog/oauth?client_id={config.INSTAGRAM_APP_ID}"
            f"&redirect_uri={config.INSTAGRAM_REDIRECT_URI}"
            f"&scope={FACEBOOK_LOGIN_SCOPES}"
            "&response_type=code"
            f"&state={state}"
        )
    if not config.INSTAGRAM_LOGIN_APP_ID:
        raise HTTPException(status_code=500, detail="INSTAGRAM_LOGIN_APP_ID no configurado.")
    return (
        f"https://www.instagram.com/oauth/authorize?client_id={config.INSTAGRAM_LOGIN_APP_ID}"
        f"&redirect_uri={config.INSTAGRAM_REDIRECT_URI}"
        "&response_type=code"
        f"&scope={INSTAGRAM_LOGIN_SCOPES}"
        f"&state={state}"
    )


# Sin prefijo: /callback/instagram debe coincidir exactamente con la URL registrada en Meta
router_no_prefix = APIRouter(tags=["Instagram Integration"])

@router_no_prefix.get("/instagram/login")
def instagram_login_np(
    token: str,
    account_id: Optional[str] = None,
    method: LoginType = 'instagram',
    current_user: User = Depends(get_current_user_from_query_token)
):
    state_param = generate_state_token(current_user.id, account_id, method)
    return RedirectResponse(_build_authorize_url(method, state_param))

@router_no_prefix.get("/callback/instagram")
def instagram_callback(
    code: Optional[str] = None,
    error: Optional[str] = None,
    state: Optional[str] = None
):
    if error:
        raise HTTPException(status_code=400, detail=f"Error de Instagram OAuth: {error}")
    
    if not code:
        raise HTTPException(status_code=400, detail="No se recibió el código de autorización de Instagram.")

    if not state:
        raise HTTPException(status_code=400, detail="No se recibió el ID de usuario en el parámetro state.")

    try:
        state_data = verify_state_token(state)
    except ValueError:
        raise HTTPException(status_code=400, detail="Parámetro state inválido o expirado.")

    if state_data['login_type'] == 'facebook':
        app_id, app_secret, exchange = config.INSTAGRAM_APP_ID, config.INSTAGRAM_APP_SECRET, exchange_facebook_code_for_account
    else:
        app_id, app_secret, exchange = config.INSTAGRAM_LOGIN_APP_ID, config.INSTAGRAM_LOGIN_APP_SECRET, exchange_code_for_account
    if not app_id or not app_secret or not config.INSTAGRAM_REDIRECT_URI:
        raise HTTPException(status_code=500, detail="Credenciales de Instagram no configuradas.")

    try:
        exchange(code, state_data)
    except requests.exceptions.RequestException as e:
        logger.error(f"Error durante el intercambio de tokens: {e.response.text if e.response is not None else e}")
        raise HTTPException(status_code=500, detail=f"Error durante el proceso de autenticación de Instagram: {e}")
    except NoLinkedInstagramAccountError:
        # Error del usuario, no del servidor: la página de Cuentas explica qué falta
        return RedirectResponse(url="http://localhost:5173/accounts?instagram_error=no_linked_page")
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Error saving Instagram account details to Supabase: {e}")
        raise HTTPException(status_code=500, detail=f"Error al guardar los detalles de la cuenta de Instagram: {str(e)}")

    return RedirectResponse(url="http://localhost:5173/dashboard?instagram_connected=true")

@router_no_prefix.get("/instagram/sync")
def instagram_sync(
    instagram_account_id: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """
    Sincroniza publicaciones desde Instagram a SocialLab.
    """
    logger.info(f"🔄 Sincronizando Instagram para usuario: {current_user.id}")

    account_id = None
    try:
        # Usar admin client: RLS bloquea instagram_accounts con cliente anon
        admin_db = get_supabase_admin_client()
        query = admin_db.table('instagram_accounts').select('id, long_lived_access_token, instagram_business_account_id, login_type').eq('user_id', current_user.id)
        if instagram_account_id:
            query = query.eq('id', instagram_account_id)
        else:
            query = query.eq('is_active', True)
        response = query.limit(1).execute()

        if not response.data or not response.data[0].get('long_lived_access_token'):
            raise HTTPException(
                status_code=404,
                detail="No se encontraron credenciales de Instagram para este usuario."
            )

        account = response.data[0]
        account_id = account['id']
        access_token = decrypt_token(account['long_lived_access_token'])
        instagram_user_id = account['instagram_business_account_id']
        base_url = graph_base_url(account['login_type'])

        all_media = []
        next_url = f"{base_url}/{instagram_user_id}/media?fields=id,caption,media_type,media_url,thumbnail_url,timestamp,permalink,media_product_type&limit=100&access_token={access_token}"

        logger.info("📦 Obteniendo posts de Instagram API con paginación...")
        page_count = 0

        while next_url:
            media_response = requests.get(next_url)
            media_response.raise_for_status()
            response_json = media_response.json()

            page_data = response_json.get('data', [])
            all_media.extend(page_data)
            page_count += 1

            next_url = response_json.get('paging', {}).get('next')

            if page_count >= 50:
                logger.warning("⚠️ Alcanzado límite de 50 páginas, deteniendo paginación")
                break

        media_data = all_media

        if not media_data:
            return {
                "status": "ok",
                "message": "No se encontraron publicaciones en Instagram."
            }

        posts_to_upsert = []
        for item in media_data:
            media_product_type = item.get('media_product_type', 'FEED')
            media_type = item.get('media_type', 'IMAGE').lower()

            if media_product_type == 'REELS':
                post_type = 'reel'
            elif media_product_type == 'STORY':
                post_type = 'story'
            else:
                post_type = media_type

            post_data = {
                'user_id': current_user.id,
                'instagram_post_id': item['id'],
                'content': item.get('caption', ''),
                'media_url': item.get('media_url'),
                'media_thumbnail_url': item.get('thumbnail_url'),
                'post_type': post_type,
                'status': 'published',
                'publication_date': item.get('timestamp'),
                'instagram_account_id': account_id,
                'is_collaboration': False,
            }
            posts_to_upsert.append(post_data)
        posts_to_upsert.extend(
            InstagramInsightsService(access_token, instagram_user_id, account['login_type'])
            .get_collaboration_post_rows(current_user.id, account_id)
        )

        admin_supabase.table('posts').upsert(
            posts_to_upsert,
            on_conflict='instagram_post_id'
        ).execute()

        profile_url = f"{base_url}/{instagram_user_id}?fields=followers_count,media_count,follows_count,name,username,profile_picture_url&access_token={access_token}"
        profile_response = requests.get(profile_url)
        profile_response.raise_for_status()
        profile_data = profile_response.json()

        get_supabase_admin_client().table('instagram_accounts').update({
            'followers_count': profile_data.get('followers_count', 0),
            'username': profile_data.get('username', ''),
            'account_name': profile_data.get('name', ''),
            'profile_picture_url': profile_data.get('profile_picture_url', ''),
            'last_sync_at': utc_now_naive().isoformat(),
            'token_invalid': False
        }).eq('id', account_id).execute()

        return {
            "status": "ok",
            "message": f"Sincronizadas {len(posts_to_upsert)} publicaciones.",
            "posts_synced": len(posts_to_upsert),
            "profile_updated": True,
            "followers_count": profile_data.get('followers_count', 0)
        }

    except requests.exceptions.RequestException as e:
        error_detail = str(e)
        if e.response is not None:
            error_detail = f"Status {e.response.status_code}: {e.response.text}"
        if e.response is not None and e.response.status_code in [400, 401]:
            if account_id:
                get_supabase_admin_client().table('instagram_accounts').update(
                    {'token_invalid': True}
                ).eq('id', account_id).execute()
            raise HTTPException(
                status_code=401,
                detail="El token de acceso de Instagram ha expirado. Vuelve a conectar tu cuenta."
            )
        raise HTTPException(status_code=500, detail=f"Error al comunicarse con Instagram API: {error_detail}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error durante la sincronización: {str(e)}")

@router_no_prefix.get("/instagram/status")
def instagram_status(current_user: User = Depends(get_current_user)):
    try:
        # Usar admin client: RLS bloquea instagram_accounts con cliente anon
        admin_db = get_supabase_admin_client()
        response = admin_db.table('instagram_accounts').select(
            'id, instagram_business_account_id, username, account_name, profile_picture_url, '
            'expires_at, created_at, is_active, followers_count, telegram_chat_id, drive_folder_id, '
            'account_type, sector, purpose, target_audience, style_guide, '
            'default_tone, default_language, posting_frequency, best_times, '
            'content_pillars, hashtag_strategy, reference_accounts, '
            'posts_per_week, scheduling_mode, preferred_days, last_agent_sync, login_type'
        ).eq('user_id', current_user.id).execute()

        accounts = []
        for account in (response.data or []):
            expires_at_str = account.get('expires_at')
            expired = False
            connected = True

            if expires_at_str:
                expires_at = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
                if expires_at < datetime.now(expires_at.tzinfo):
                    expired = True
                    connected = False

            accounts.append({
                'id': account.get('id'),
                'instagram_business_account_id': account.get('instagram_business_account_id'),
                'username': account.get('username'),
                'account_name': account.get('account_name'),
                'profile_picture_url': account.get('profile_picture_url'),
                'expires_at': expires_at_str,
                'created_at': account.get('created_at'),
                'is_active': account.get('is_active', True),
                'followers_count': account.get('followers_count'),
                'telegram_chat_id': account.get('telegram_chat_id'),
                'drive_folder_id': account.get('drive_folder_id'),
                'connected': connected,
                'expired': expired,
                'login_type': account.get('login_type', 'facebook'),
                # Strategy fields
                'account_type': account.get('account_type', 'personal'),
                'sector': account.get('sector'),
                'purpose': account.get('purpose'),
                'target_audience': account.get('target_audience'),
                'style_guide': account.get('style_guide'),
                'default_tone': account.get('default_tone', 'energetic'),
                'default_language': account.get('default_language', 'es'),
                'posting_frequency': account.get('posting_frequency', 'few_times_week'),
                'best_times': account.get('best_times') or ['09:00', '18:00'],
                'content_pillars': account.get('content_pillars') or [],
                'hashtag_strategy': account.get('hashtag_strategy', 'moderate'),
                'reference_accounts': account.get('reference_accounts') or [],
                'posts_per_week': account.get('posts_per_week', 3),
                'scheduling_mode': account.get('scheduling_mode', 'flexible'),
                'preferred_days': account.get('preferred_days') or [],
                'last_agent_sync': account.get('last_agent_sync'),
            })

        return accounts
    except Exception as e:
        logger.error(f"Error en instagram_status: {e}")
        return []

@router_no_prefix.post("/instagram/publish/{post_id}")
def publish_to_instagram(post_id: int, current_user: User = Depends(get_current_user)):
    try:
        post_response = supabase.table('posts').select('*').eq('id', post_id).eq('user_id', current_user.id).single().execute()

        if not post_response.data:
            raise HTTPException(status_code=404, detail="Post no encontrado")

        post = post_response.data

        if post.get('instagram_post_id'):
            raise HTTPException(status_code=400, detail="Este post ya está publicado en Instagram")

        post_account_id = post.get('instagram_account_id')
        query = admin_supabase.table('instagram_accounts').select('instagram_business_account_id, long_lived_access_token, expires_at, login_type').eq('user_id', current_user.id)
        if post_account_id:
            query = query.eq('id', post_account_id)
        else:
            query = query.eq('is_active', True)
        ig_response = query.limit(1).execute()

        if not ig_response.data:
            raise HTTPException(status_code=400, detail="No hay cuenta de Instagram conectada")

        ig_data = ig_response.data[0]

        expires_at_str = ig_data.get('expires_at')
        if expires_at_str:
            expires_at = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
            if expires_at < datetime.now(expires_at.tzinfo):
                raise HTTPException(status_code=401, detail="El token de Instagram ha expirado. Vuelve a conectar esta cuenta.")

        ig_account_id = ig_data['instagram_business_account_id']
        access_token = decrypt_token(ig_data['long_lived_access_token'])
        base_url = graph_base_url(ig_data['login_type'])

        media_url = post.get('media_url')
        if not media_url:
            raise HTTPException(status_code=400, detail="El post debe tener una imagen o video")

        # Cupo de Instagram (100 posts/24 h); si no se puede consultar se publica igual
        quota = fetch_publishing_quota(ig_account_id, access_token, base_url)
        if quota and quota['quota_usage'] >= quota['quota_total']:
            # Respuesta directa: HTTPException anidaría el código dentro de "detail"
            return JSONResponse(status_code=429, content={
                "detail": "Se ha alcanzado el límite diario de publicaciones de Instagram (100 en 24 h). Inténtalo más tarde.",
                "code": "PUBLISH_QUOTA_EXCEEDED",
            })

        post_type = post.get('post_type', 'image').lower()
        media_type = 'VIDEO' if post_type in ['video', 'reel'] else 'IMAGE'

        container_params = {
            'access_token': access_token,
            'caption': post.get('content', ''),
        }

        if media_type == 'IMAGE':
            container_params['image_url'] = media_url
        else:
            container_params['video_url'] = media_url
            container_params['media_type'] = 'REELS' if post_type == 'reel' else 'VIDEO'

        container_url = f"{base_url}/{ig_account_id}/media"
        container_response = requests.post(container_url, data=container_params)

        if container_response.status_code != 200:
            raise HTTPException(
                status_code=500,
                detail=f"Error al crear contenedor: {container_response.json().get('error', {}).get('message', 'Error')}"
            )

        container_id = container_response.json().get('id')

        status_url = f"{base_url}/{container_id}"
        status_params = {'fields': 'status_code', 'access_token': access_token}

        max_attempts = 10
        for _ in range(max_attempts):
            status_response = requests.get(status_url, params=status_params)
            if status_response.status_code == 200:
                status_code = status_response.json().get('status_code')
                if status_code == 'FINISHED':
                    break
                elif status_code == 'ERROR':
                    raise HTTPException(status_code=500, detail="Error al procesar media en Instagram")
            time.sleep(2)

        publish_url = f"{base_url}/{ig_account_id}/media_publish"
        publish_params = {'creation_id': container_id, 'access_token': access_token}

        publish_response = requests.post(publish_url, data=publish_params)

        if publish_response.status_code != 200:
            raise HTTPException(
                status_code=500,
                detail=f"Error al publicar en Instagram: {publish_response.json().get('error', {}).get('message', 'Error')}"
            )

        instagram_post_id = publish_response.json().get('id')

        supabase.table('posts').update({
            'instagram_post_id': instagram_post_id,
            'status': 'published',
            'publication_date': utc_now_naive().isoformat()
        }).eq('id', post_id).execute()

        return {
            "success": True,
            "instagram_post_id": instagram_post_id,
            "message": "Post publicado exitosamente en Instagram"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al publicar en Instagram: {str(e)}")

@router_no_prefix.post("/instagram/schedule/{post_id}")
def schedule_instagram_post(
    post_id: int,
    scheduled_time: datetime,
    current_user: User = Depends(get_current_user)
):
    try:
        post_response = supabase.table('posts').select('*').eq('id', post_id).eq('user_id', current_user.id).single().execute()

        if not post_response.data:
            raise HTTPException(status_code=404, detail="Post no encontrado")

        post = post_response.data

        if post.get('instagram_post_id'):
            raise HTTPException(status_code=400, detail="Este post ya está publicado en Instagram")

        if scheduled_time <= utc_now_naive():
            raise HTTPException(status_code=400, detail="La fecha programada debe ser en el futuro")

        supabase.table('posts').update({
            'scheduled_at': scheduled_time.isoformat(),
            'status': 'scheduled'
        }).eq('id', post_id).execute()

        return {
            "success": True,
            "message": f"Post programado para {scheduled_time.isoformat()}",
            "scheduled_time": scheduled_time.isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al programar post: {str(e)}")

@router_no_prefix.get("/instagram/scheduled-posts")
def get_scheduled_posts(current_user: User = Depends(get_current_user)):
    try:
        response = supabase.table('posts').select('*').eq('user_id', current_user.id).eq('status', 'scheduled').not_.is_('scheduled_at', 'null').order('scheduled_at', desc=False).execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener posts programados: {str(e)}")

@router_no_prefix.get("/instagram/accounts")
def get_instagram_accounts(current_user: User = Depends(get_current_user)):
    """
    Retorna la lista de cuentas de Instagram conectadas del usuario autenticado.
    """
    try:
        response = admin_supabase.table('instagram_accounts')\
            .select('id, instagram_business_account_id, username, account_name, followers_count, profile_picture_url, expires_at, is_active, telegram_chat_id, drive_folder_id, token_invalid, sector, primary_timezone, secondary_timezone, detected_timezone, login_type')\
            .eq('user_id', current_user.id)\
            .execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener las cuentas de Instagram: {str(e)}")

@router_no_prefix.put("/instagram/accounts/{account_id}/config")
def update_account_config(
    account_id: str,
    config: InstagramAccountConfigUpdate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    existing = admin_supabase.table('instagram_accounts').select('id').eq('id', account_id).eq('user_id', current_user.id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")

    update_data = {k: v for k, v in config.model_dump().items() if v is not None}
    # Las zonas aceptan null explícito para volver a "navegador" / quitar la secundaria
    for field in ('primary_timezone', 'secondary_timezone', 'detected_timezone'):
        if field in config.model_fields_set:
            update_data[field] = getattr(config, field)
    if update_data:
        admin_supabase.table('instagram_accounts').update(update_data).eq('id', account_id).execute()

    if update_data.get('drive_folder_id'):
        from services.drive_webhook_service import register_channel
        background_tasks.add_task(register_channel, int(account_id), update_data['drive_folder_id'])

    return {"success": True}

@router_no_prefix.delete("/instagram/accounts/{account_id}")
def disconnect_account(
    account_id: str,
    current_user: User = Depends(get_current_user)
):
    existing = admin_supabase.table('instagram_accounts').select('id').eq('id', account_id).eq('user_id', current_user.id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")

    admin_supabase.table('instagram_accounts').delete().eq('id', account_id).execute()
    return {"success": True}
