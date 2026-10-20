from __future__ import annotations
import os
import time
import logging
import requests
from typing import Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks
from starlette.responses import RedirectResponse

from database.supabase_client import get_supabase_client
from database.supabase_client import get_supabase_admin_client
from models.schemas import User, InstagramAccountConfigUpdate
from auth.dependencies import get_current_user, get_current_user_from_query_token
from services.instagram_insights import InstagramInsightsService
from utils.encryption import encrypt_token, decrypt_token
from utils.oauth_state import generate_state_token, verify_state_token
from utils.graph_api import graph_url

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/instagram", tags=["Instagram Integration"])
supabase = get_supabase_client()
admin_supabase = get_supabase_admin_client()
from config import INSTAGRAM_APP_ID, INSTAGRAM_APP_SECRET, INSTAGRAM_REDIRECT_URI

@router.get("/login")
def instagram_login(
    token: str,
    account_id: Optional[str] = None,
    current_user: User = Depends(get_current_user_from_query_token)
):
    if not INSTAGRAM_APP_ID:
        raise HTTPException(status_code=500, detail="INSTAGRAM_APP_ID no configurado.")

    state_param = generate_state_token(current_user.id, account_id)

    auth_url = (
        f"https://graph.facebook.com/oauth/authorize?client_id={INSTAGRAM_APP_ID}"
        f"&redirect_uri={INSTAGRAM_REDIRECT_URI}"
        "&scope=business_management,instagram_basic,instagram_content_publish,pages_show_list,pages_read_engagement,instagram_manage_insights"
        "&response_type=code"
        f"&state={state_param}"
    )
    return RedirectResponse(auth_url)

# callback/instagram no tiene prefijo /instagram, sino /callback/instagram
# Lo registramos en un router aparte o en este router quitando la barra del prefijo para esta ruta
# Si definimos router con prefix="/instagram", podemos declarar callback/instagram en este router
# pero usando un APIRouter global sin prefijo para que coincida exactamente con la URL del callback
# declarada en Meta.
# Vamos a declarar callback en este mismo archivo, pero lo asociaremos a un router sin prefijo o
# usaremos la ruta absoluta en el APIRouter quitando el prefijo para ese endpoint.
# Para evitar problemas con el prefix de APIRouter, lo más limpio es crear un router secundario
# en este archivo o no usar prefijo a nivel de clase router y especificar los prefijos en cada método.
# Hagamos que el router no tenga prefijo de clase, y pongamos el prefijo /instagram en los métodos
# excepto en el callback. Esto es extremadamente seguro y no rompe la URL.

router_no_prefix = APIRouter(tags=["Instagram Integration"])

