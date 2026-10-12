import asyncio
import json
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import Response
from fastapi import status as http_status
from pydantic import BaseModel, Field

from auth.dependencies import (
    get_current_user,
    get_current_user_from_query_token,
    get_user_supabase_client,
    get_user_supabase_client_from_query_token,
)
from database.supabase_client import get_supabase_admin_client
from models.schemas import User, Post
from services.media_thumbnails import (
    DEFAULT_THUMBNAIL_SIZE,
    IMAGE_CACHE_HEADERS,
    ThumbnailSize,
    get_thumbnail,
)
from services.publisher.instagram_publisher import InstagramPublisher, InstagramPublishError, resolve_publish_type
from supabase import Client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/posts", tags=["posts"])

admin_supabase = get_supabase_admin_client()


CONTENT_FORMATS = ('post', 'reel', 'carousel', 'story')
TRIAL_GRADUATIONS = ('MANUAL', 'SS_PERFORMANCE')


def _structure_fields(content_format: Optional[str], content_structure: Optional[str]) -> dict:
    """Valida `content_format` y `content_structure` (JSON con slides | beats | frames) del formulario.
    Solo devuelve los campos enviados, para no borrar la estructura de un post al editar otros campos."""
    fields: dict = {}
    if content_format is not None:
        if content_format not in CONTENT_FORMATS:
            raise HTTPException(status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                                detail=f"content_format debe ser uno de {', '.join(CONTENT_FORMATS)}.")
        fields['content_format'] = content_format
    if content_structure is not None:
        try:
            parsed = json.loads(content_structure)
        except json.JSONDecodeError:
            parsed = None
        if not isinstance(parsed, dict):
            raise HTTPException(status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                                detail="content_structure debe ser un objeto JSON.")
        fields['content_structure'] = parsed
    return fields


class PublishPostRequest(BaseModel):
    # Sin valor se usa el tipo guardado en el post (resolve_publish_type)
    post_type: Optional[str] = Field(default=None)


class PublishPostResponse(BaseModel):
    success: bool
    message: str
    instagram_post_id: Optional[str] = None
    permalink: Optional[str] = None
    published_at: Optional[datetime] = None


@router.post("", response_model=Post)
def create_post(
    background_tasks: BackgroundTasks,
    content: str = Form(...),
    post_type: str = Form(...),
    status: str = Form(...),
    scheduled_at: Optional[datetime] = Form(None),
    media_file: Optional[UploadFile] = File(None),
    instagram_account_id: Optional[int] = Form(None),
    notify_telegram: bool = Form(True),
    content_format: Optional[str] = Form(None),
    content_structure: Optional[str] = Form(None),
    trial_graduation: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    supabase: Client = Depends(get_user_supabase_client)
):
    structure_fields = _structure_fields(content_format, content_structure)
    if trial_graduation is not None and trial_graduation not in TRIAL_GRADUATIONS:
        raise HTTPException(status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"trial_graduation debe ser uno de {', '.join(TRIAL_GRADUATIONS)}.")
    # Trial Reels (AD-10): solo los Reels se publican como prueba; en otros formatos se ignora
    if content_format != 'reel':
        trial_graduation = None
    if not notify_telegram and status == 'scheduled':
        if not scheduled_at:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Se requiere scheduled_at futuro para programar la publicación."
            )
        now = datetime.now(timezone.utc)
        sched_dt = scheduled_at if scheduled_at.tzinfo is not None else scheduled_at.replace(tzinfo=timezone.utc)
        if sched_dt <= now:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="La fecha scheduled_at debe ser en el futuro."
            )
        if not media_file:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Se requiere una imagen o vídeo para programar la publicación."
            )

    if instagram_account_id is not None:
        account_check = admin_supabase.table('instagram_accounts')\
            .select('id').eq('id', instagram_account_id).eq('user_id', current_user.id).execute()
        if not account_check.data:
            raise HTTPException(status_code=403, detail="No tienes permiso para usar esta cuenta de Instagram.")

    media_url = None
    if media_file:
        try:
            file_extension = media_file.filename.split(".")[-1]
            folder_map = {'draft': 'drafts', 'scheduled': 'scheduled', 'published': 'published'}
            folder = folder_map.get(status, 'drafts')
            unique_filename = f"{folder}/{uuid.uuid4()}.{file_extension}"
            file_content = media_file.file.read()
            admin_supabase.storage.from_("posts").upload(unique_filename, file_content, {"content-type": media_file.content_type})
            media_url = admin_supabase.storage.from_("posts").get_public_url(unique_filename)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error al procesar archivo multimedia: {str(e)}")

    try:
        response = supabase.table('posts').insert({
            'user_id': current_user.id,
            'content': content,
            'media_url': media_url,
            'post_type': post_type,
            'status': status,
            'scheduled_at': scheduled_at.isoformat() if scheduled_at else None,
            'instagram_account_id': instagram_account_id,
            'trial_graduation': trial_graduation,
            **structure_fields,
        }).execute()

        if response.data:
            post = response.data[0]
            if not notify_telegram and status == 'scheduled' and scheduled_at:
                from services.scheduler.post_scheduler import PostScheduler
                try:
                    PostScheduler().schedule_post(post['id'], scheduled_at)
                except Exception as e:
                    logger.warning(f"No se pudo crear APScheduler job para post {post['id']}: {e}")
            elif notify_telegram and instagram_account_id:
                account_res = admin_supabase.table('instagram_accounts')\
                    .select('telegram_chat_id').eq('id', instagram_account_id).execute()
                if account_res.data and account_res.data[0].get('telegram_chat_id'):
                    from services.telegram_service import TelegramService
                    chat_id = account_res.data[0]['telegram_chat_id']
                    background_tasks.add_task(TelegramService().send_approval_message, post['id'], chat_id, post)
            return post
        raise HTTPException(status_code=500, detail="No se pudo crear la publicación.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al crear la publicación: {str(e)}")


