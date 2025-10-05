"""
PROJECT 1 Sync Service
Sincroniza exports desde PROJECT 1 (Wyscout CSV Analyzer) almacenados en Google Drive.
"""

import os
import logging
from typing import List, Dict, Optional
from datetime import datetime
from .google_drive_connector import get_drive_connector
from supabase import Client

logger = logging.getLogger(__name__)


class Project1SyncService:
    """Servicio para sincronizar datos de PROJECT 1 desde Google Drive."""

    def __init__(self, supabase_client: Client, project1_folder_id: str):
        """
        Inicializa el servicio de sincronización.

        Args:
            supabase_client: Cliente de Supabase
            project1_folder_id: ID de carpeta raíz de PROJECT 1 en Drive
        """
        self.supabase = supabase_client
        self.project1_folder_id = project1_folder_id
        self.drive = get_drive_connector()

    def list_available_exports(self) -> List[Dict]:
        """
        Lista todos los exports disponibles de PROJECT 1.

        Returns:
            Lista de exports con metadata
        """
        try:
            exports = self.drive.list_project1_exports(
                self.project1_folder_id
            )

            logger.info(f"📦 {len(exports)} exports disponibles")
            return exports

        except Exception as e:
            logger.error(f"❌ Error listando exports: {str(e)}")
            return []

    def get_export_details(self, export_folder_id: str) -> Optional[Dict]:
        """
        Obtiene detalles completos de un export específico.

        Args:
            export_folder_id: ID de la carpeta del export

        Returns:
            Diccionario con detalles del export
        """
        try:
            # Cargar metadata.json
            metadata = self.drive.download_metadata_json(export_folder_id)

            if not metadata:
                logger.warning(f"⚠️  Export sin metadata: {export_folder_id}")
                return None

            # Listar imágenes en la carpeta
            files = self.drive.list_files(
                folder_id=export_folder_id,
                mime_type="image/png"
            )

            # Construir detalles del export
            export_details = {
                'folder_id': export_folder_id,
                'metadata': metadata,
                'images': [
                    {
                        'file_id': f['id'],
                        'name': f['name'],
                        'size': f.get('size', 0),
                        'download_url': self.drive.get_file_direct_url(
                            f['id']
                        ),
                        'created_at': f.get('createdTime')
                    }
                    for f in files
                ],
                'total_images': len(files)
            }

            return export_details

        except Exception as e:
            logger.error(f"❌ Error obteniendo detalles: {str(e)}")
            return None

    def sync_new_exports(
        self,
        user_id: str,
        instagram_account_id: int
    ) -> Dict:
        """
        Sincroniza nuevos exports desde Google Drive a la cola de generación.

        Args:
            user_id: UUID del usuario
            instagram_account_id: ID de cuenta de Instagram

        Returns:
            Resumen de sincronización
        """
        try:
            # Listar exports disponibles
            exports = self.list_available_exports()

            if not exports:
                return {
                    'success': True,
                    'new_exports': 0,
                    'message': 'No hay exports disponibles'
                }

            new_count = 0
            errors = []

            for export in exports:
                if not export['has_metadata']:
                    continue

                folder_id = export['folder_id']
                metadata = export['metadata']

                # Verificar si ya existe en la cola
                existing = self.supabase.table(
                    'content_generation_queue'
                ).select('id').eq(
                    'source_data_id', folder_id
                ).execute()

                if existing.data:
                    logger.info(f"⏭️  Export ya procesado: {folder_id}")
                    continue

                # Agregar a la cola de generación
                try:
                    self.supabase.table('content_generation_queue').insert({
                        'user_id': user_id,
                        'instagram_account_id': instagram_account_id,
                        'source_data_id': folder_id,
                        'source_data_url': f"https://drive.google.com/drive/folders/{folder_id}",
                        'source_data': metadata,
                        'status': 'pending'
                    }).execute()

                    new_count += 1
                    logger.info(f"✅ Export agregado a cola: {folder_id}")

                except Exception as e:
                    error_msg = f"Error con {folder_id}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(f"❌ {error_msg}")

            return {
                'success': True,
                'new_exports': new_count,
                'total_checked': len(exports),
                'errors': errors,
                'message': f'Sincronizados {new_count} nuevos exports'
            }

        except Exception as e:
            logger.error(f"❌ Error en sincronización: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def download_export_image(
        self,
        file_id: str,
        destination_dir: str = "/tmp"
    ) -> Optional[str]:
        """
        Descarga una imagen de un export.

        Args:
            file_id: ID del archivo en Drive
            destination_dir: Directorio destino

        Returns:
            Path local del archivo descargado
        """
        try:
            filename = f"project1_export_{file_id}.png"
            destination_path = os.path.join(destination_dir, filename)

            success = self.drive.download_file(file_id, destination_path)

            if success:
                return destination_path
            return None

        except Exception as e:
            logger.error(f"❌ Error descargando imagen: {str(e)}")
            return None

    def get_export_statistics(self) -> Dict:
        """
        Obtiene estadísticas de exports procesados.

        Returns:
            Diccionario con estadísticas
        """
        try:
            # Total en cola
            queue_stats = self.supabase.table(
                'content_generation_queue'
            ).select('status', count='exact').execute()

            # Por estado
            pending = self.supabase.table(
                'content_generation_queue'
            ).select('id', count='exact').eq('status', 'pending').execute()

            processing = self.supabase.table(
                'content_generation_queue'
            ).select('id', count='exact').eq('status', 'processing').execute()

            completed = self.supabase.table(
                'content_generation_queue'
            ).select('id', count='exact').eq('status', 'completed').execute()

            failed = self.supabase.table(
                'content_generation_queue'
            ).select('id', count='exact').eq('status', 'failed').execute()

            return {
                'total_in_queue': queue_stats.count,
                'pending': pending.count,
                'processing': processing.count,
                'completed': completed.count,
                'failed': failed.count
            }

        except Exception as e:
            logger.error(f"❌ Error obteniendo estadísticas: {str(e)}")
            return {}


def get_project1_sync(
    supabase_client: Client,
    project1_folder_id: Optional[str] = None
) -> Project1SyncService:
    """
    Factory function para obtener servicio de sincronización.

    Args:
        supabase_client: Cliente de Supabase
        project1_folder_id: ID de carpeta (usa env var si no se provee)

    Returns:
        Instancia de Project1SyncService
    """
    if not project1_folder_id:
        project1_folder_id = os.getenv('GOOGLE_DRIVE_PROJECT1_FOLDER_ID')

    if not project1_folder_id:
        raise ValueError(
            "GOOGLE_DRIVE_PROJECT1_FOLDER_ID no configurado en .env"
        )

    return Project1SyncService(supabase_client, project1_folder_id)


# Testing
if __name__ == '__main__':
    from supabase import create_client
    from dotenv import load_dotenv

    load_dotenv()
    logging.basicConfig(level=logging.INFO)

    # Setup
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_KEY')
    supabase = create_client(supabase_url, supabase_key)

    # Test
    sync_service = get_project1_sync(supabase)

    print("\n📦 Listando exports disponibles...")
    exports = sync_service.list_available_exports()

    for export in exports:
        print(f"\n📁 {export['folder_name']}")
        print(f"   Created: {export['created_at']}")
        print(f"   Has metadata: {export['has_metadata']}")

    print(f"\n📊 Estadísticas de sincronización:")
    stats = sync_service.get_export_statistics()
    for key, value in stats.items():
        print(f"   {key}: {value}")