@router_no_prefix.get("/instagram/login")
def instagram_login_np(
    token: str,
    account_id: Optional[str] = None,
    current_user: User = Depends(get_current_user_from_query_token)
):
    if not INSTAGRAM_APP_ID:
        raise HTTPException(status_code=500, detail="INSTAGRAM_APP_ID no configurado.")
    state_param = generate_state_token(current_user.id, account_id)
    auth_url = (
        f"https://graph.facebook.com/oauth/authorize?client_id={INSTAGRAM_APP_ID}"
        f"&redirect_uri={INSTAGRAM_REDIRECT_URI}"
        "&scope=business_management,instagram_basic,instagram_content_publish,pages_show_list,pages_read_engagement,instagram_manage_insights"
        "&response_type=code"
        f"&state={state_param}"
    )
    return RedirectResponse(auth_url)

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
        sociallab_user_id = state_data["user_id"]
        target_account_id = state_data.get("account_id")
    except ValueError:
        raise HTTPException(status_code=400, detail="Parámetro state inválido o expirado.")

    if not INSTAGRAM_APP_ID or not INSTAGRAM_APP_SECRET or not INSTAGRAM_REDIRECT_URI:
        raise HTTPException(status_code=500, detail="Credenciales de Instagram no configuradas.")

    token_exchange_url = "https://graph.facebook.com/oauth/access_token"
    data = {
        'client_id': INSTAGRAM_APP_ID,
        'client_secret': INSTAGRAM_APP_SECRET,
        'grant_type': 'authorization_code',
        'redirect_uri': INSTAGRAM_REDIRECT_URI,
        'code': code,
    }
    
    try:
        response = requests.post(token_exchange_url, data=data)
        response.raise_for_status()
        token_data = response.json()
        
        short_lived_access_token = token_data.get('access_token')

        if not short_lived_access_token:
            raise HTTPException(status_code=500, detail="No se pudo obtener el token de acceso de corta duración de Instagram.")

        long_lived_token_exchange_url = "https://graph.facebook.com/oauth/access_token"
        long_lived_data = {
            'grant_type': 'fb_exchange_token',
            'client_id': INSTAGRAM_APP_ID,
            'client_secret': INSTAGRAM_APP_SECRET,
            'fb_exchange_token': short_lived_access_token
        }

        long_lived_response = requests.get(long_lived_token_exchange_url, params=long_lived_data)
        long_lived_response.raise_for_status()
        long_lived_token_data = long_lived_response.json()

        long_lived_access_token = long_lived_token_data.get('access_token')
        long_lived_expires_in = long_lived_token_data.get('expires_in')

        if not long_lived_access_token:
            raise HTTPException(status_code=500, detail="No se pudo obtener el token de acceso de larga duración de Instagram.")

        if long_lived_expires_in is None:
            long_lived_expires_in = 60 * 24 * 60 * 60
            logger.warning("'expires_in' no recibido para el token de larga duración. Usando 60 días por defecto.")

        expires_at = datetime.utcnow() + timedelta(seconds=long_lived_expires_in)

        pages_url = graph_url(f"me/accounts?access_token={long_lived_access_token}")
        pages_response = requests.get(pages_url)
        pages_response.raise_for_status()
        pages_data = pages_response.json()

        facebook_page_id = None
        if pages_data and pages_data.get('data'):
            facebook_page_id = pages_data['data'][0].get('id')

        if not facebook_page_id:
            raise HTTPException(status_code=500, detail="No se pudo obtener el ID de la página de Facebook.")

        instagram_business_account_url = graph_url(f"{facebook_page_id}?fields=instagram_business_account&access_token={long_lived_access_token}")
        instagram_account_response = requests.get(instagram_business_account_url)
        instagram_account_response.raise_for_status()
        instagram_account_data = instagram_account_response.json()

        instagram_business_account_id = None
        if instagram_account_data.get('instagram_business_account'):
            instagram_business_account_id = instagram_account_data['instagram_business_account'].get('id')

        if not instagram_business_account_id:
            raise HTTPException(status_code=500, detail="No se pudo obtener el ID de la cuenta de Instagram Business.")

        try:
            admin_supabase = get_supabase_admin_client()
            if target_account_id:
                # Reconexión de una tarjeta concreta: actualiza esa fila exacta,
                # sin importar qué instagram_business_account_id devuelva esta vez
                # Facebook — evita crear una cuenta nueva por accidente si el
                # usuario elige una página distinta en el popup de Meta.
                admin_supabase.table('instagram_accounts').update({
                    'instagram_business_account_id': instagram_business_account_id,
                    'long_lived_access_token': encrypt_token(long_lived_access_token),
                    'expires_at': expires_at.isoformat() + 'Z',
                    'token_invalid': False
                }).eq('id', target_account_id).eq('user_id', sociallab_user_id).execute()
            else:
                admin_supabase.table('instagram_accounts').upsert({
                    'user_id': sociallab_user_id,
                    'instagram_business_account_id': instagram_business_account_id,
                    'long_lived_access_token': encrypt_token(long_lived_access_token),
                    'expires_at': expires_at.isoformat() + 'Z',
                    'token_invalid': False
                }, on_conflict='user_id,instagram_business_account_id').execute()
            logger.info("Instagram account details saved to Supabase.")
        except Exception as e:
            logger.error(f"Error saving Instagram account details to Supabase: {e}")
            raise HTTPException(status_code=500, detail=f"Error al guardar los detalles de la cuenta de Instagram: {str(e)}")

        return RedirectResponse(url="http://localhost:5173/dashboard?instagram_connected=true")

    except requests.exceptions.RequestException as e:
        logger.error(f"Error durante el intercambio de tokens: {e.response.text if e.response else e}")
        raise HTTPException(status_code=500, detail=f"Error durante el proceso de autenticación de Instagram: {e}")

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
        query = admin_db.table('instagram_accounts').select('id, long_lived_access_token, instagram_business_account_id').eq('user_id', current_user.id)
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

        account_id = response.data[0]['id']
        access_token = decrypt_token(response.data[0]['long_lived_access_token'])

        user_accounts_url = graph_url(f"me/accounts?access_token={access_token}")
        user_accounts_response = requests.get(user_accounts_url)
        user_accounts_response.raise_for_status()
        user_accounts_data = user_accounts_response.json()

        if not user_accounts_data.get('data'):
            raise HTTPException(
                status_code=500,
                detail="No se encontraron páginas de Facebook asociadas a esta cuenta."
            )

        facebook_page_id = user_accounts_data['data'][0]['id']

        ig_account_url = graph_url(f"{facebook_page_id}?fields=instagram_business_account&access_token={access_token}")
        ig_account_response = requests.get(ig_account_url)
        ig_account_response.raise_for_status()
        ig_account_data = ig_account_response.json()

        if not ig_account_data.get('instagram_business_account'):
            raise HTTPException(
                status_code=500,
                detail="No se encontró una cuenta de Instagram Business asociada."
            )

        instagram_user_id = ig_account_data['instagram_business_account']['id']

        all_media = []
        next_url = graph_url(f"{instagram_user_id}/media?fields=id,caption,media_type,media_url,thumbnail_url,timestamp,permalink,media_product_type&limit=100&access_token={access_token}")

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
            InstagramInsightsService(access_token, instagram_user_id)
            .get_collaboration_post_rows(current_user.id, account_id)
        )

        admin_supabase.table('posts').upsert(
            posts_to_upsert,
            on_conflict='instagram_post_id'
        ).execute()

        profile_url = graph_url(f"{instagram_user_id}?fields=followers_count,media_count,follows_count,name,username,profile_picture_url&access_token={access_token}")
        profile_response = requests.get(profile_url)
        profile_response.raise_for_status()
        profile_data = profile_response.json()

        get_supabase_admin_client().table('instagram_accounts').update({
            'followers_count': profile_data.get('followers_count', 0),
            'username': profile_data.get('username', ''),
            'account_name': profile_data.get('name', ''),
            'profile_picture_url': profile_data.get('profile_picture_url', ''),
            'last_sync_at': datetime.utcnow().isoformat(),
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
            'posts_per_week, scheduling_mode, preferred_days, last_agent_sync'
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
        query = admin_supabase.table('instagram_accounts').select('instagram_business_account_id, long_lived_access_token, expires_at').eq('user_id', current_user.id)
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

        media_url = post.get('media_url')
        if not media_url:
            raise HTTPException(status_code=400, detail="El post debe tener una imagen o video")

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

        container_url = graph_url(f"{ig_account_id}/media")
        container_response = requests.post(container_url, data=container_params)

        if container_response.status_code != 200:
            raise HTTPException(
                status_code=500,
                detail=f"Error al crear contenedor: {container_response.json().get('error', {}).get('message', 'Error')}"
            )

        container_id = container_response.json().get('id')

        status_url = graph_url(container_id)
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

        publish_url = graph_url(f"{ig_account_id}/media_publish")
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
            'publication_date': datetime.utcnow().isoformat()
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

        if scheduled_time <= datetime.utcnow():
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
            .select('id, instagram_business_account_id, username, account_name, followers_count, profile_picture_url, expires_at, is_active, telegram_chat_id, drive_folder_id, token_invalid, sector, primary_timezone, secondary_timezone, detected_timezone')\
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