@router.get("", response_model=list[Post])
def get_posts(
    current_user: User = Depends(get_current_user),
    supabase: Client = Depends(get_user_supabase_client)
):
    try:
        response = (
            supabase.table('posts')
            .select('*')
            .eq('user_id', current_user.id)
            .order('publication_date', desc=True)
            .order('created_at', desc=True)
            .execute()
        )
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener las publicaciones: {str(e)}")


@router.put("/{post_id}", response_model=Post)
def update_post(
    post_id: int,
    content: str = Form(...),
    post_type: str = Form(...),
    status: str = Form(...),
    scheduled_at: Optional[datetime] = Form(None),
    media_file: Optional[UploadFile] = File(None),
    instagram_account_id: Optional[int] = Form(None),
    content_format: Optional[str] = Form(None),
    content_structure: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    supabase: Client = Depends(get_user_supabase_client)
):
    structure_fields = _structure_fields(content_format, content_structure)
    response = supabase.table('posts').select('id, media_url').eq('id', post_id).eq('user_id', current_user.id).execute()
    if not response.data:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Publicación no encontrada")

    if instagram_account_id is not None:
        account_check = admin_supabase.table('instagram_accounts')\
            .select('id').eq('id', instagram_account_id).eq('user_id', current_user.id).execute()
        if not account_check.data:
            raise HTTPException(status_code=403, detail="No tienes permiso para usar esta cuenta de Instagram.")

    existing_media_url = response.data[0].get('media_url')
    media_url = existing_media_url

    if media_file:
        try:
            if existing_media_url:
                old_file_path = existing_media_url.split('/posts/')[-1] if '/posts/' in existing_media_url else existing_media_url.split('/')[-1]
                admin_supabase.storage.from_("posts").remove([old_file_path])
            file_extension = media_file.filename.split(".")[-1]
            folder_map = {'draft': 'drafts', 'scheduled': 'scheduled', 'published': 'published'}
            folder = folder_map.get(status, 'drafts')
            unique_filename = f"{folder}/{uuid.uuid4()}.{file_extension}"
            file_content = media_file.file.read()
            admin_supabase.storage.from_("posts").upload(unique_filename, file_content, {"content-type": media_file.content_type})
            media_url = admin_supabase.storage.from_("posts").get_public_url(unique_filename)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error al procesar archivo multimedia: {str(e)}")

    try:
        update_data = {
            'content': content,
            'media_url': media_url,
            'post_type': post_type,
            'status': status,
            'scheduled_at': scheduled_at.isoformat() if scheduled_at else None,
            'instagram_account_id': instagram_account_id,
            **structure_fields,
        }
        response = supabase.table('posts').update(update_data).eq('id', post_id).execute()
        if response.data:
            if status == 'scheduled' and scheduled_at:
                from services.scheduler.post_scheduler import PostScheduler
                try:
                    PostScheduler().schedule_post(post_id, scheduled_at)
                except Exception as e:
                    logger.warning(f"No se pudo crear APScheduler job para post {post_id}: {e}")
            return response.data[0]
        raise HTTPException(status_code=500, detail="No se pudo actualizar la publicación.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al actualizar la publicación: {str(e)}")


@router.delete("/{post_id}", status_code=http_status.HTTP_204_NO_CONTENT)
def delete_post(
    post_id: int,
    current_user: User = Depends(get_current_user),
    supabase: Client = Depends(get_user_supabase_client)
):
    response = supabase.table('posts').select('id, media_url').eq('id', post_id).eq('user_id', current_user.id).execute()
    if not response.data:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Publicación no encontrada")

    existing_media_url = response.data[0].get('media_url')
    try:
        if existing_media_url:
            file_path = existing_media_url.split('/posts/')[-1] if '/posts/' in existing_media_url else existing_media_url.split('/')[-1]
            admin_supabase.storage.from_("posts").remove([file_path])
        supabase.table('posts').delete().eq('id', post_id).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al eliminar la publicación: {str(e)}")


