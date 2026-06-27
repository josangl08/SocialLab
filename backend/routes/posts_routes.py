import asyncio
import uuid
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from fastapi import status as http_status
from pydantic import BaseModel, Field

from auth.dependencies import get_current_user
from database.supabase_client import get_supabase_client, get_supabase_admin_client
from models.schemas import User, Post
from services.publisher.instagram_publisher import InstagramPublisher, InstagramPublishError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/posts", tags=["posts"])

supabase = get_supabase_client()
admin_supabase = get_supabase_admin_client()


class PublishPostRequest(BaseModel):
    post_type: Optional[str] = Field(default='FEED')


class PublishPostResponse(BaseModel):
    success: bool
    message: str
    instagram_post_id: Optional[str] = None
    permalink: Optional[str] = None
    published_at: Optional[datetime] = None


@router.post("", response_model=Post)
async def create_post(
    content: str = Form(...),
    post_type: str = Form(...),
    status: str = Form(...),
    scheduled_at: Optional[datetime] = Form(None),
    media_file: Optional[UploadFile] = File(None),
    instagram_account_id: Optional[int] = Form(None),
    current_user: User = Depends(get_current_user)
):
    media_url = None
    if media_file:
        try:
            file_extension = media_file.filename.split(".")[-1]
            folder_map = {'draft': 'drafts', 'scheduled': 'scheduled', 'published': 'published'}
            folder = folder_map.get(status, 'drafts')
            unique_filename = f"{folder}/{uuid.uuid4()}.{file_extension}"
            file_content = await media_file.read()
            supabase.storage.from_("posts").upload(unique_filename, file_content, {"content-type": media_file.content_type})
            media_url = supabase.storage.from_("posts").get_public_url(unique_filename)
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
            'instagram_account_id': instagram_account_id
        }).execute()

        if response.data:
            post = response.data[0]
            if instagram_account_id:
                account_res = admin_supabase.table('instagram_accounts')\
                    .select('telegram_chat_id').eq('id', instagram_account_id).execute()
                if account_res.data and account_res.data[0].get('telegram_chat_id'):
                    from services.telegram_service import TelegramService
                    chat_id = account_res.data[0]['telegram_chat_id']
                    asyncio.create_task(TelegramService().send_approval_message(post['id'], chat_id, post))
            return post
        raise HTTPException(status_code=500, detail="No se pudo crear la publicación.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al crear la publicación: {str(e)}")


@router.get("", response_model=list[Post])
async def get_posts(current_user: User = Depends(get_current_user)):
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
async def update_post(
    post_id: int,
    content: str = Form(...),
    post_type: str = Form(...),
    status: str = Form(...),
    scheduled_at: Optional[datetime] = Form(None),
    media_file: Optional[UploadFile] = File(None),
    instagram_account_id: Optional[int] = Form(None),
    current_user: User = Depends(get_current_user)
):
    response = supabase.table('posts').select('id, media_url').eq('id', post_id).eq('user_id', current_user.id).execute()
    if not response.data:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Publicación no encontrada")

    existing_media_url = response.data[0].get('media_url')
    media_url = existing_media_url

    if media_file:
        try:
            if existing_media_url:
                old_file_path = existing_media_url.split('/posts/')[-1] if '/posts/' in existing_media_url else existing_media_url.split('/')[-1]
                supabase.storage.from_("posts").remove([old_file_path])
            file_extension = media_file.filename.split(".")[-1]
            folder_map = {'draft': 'drafts', 'scheduled': 'scheduled', 'published': 'published'}
            folder = folder_map.get(status, 'drafts')
            unique_filename = f"{folder}/{uuid.uuid4()}.{file_extension}"
            file_content = await media_file.read()
            supabase.storage.from_("posts").upload(unique_filename, file_content, {"content-type": media_file.content_type})
            media_url = supabase.storage.from_("posts").get_public_url(unique_filename)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error al procesar archivo multimedia: {str(e)}")

    try:
        update_data = {
            'content': content,
            'media_url': media_url,
            'post_type': post_type,
            'status': status,
            'scheduled_at': scheduled_at.isoformat() if scheduled_at else None,
            'instagram_account_id': instagram_account_id
        }
        response = supabase.table('posts').update(update_data).eq('id', post_id).execute()
        if response.data:
            return response.data[0]
        raise HTTPException(status_code=500, detail="No se pudo actualizar la publicación.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al actualizar la publicación: {str(e)}")


@router.delete("/{post_id}", status_code=http_status.HTTP_204_NO_CONTENT)
async def delete_post(post_id: int, current_user: User = Depends(get_current_user)):
    response = supabase.table('posts').select('id, media_url').eq('id', post_id).eq('user_id', current_user.id).execute()
    if not response.data:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Publicación no encontrada")

    existing_media_url = response.data[0].get('media_url')
    try:
        if existing_media_url:
            file_path = existing_media_url.split('/posts/')[-1] if '/posts/' in existing_media_url else existing_media_url.split('/')[-1]
            supabase.storage.from_("posts").remove([file_path])
        supabase.table('posts').delete().eq('id', post_id).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al eliminar la publicación: {str(e)}")


@router.post("/{post_id}/publish", response_model=PublishPostResponse)
async def publish_post_now(
    post_id: int,
    request: PublishPostRequest = PublishPostRequest(),
    current_user: User = Depends(get_current_user)
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
        post_type = request.post_type or post.get('post_type', 'FEED')

        result = publisher.publish_post(
            media_url=post['media_url'],
            caption=post.get('caption', ''),
            instagram_account_id=instagram_account_id,
            post_type=post_type
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


@router.get("/{post_id}")
async def get_post(post_id: int, current_user: User = Depends(get_current_user)):
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
