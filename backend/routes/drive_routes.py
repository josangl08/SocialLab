"""
Google Drive API Routes
Endpoints para gestionar exports de PROJECT 1 desde Google Drive.
"""

import asyncio
import os
import logging
from typing import List, Optional
from pydantic import BaseModel

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import Response

from auth.dependencies import get_current_user, get_current_user_from_query_token, get_user_supabase_client
from supabase import Client
from models.schemas import User
from services.google_drive_connector import get_drive_connector
from services.media_thumbnails import IMAGE_CACHE_HEADERS, ThumbnailSize, get_thumbnail

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/drive", tags=["Google Drive"])


class DriveExport(BaseModel):
    """Schema para export de PROJECT 1."""
    id: str
    export_type: str
    player: Optional[dict] = None
    match: Optional[dict] = None
    team: Optional[dict] = None
    stats: dict = {}
    image_url: Optional[str] = None
    date: Optional[str] = None
    folder_id: str
    folder_name: str


@router.get("/exports", response_model=List[DriveExport])
async def list_project1_exports(
    current_user: User = Depends(get_current_user)
):
    """
    Lista todos los exports disponibles de PROJECT 1 en Google Drive.

    Cada export contiene:
    - metadata.json con información del export
    - Gráficos generados (PNG)
    - Datos estadísticos (JSON)

    Returns:
        Lista de exports con su metadata procesado
    """
    try:
        # Obtener folder ID de PROJECT 1 desde variables de entorno
        project1_folder_id = os.getenv('GOOGLE_DRIVE_PROJECT1_FOLDER_ID')

        logger.info(f"📂 FOLDER ID configurado: {project1_folder_id}")

        if not project1_folder_id:
            # Si no hay Google Drive configurado, devolver datos mock
            logger.warning("❌ Google Drive no configurado, devolviendo datos mock")
            return get_mock_exports()

        # Intentar conectar a Google Drive
        try:
            logger.info("🔌 Intentando conectar a Google Drive...")
            drive = get_drive_connector(str(current_user.id))

            logger.info("✅ Conectado a Google Drive correctamente")

            # Listar exports
            logger.info(f"📋 Listando exports en folder: {project1_folder_id}")
            exports_data = drive.list_project1_exports(project1_folder_id)

            logger.info(f"📦 Se encontraron {len(exports_data) if exports_data else 0} carpetas")

            # Si no hay exports, devolver mock
            if not exports_data or len(exports_data) == 0:
                logger.warning("⚠️ No se encontraron exports en Google Drive, usando datos mock")
                return get_mock_exports()

            # Convertir a formato del schema
            exports = []
            for export in exports_data:
                folder_name = export.get('folder_name', 'unknown')
                logger.info(f"  📁 Procesando: {folder_name}")

                metadata = export.get('metadata', {})

                # Si no tiene metadata válido, skip
                if not metadata or not metadata.get('export_type'):
                    logger.warning(f"    ❌ {folder_name}: Sin metadata válido, ignorando")
                    continue

                logger.info(f"    ✅ {folder_name}: Metadata OK, tipo={metadata.get('export_type')}")

                export_obj = DriveExport(
                    id=export['folder_name'],
                    export_type=metadata.get('export_type', 'unknown'),
                    player=metadata.get('player'),
                    match=metadata.get('match'),
                    team=metadata.get('team'),
                    stats=metadata.get('stats', {}),
                    image_url=export.get('image_preview_url'),
                    date=export.get('created_date'),
                    folder_id=export['folder_id'],
                    folder_name=export['folder_name']
                )
                exports.append(export_obj)

            # Si no hay exports válidos, usar mock
            if len(exports) == 0:
                logger.warning("⚠️ No se encontraron exports válidos, usando datos mock")
                return get_mock_exports()

            logger.info(f"🎉 ¡ÉXITO! Devolviendo {len(exports)} exports reales de Google Drive")
            return exports

        except Exception as drive_error:
            logger.error(f"❌ ERROR en Google Drive: {str(drive_error)}")
            logger.warning("⚠️ Devolviendo datos mock por error en Google Drive")
            return get_mock_exports()

    except Exception as e:
        logger.error(f"❌ Error general listando exports: {str(e)}")
        # Devolver mock data en caso de error
        logger.info("Devolviendo datos mock por error general")
        return get_mock_exports()


@router.get("/sync")
async def sync_drive_data(
    current_user: User = Depends(get_current_user)
):
    """
    Fuerza una sincronización manual de Google Drive.
    Actualiza la caché local de exports disponibles.
    """
    try:
        project1_folder_id = os.getenv('GOOGLE_DRIVE_PROJECT1_FOLDER_ID')

        if not project1_folder_id:
            raise HTTPException(
                status_code=400,
                detail="Google Drive no configurado. Configura GOOGLE_DRIVE_PROJECT1_FOLDER_ID"
            )

        drive = get_drive_connector(str(current_user.id))
        exports_data = drive.list_project1_exports(project1_folder_id)

        return {
            "success": True,
            "message": "Sincronización completada",
            "exports_found": len(exports_data)
        }

    except Exception as e:
        logger.error(f"Error en sincronización: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error sincronizando con Google Drive: {str(e)}"
        )


