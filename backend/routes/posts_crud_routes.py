import uuid
import logging
from datetime import datetime
from typing import Literal, Optional
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, status

from database.supabase_client import get_supabase_client
from models.schemas import User, Post
from auth.dependencies import get_current_user

logger = logging.getLogger(__name__)
# Sin prefijo para que coincida exactamente con /posts y /posts/{post_id} que usa el frontend
router = APIRouter(tags=["Posts CRUD"])
supabase = get_supabase_client()

@router.post("/posts", response_model=Post)
async def create_post(
    content: str = Form(...),
    post_type: str = Form(...),
    status: str = Form(...),
    scheduled_at: Optional[datetime] = Form(None),
    media_file: Optional[UploadFile] = File(None),
    instagram_account_id: Optional[int] = Form(None),
    current_user: User = Depends(get_current_user)
):
    """
    Crea una nueva publicación para el usuario autenticado, con opción de subir un archivo multimedia.
    """
    media_url = None
    if media_file:
        try:
            file_extension = media_file.filename.split(".")[-1]
            folder_map = {
                'draft': 'drafts',
                'scheduled': 'scheduled',
                'published': 'published'
            }
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
            return response.data[0]
        else:
            raise HTTPException(status_code=500, detail="No se pudo crear la publicación.")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al crear la publicación: {str(e)}")

@router.get("/posts", response_model=list[Post])
async def get_posts(current_user: User = Depends(get_current_user)):
    """
    Obtiene todas las publicaciones del usuario autenticado ordenadas por fecha.
    """
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

@router.put("/posts/{post_id}", response_model=Post)
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
    """
    Actualiza una publicación existente del usuario autenticado, con opción de subir un archivo multimedia.
    """
    response = supabase.table('posts').select('id', 'media_url').eq('id', post_id).eq('user_id', current_user.id).execute()
    if not response.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Publicación no encontrada")

    existing_media_url = response.data[0].get('media_url')
    media_url = existing_media_url

    if media_file:
        try:
            if existing_media_url:
                old_file_path = existing_media_url.split('/posts/')[-1] if '/posts/' in existing_media_url else existing_media_url.split('/')[-1]
                supabase.storage.from_("posts").remove([old_file_path])

            file_extension = media_file.filename.split(".")[-1]
            folder_map = {
                'draft': 'drafts',
                'scheduled': 'scheduled',
                'published': 'published'
            }
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
        else:
            raise HTTPException(status_code=500, detail="No se pudo actualizar la publicación.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al actualizar la publicación: {str(e)}")

@router.delete("/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(post_id: int, current_user: User = Depends(get_current_user)):
    """
    Elimina una publicación del usuario autenticado.
    """
    response = supabase.table('posts').select('id', 'media_url').eq('id', post_id).eq('user_id', current_user.id).execute()
    if not response.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Publicación no encontrada")

    existing_media_url = response.data[0].get('media_url')

    try:
        if existing_media_url:
            file_path_to_delete = existing_media_url.split('/posts/')[-1] if '/posts/' in existing_media_url else existing_media_url.split('/')[-1]
            supabase.storage.from_("posts").remove([file_path_to_delete])

        supabase.table('posts').delete().eq('id', post_id).execute()
        return
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al eliminar la publicación: {str(e)}")
