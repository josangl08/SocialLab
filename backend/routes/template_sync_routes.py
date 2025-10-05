"""
Template Sync API Routes
Endpoints para sincronizar templates desde Google Drive.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict
from pydantic import BaseModel

from auth.jwt_handler import get_current_user
from services.template_sync import get_template_sync

router = APIRouter(prefix="/templates", tags=["Template Sync"])


class SyncResponse(BaseModel):
    """Schema de respuesta de sincronización."""
    success: bool
    synced: int
    errors: int
    message: str
    templates: list = []
    error_details: list = []


@router.post("/sync-from-drive", response_model=SyncResponse)
async def sync_templates_from_drive(
    current_user: dict = Depends(get_current_user)
):
    """
    Sincroniza templates desde Google Drive/TEMPLATES_SOCIALLAB/.

    Flujo:
    1. Lee archivos PNG/JPG de Google Drive
    2. Los sube a Supabase Storage
    3. Crea/actualiza registros en tabla templates

    Returns:
        Resultado de sincronización con detalles
    """
    try:
        user_id = current_user['id']

        sync_service = get_template_sync()
        result = sync_service.sync_templates_from_drive(user_id)

        if result['success']:
            message = (
                f"Sincronizados {result['synced']} templates. "
                f"Errores: {result['errors']}"
            )

            return SyncResponse(
                success=True,
                synced=result['synced'],
                errors=result['errors'],
                message=message,
                templates=result.get('templates', []),
                error_details=result.get('error_details', [])
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=result.get('error', 'Error en sincronización')
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error sincronizando templates: {str(e)}"
        )


@router.get("/drive-status")
async def get_drive_sync_status(
    current_user: dict = Depends(get_current_user)
):
    """
    Verifica estado de Google Drive y carpeta de templates.

    Returns:
        Estado de configuración y archivos disponibles
    """
    try:
        import os
        from services.google_drive_connector import get_drive_connector

        folder_id = os.getenv('GOOGLE_DRIVE_TEMPLATES_FOLDER_ID')

        if not folder_id:
            return {
                'configured': False,
                'error': 'GOOGLE_DRIVE_TEMPLATES_FOLDER_ID no configurado'
            }

        drive = get_drive_connector()

        # Listar archivos de templates
        files = drive.list_files(
            folder_id=folder_id,
            mime_type='image/png'
        )

        jpg_files = drive.list_files(
            folder_id=folder_id,
            mime_type='image/jpeg'
        )

        all_files = files + jpg_files

        return {
            'configured': True,
            'folder_id': folder_id,
            'total_files': len(all_files),
            'png_files': len(files),
            'jpg_files': len(jpg_files),
            'files': [
                {
                    'name': f['name'],
                    'size': f.get('size', 0),
                    'created': f.get('createdTime')
                }
                for f in all_files[:10]  # Primeros 10
            ]
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error verificando Google Drive: {str(e)}"
        )