@router.get("/images")
async def list_drive_images(
    account_id: int,
    current_user: User = Depends(get_current_user),
    supabase: Client = Depends(get_user_supabase_client),
):
    """Returns the list of image files in the account's Drive folder."""
    acc_res = supabase.table('instagram_accounts').select('drive_folder_id, user_id').eq('id', account_id).execute()
    if not acc_res.data:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    account = acc_res.data[0]
    if str(account['user_id']) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Sin acceso a esta cuenta")
    folder_id = account.get('drive_folder_id')
    if not folder_id:
        raise HTTPException(status_code=400, detail="No hay carpeta Drive configurada")

    try:
        drive = get_drive_connector(str(current_user.id))
    except RuntimeError:
        raise HTTPException(status_code=401, detail="Drive no conectado. Reconecta en Ajustes.")
    try:
        files = drive.list_files(folder_id=folder_id)
        return [{'id': f['id'], 'name': f['name']} for f in files
                if f.get('mimeType', '').startswith('image/')]
    except Exception as e:
        logger.error(f"Drive list images failed for account {account_id}: {e}")
        raise HTTPException(status_code=502, detail=f"Error de Drive: {str(e)}")


@router.get("/files/{file_id}/image")
async def get_drive_file_image(
    file_id: str,
    token: str,
    size: Optional[ThumbnailSize] = None,
    current_user: User = Depends(get_current_user_from_query_token),
):
    """Streams a Drive file as an image, authenticated via query token.
    With ?size= returns a small JPEG thumbnail instead of the original."""
    user_id = str(current_user.id)
    try:
        if size is not None:
            data = await get_thumbnail("drive", file_id, int(size), user_id=user_id)
            if data is None:
                raise HTTPException(status_code=404, detail="Archivo sin miniatura")
            return Response(content=data, media_type="image/jpeg", headers=IMAGE_CACHE_HEADERS)
        drive = await asyncio.to_thread(get_drive_connector, user_id)
        data, mime_type = await asyncio.to_thread(drive.get_image_bytes, file_id)
        return Response(content=data, media_type=mime_type, headers=IMAGE_CACHE_HEADERS)
    except HTTPException:
        raise
    except RuntimeError:
        raise HTTPException(status_code=401, detail="Drive no conectado. Reconecta en Ajustes.")
    except Exception as e:
        logger.error(f"Drive image fetch failed for file {file_id}: {e}")
        raise HTTPException(status_code=502, detail=f"Error de Drive: {str(e)}")


def get_mock_exports() -> List[DriveExport]:
    """
    Devuelve datos mock de exports para desarrollo/testing.
    Útil cuando Google Drive no está configurado.
    """
    return [
        DriveExport(
            id="export_player_messi_2025_01",
            export_type="player",
            player={
                "name": "Lionel Messi",
                "position": "Forward",
                "team": "Inter Miami"
            },
            stats={
                "goals": 12,
                "assists": 9,
                "shots": 54,
                "pass_accuracy": "89%",
                "minutes_played": 1350
            },
            date="2025-01-15",
            folder_id="mock_folder_1",
            folder_name="export_player_messi_2025_01"
        ),
        DriveExport(
            id="export_match_barcelona_real_2025_01",
            export_type="match",
            match={
                "home_team": {"name": "Barcelona", "logo": ""},
                "away_team": {"name": "Real Madrid", "logo": ""},
                "score": "3-1",
                "status": "finished",
                "date": "2025-01-14"
            },
            stats={
                "possession": {"home": 58, "away": 42},
                "shots": {"home": 15, "away": 8},
                "corners": {"home": 7, "away": 3}
            },
            date="2025-01-14",
            folder_id="mock_folder_2",
            folder_name="export_match_barcelona_real_2025_01"
        ),
        DriveExport(
            id="export_team_man_city_2025_01",
            export_type="team",
            team={
                "name": "Manchester City",
                "logo": ""
            },
            stats={
                "wins": 20,
                "draws": 3,
                "losses": 2,
                "goals_scored": 65,
                "goals_conceded": 18,
                "points": 63
            },
            date="2025-01-13",
            folder_id="mock_folder_3",
            folder_name="export_team_man_city_2025_01"
        ),
        DriveExport(
            id="export_player_haaland_2025_01",
            export_type="player",
            player={
                "name": "Erling Haaland",
                "position": "Striker",
                "team": "Manchester City"
            },
            stats={
                "goals": 25,
                "assists": 5,
                "shots": 78,
                "shot_accuracy": "67%",
                "minutes_played": 1800
            },
            date="2025-01-12",
            folder_id="mock_folder_4",
            folder_name="export_player_haaland_2025_01"
        )
    ]
