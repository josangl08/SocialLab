"""
Templates API Routes
Endpoints para gestión de templates del planificador.
"""

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import logging

from auth.jwt_handler import get_current_user
from database.supabase_client import get_supabase_client
from services.google_drive_connector import get_drive_connector
from services.image_composer import get_image_composer

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/templates", tags=["Templates"])


# Schemas
class TemplateCreate(BaseModel):
    """Schema para crear template."""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    category_id: Optional[int] = None
    instagram_account_id: Optional[int] = None
    selection_rules: Optional[dict] = None
    template_config: Optional[dict] = None
    priority: int = Field(default=50, ge=0, le=100)
    is_active: bool = True


class TemplateUpdate(BaseModel):
    """Schema para actualizar template."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    category_id: Optional[int] = None
    instagram_account_id: Optional[int] = None
    selection_rules: Optional[dict] = None
    template_config: Optional[dict] = None
    priority: Optional[int] = Field(None, ge=0, le=100)
    is_active: Optional[bool] = None


class TemplateResponse(BaseModel):
    """Schema de respuesta de template."""
    id: int
    name: str
    description: Optional[str]
    category_id: Optional[int]
    instagram_account_id: Optional[int]
    image_url: Optional[str]
    selection_rules: Optional[dict]
    template_config: Optional[dict]
    priority: int
    is_active: bool
    use_count: int
    created_at: datetime
    updated_at: datetime


# Endpoints
@router.post("/", response_model=dict)
async def create_template(
    template: TemplateCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Crea un nuevo template.

    Requiere:
    - Autenticación JWT
    - Datos del template
    """
    try:
        supabase = get_supabase_client()
        user_id = current_user['id']

        # Crear template en DB
        template_data = {
            'user_id': user_id,
            'name': template.name,
            'description': template.description,
            'category_id': template.category_id,
            'instagram_account_id': template.instagram_account_id,
            'selection_rules': template.selection_rules or {},
            'template_config': template.template_config or {},
            'priority': template.priority,
            'is_active': template.is_active,
            'use_count': 0
        }

        result = supabase.table('templates').insert(template_data).execute()

        if not result.data:
            raise HTTPException(
                status_code=500,
                detail="Error creando template"
            )

        logger.info(f"✅ Template creado: {template.name}")

        return {
            'success': True,
            'message': 'Template creado exitosamente',
            'template': result.data[0]
        }

    except Exception as e:
        logger.error(f"❌ Error creando template: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=List[TemplateResponse])
async def list_templates(
    category_id: Optional[int] = None,
    instagram_account_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Lista templates del usuario.

    Filtros opcionales:
    - category_id: Por categoría
    - instagram_account_id: Por cuenta Instagram
    - is_active: Solo activos/inactivos
    """
    try:
        supabase = get_supabase_client()
        user_id = current_user['id']

        # Query base
        query = supabase.table('templates').select('*').eq(
            'user_id',
            user_id
        )

        # Aplicar filtros
        if category_id is not None:
            query = query.eq('category_id', category_id)

        if instagram_account_id is not None:
            query = query.eq('instagram_account_id', instagram_account_id)

        if is_active is not None:
            query = query.eq('is_active', is_active)

        # Ordenar por prioridad
        query = query.order('priority', desc=True)

        result = query.execute()

        return result.data

    except Exception as e:
        logger.error(f"❌ Error listando templates: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Obtiene un template específico."""
    try:
        supabase = get_supabase_client()
        user_id = current_user['id']

        result = supabase.table('templates').select('*').eq(
            'id',
            template_id
        ).eq('user_id', user_id).execute()

        if not result.data:
            raise HTTPException(
                status_code=404,
                detail="Template no encontrado"
            )

        return result.data[0]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error obteniendo template: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{template_id}", response_model=dict)
async def update_template(
    template_id: int,
    template_update: TemplateUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Actualiza un template existente."""
    try:
        supabase = get_supabase_client()
        user_id = current_user['id']

        # Verificar que el template existe y pertenece al usuario
        existing = supabase.table('templates').select('id').eq(
            'id',
            template_id
        ).eq('user_id', user_id).execute()

        if not existing.data:
            raise HTTPException(
                status_code=404,
                detail="Template no encontrado"
            )

        # Preparar datos de actualización (solo campos no None)
        update_data = {
            k: v for k,
            v in template_update.dict().items() if v is not None
        }

        if not update_data:
            raise HTTPException(
                status_code=400,
                detail="No hay datos para actualizar"
            )

        # Actualizar
        result = supabase.table('templates').update(update_data).eq(
            'id',
            template_id
        ).execute()

        logger.info(f"✅ Template actualizado: {template_id}")

        return {
            'success': True,
            'message': 'Template actualizado exitosamente',
            'template': result.data[0] if result.data else None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error actualizando template: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{template_id}", response_model=dict)
async def delete_template(
    template_id: int,
    current_user: dict = Depends(get_current_user)
):
    """
    Elimina un template (soft delete).

    Solo lo marca como inactivo en lugar de eliminarlo físicamente.
    """
    try:
        supabase = get_supabase_client()
        user_id = current_user['id']

        # Verificar que existe
        existing = supabase.table('templates').select('id').eq(
            'id',
            template_id
        ).eq('user_id', user_id).execute()

        if not existing.data:
            raise HTTPException(
                status_code=404,
                detail="Template no encontrado"
            )

        # Soft delete: marcar como inactivo
        result = supabase.table('templates').update({
            'is_active': False
        }).eq('id', template_id).execute()

        logger.info(f"✅ Template eliminado (soft): {template_id}")

        return {
            'success': True,
            'message': 'Template eliminado exitosamente'
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error eliminando template: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{template_id}/upload-image", response_model=dict)
async def upload_template_image(
    template_id: int,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Sube imagen de template.

    Valida dimensiones y guarda en Supabase Storage.
    """
    try:
        supabase = get_supabase_client()
        user_id = current_user['id']

        # Verificar template
        template_result = supabase.table('templates').select('id').eq(
            'id',
            template_id
        ).eq('user_id', user_id).execute()

        if not template_result.data:
            raise HTTPException(
                status_code=404,
                detail="Template no encontrado"
            )

        # Leer archivo
        image_bytes = await file.read()

        # Validar imagen
        composer = get_image_composer()
        if not composer.validate_image_dimensions(image_bytes):
            raise HTTPException(
                status_code=400,
                detail="Imagen muy pequeña. Mínimo 320x320px"
            )

        # Generar nombre de archivo
        file_extension = file.filename.split('.')[-1]
        file_path = f"templates/{user_id}/{template_id}.{file_extension}"

        # Subir a Supabase Storage
        storage_result = supabase.storage.from_('templates').upload(
            file_path,
            image_bytes,
            {'content-type': file.content_type}
        )

        # Obtener URL pública
        public_url = supabase.storage.from_('templates').get_public_url(
            file_path
        )

        # Actualizar template con URL
        supabase.table('templates').update({
            'image_url': public_url
        }).eq('id', template_id).execute()

        logger.info(f"✅ Imagen subida para template {template_id}")

        return {
            'success': True,
            'message': 'Imagen subida exitosamente',
            'image_url': public_url
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error subiendo imagen: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{template_id}/preview", response_model=dict)
async def get_template_preview(
    template_id: int,
    format_type: str = 'square',
    current_user: dict = Depends(get_current_user)
):
    """
    Genera preview del template.

    Args:
    - format_type: 'square' | 'portrait' | 'story'
    """
    try:
        supabase = get_supabase_client()
        user_id = current_user['id']

        # Obtener template
        template_result = supabase.table('templates').select(
            'id, image_url'
        ).eq('id', template_id).eq('user_id', user_id).execute()

        if not template_result.data:
            raise HTTPException(
                status_code=404,
                detail="Template no encontrado"
            )

        template = template_result.data[0]

        if not template.get('image_url'):
            raise HTTPException(
                status_code=400,
                detail="Template no tiene imagen"
            )

        # TODO: Descargar imagen desde URL y generar preview
        # Por ahora retornar URL existente
        return {
            'success': True,
            'preview_url': template['image_url'],
            'format_type': format_type
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error generando preview: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/categories/list", response_model=List[dict])
async def list_template_categories(
    current_user: dict = Depends(get_current_user)
):
    """Lista categorías de templates disponibles."""
    try:
        supabase = get_supabase_client()

        result = supabase.table('template_categories').select(
            '*'
        ).order('name').execute()

        return result.data

    except Exception as e:
        logger.error(f"❌ Error listando categorías: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/categories", response_model=dict)
async def create_template_category(
    name: str,
    description: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Crea una nueva categoría de templates."""
    try:
        supabase = get_supabase_client()

        # Verificar que no existe
        existing = supabase.table('template_categories').select('id').eq(
            'name',
            name
        ).execute()

        if existing.data:
            raise HTTPException(
                status_code=400,
                detail="Categoría ya existe"
            )

        # Crear
        result = supabase.table('template_categories').insert({
            'name': name,
            'description': description
        }).execute()

        logger.info(f"✅ Categoría creada: {name}")

        return {
            'success': True,
            'message': 'Categoría creada exitosamente',
            'category': result.data[0]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error creando categoría: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