@router.post("/{post_id}/publish", response_model=PublishPostResponse)
def publish_post_now(
    post_id: int,
    request: PublishPostRequest = PublishPostRequest(),
    current_user: User = Depends(get_current_user),
    supabase: Client = Depends(get_user_supabase_client)
):
    try:
        logger.info(f"User {current_user.id} attempting to publish post {post_id}")

        post_result = supabase.table('posts')\
            .select('*, instagram_accounts(long_lived_access_token, instagram_business_account_id)')\
            .eq('id', post_id).single().execute()

        if not post_result.data:
            raise HTTPException(status_code=404, detail=f"Post {post_id} not found")

        post = post_result.data

        if post['user_id'] != current_user.id:
            raise HTTPException(status_code=403, detail="You don't have permission to publish this post")

        if not post.get('media_url'):
            raise HTTPException(status_code=400, detail="Post must have a media_url to be published")

        if post['status'] == 'published':
            raise HTTPException(status_code=400, detail="Post is already published")

        instagram_account_id = post.get('instagram_account_id')
        if not instagram_account_id:
            raise HTTPException(status_code=400, detail="Post must be associated with an Instagram account")

        publisher = InstagramPublisher()
        publish_type = resolve_publish_type(
            {**post, 'content_format': None, 'post_type': request.post_type} if request.post_type else post
        )

        result = publisher.publish_post(
            media_url=post['media_url'],
            caption=post.get('content', ''),
            instagram_account_id=instagram_account_id,
            **publish_type,
            trial_graduation=post.get('trial_graduation')
        )

        published_at = datetime.utcnow()
        supabase.table('posts').update({
            'status': 'published',
            'instagram_post_id': result['id'],
            'publication_date': published_at.isoformat(),
        }).eq('id', post_id).execute()

        return PublishPostResponse(
            success=True,
            message='Post published successfully to Instagram',
            instagram_post_id=result['id'],
            permalink=result.get('permalink'),
            published_at=published_at
        )

    except InstagramPublishError as e:
        logger.error(f"Instagram API error publishing post {post_id}: {e}")
        raise HTTPException(status_code=502, detail=f"Instagram API error: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error publishing post {post_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to publish post: {str(e)}")


@router.get("/{post_id}/thumbnail")
async def get_post_thumbnail(
    post_id: int,
    token: str,
    size: ThumbnailSize = DEFAULT_THUMBNAIL_SIZE,
    v: Optional[str] = None,  # solo invalida la caché del navegador cuando cambia la imagen
    current_user: User = Depends(get_current_user_from_query_token),
    supabase: Client = Depends(get_user_supabase_client_from_query_token),
):
    """Miniatura JPEG de la imagen del post (Storage o Drive), autenticada por query token."""
    result = await asyncio.to_thread(
        lambda: supabase.table('posts').select('user_id, media_url, drive_file_id')
        .eq('id', post_id).limit(1).execute()
    )
    if not result.data or str(result.data[0]['user_id']) != str(current_user.id):
        raise HTTPException(status_code=404, detail=f"Post {post_id} not found")
    post = result.data[0]

    # Misma prioridad que al publicar: media_url antes que drive_file_id
    if post.get('media_url'):
        source, source_id = "storage", post['media_url']
    elif post.get('drive_file_id'):
        source, source_id = "drive", post['drive_file_id']
    else:
        raise HTTPException(status_code=404, detail="El post no tiene imagen")

    try:
        data = await get_thumbnail(source, source_id, int(size), user_id=str(current_user.id))
    except Exception as e:
        logger.error(f"Thumbnail failed for post {post_id} ({source}): {e}")
        raise HTTPException(status_code=502, detail=f"Error obteniendo la miniatura: {str(e)}")
    if data is None:
        raise HTTPException(status_code=404, detail="La media del post no tiene miniatura")
    return Response(content=data, media_type="image/jpeg", headers=IMAGE_CACHE_HEADERS)


@router.get("/{post_id}")
def get_post(
    post_id: int,
    current_user: User = Depends(get_current_user),
    supabase: Client = Depends(get_user_supabase_client)
):
    try:
        result = supabase.table('posts').select('*').eq('id', post_id).single().execute()

        if not result.data:
            raise HTTPException(status_code=404, detail=f"Post {post_id} not found")

        post = result.data
        if post['user_id'] != current_user.id:
            raise HTTPException(status_code=403, detail="You don't have permission to view this post")

        return post
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting post {post_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get post: {str(e)}")

