"""
Template Sync Service
Sincroniza templates desde Google Drive → Supabase Storage + DB
"""

import logging
import os
import io
from typing import List, Dict, Optional
from database.supabase_client import (
    get_supabase_client,
    get_supabase_admin_client
)
from services.google_drive_connector import get_drive_connector

logger = logging.getLogger(__name__)


class TemplateSyncService:
    """Servicio para sincronizar templates desde Google Drive."""

    def __init__(self, use_admin=False):
        """
        Inicializa el servicio de sincronización.

        Args:
            use_admin: Si True, usa service_role key (bypass RLS).
                      Solo para scripts administrativos.
        """
        if use_admin:
            self.supabase = get_supabase_admin_client()
            logger.info("🔑 Usando admin client (service_role)")
        else:
            self.supabase = get_supabase_client()

        self.drive = get_drive_connector()
        self.templates_folder_id = os.getenv(
            'GOOGLE_DRIVE_TEMPLATES_FOLDER_ID'
        )

    def sync_templates_from_drive(self, user_id: str) -> Dict:
        """
        Sincroniza templates desde Google Drive a Supabase.

        Flujo:
        1. Lista archivos en Google Drive/TEMPLATES_SOCIALLAB/
        2. Por cada imagen PNG/JPG:
           - Descarga de Google Drive
           - Sube a Supabase Storage
           - Crea/actualiza registro en tabla templates

        Args:
            user_id: UUID del usuario

        Returns:
            Diccionario con resultado de sincronización
        """
        if not self.templates_folder_id:
            logger.error("GOOGLE_DRIVE_TEMPLATES_FOLDER_ID no configurado")
            return {
                'success': False,
                'error': 'Configuración de Google Drive faltante'
            }

        logger.info(
            f"🔄 Iniciando sincronización de templates para {user_id}"
        )

        try:
            # 1. Listar archivos de templates en Google Drive
            files = self.drive.list_files(
                folder_id=self.templates_folder_id,
                mime_type='image/png'
            )

            # También buscar JPG
            jpg_files = self.drive.list_files(
                folder_id=self.templates_folder_id,
                mime_type='image/jpeg'
            )

            all_files = files + jpg_files

            logger.info(
                f"📁 Encontrados {len(all_files)} archivos en Google Drive"
            )

            synced = []
            errors = []

            for file in all_files:
                try:
                    result = self._sync_single_template(file, user_id)
                    if result['success']:
                        synced.append(result['template'])
                    else:
                        errors.append({
                            'file': file['name'],
                            'error': result['error']
                        })
                except Exception as e:
                    logger.error(
                        f"❌ Error sincronizando {file['name']}: {str(e)}"
                    )
                    errors.append({
                        'file': file['name'],
                        'error': str(e)
                    })

            logger.info(
                f"✅ Sincronización completada: "
                f"{len(synced)} exitosos, {len(errors)} errores"
            )

            return {
                'success': True,
                'synced': len(synced),
                'errors': len(errors),
                'templates': synced,
                'error_details': errors
            }

        except Exception as e:
            logger.error(f"❌ Error en sincronización: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def _sync_single_template(
        self,
        drive_file: Dict,
        user_id: str
    ) -> Dict:
        """
        Sincroniza un template individual.

        Args:
            drive_file: Metadata del archivo de Google Drive
            user_id: UUID del usuario

        Returns:
            Resultado de sincronización
        """
        file_name = drive_file['name']
        file_id = drive_file['id']

        logger.info(f"📥 Sincronizando: {file_name}")

        try:
            # 1. Descargar archivo de Google Drive
            import tempfile

            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp_path = tmp.name

            self.drive.download_file(file_id, tmp_path)

            with open(tmp_path, 'rb') as f:
                file_bytes = f.read()

            os.unlink(tmp_path)

            # 2. Generar nombre único para Supabase
            # Formato: user_id/original_filename
            storage_path = f"{user_id}/{file_name}"

            # 3. Subir a Supabase Storage
            try:
                # Intentar subir (sobrescribe si existe)
                self.supabase.storage.from_('templates').upload(
                    storage_path,
                    file_bytes,
                    {
                        'content-type': drive_file.get('mimeType'),
                        'upsert': 'true'
                    }
                )
            except Exception as e:
                # Si falla, intentar actualizar
                logger.warning(
                    f"Upload falló, intentando update: {str(e)[:50]}"
                )
                self.supabase.storage.from_('templates').update(
                    storage_path,
                    file_bytes,
                    {'content-type': drive_file.get('mimeType')}
                )

            # 4. Obtener URL pública
            public_url = self.supabase.storage.from_(
                'templates'
            ).get_public_url(storage_path)

            # 5. Crear/actualizar registro en tabla templates
            # Buscar si ya existe template con este nombre
            existing = self.supabase.table('templates').select('id').eq(
                'user_id',
                user_id
            ).eq('name', file_name).execute()

            template_data = {
                'user_id': user_id,
                'name': file_name,
                'description': f'Sincronizado desde Google Drive',
                'image_url': public_url,
                'is_active': True,
                'priority': 50,
                'selection_rules': {},
                'template_config': {
                    'graphic_position': 'center',
                    'graphic_scale': 0.75,
                    'margin': 80
                }
            }

            if existing.data:
                # Actualizar existente
                result = self.supabase.table('templates').update(
                    template_data
                ).eq('id', existing.data[0]['id']).execute()

                logger.info(f"✅ Template actualizado: {file_name}")
            else:
                # Crear nuevo
                result = self.supabase.table('templates').insert(
                    template_data
                ).execute()

                logger.info(f"✅ Template creado: {file_name}")

            return {
                'success': True,
                'template': result.data[0] if result.data else None
            }

        except Exception as e:
            logger.error(f"❌ Error en {file_name}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def delete_template_from_storage(
        self,
        template_id: int,
        user_id: str
    ) -> bool:
        """
        Elimina template de Supabase Storage (no de DB).

        Args:
            template_id: ID del template
            user_id: UUID del usuario

        Returns:
            True si se eliminó exitosamente
        """
        try:
            # Obtener template
            template = self.supabase.table('templates').select(
                'image_url, name'
            ).eq('id', template_id).eq('user_id', user_id).single().execute()

            if not template.data:
                logger.warning(f"Template {template_id} no encontrado")
                return False

            # Extraer path del storage desde URL
            image_url = template.data['image_url']
            # URL format: https://...supabase.co/storage/v1/object/public/templates/user_id/file.png
            storage_path = f"{user_id}/{template.data['name']}"

            # Eliminar de storage
            self.supabase.storage.from_('templates').remove([storage_path])

            logger.info(f"✅ Template eliminado de storage: {storage_path}")
            return True

        except Exception as e:
            logger.error(
                f"❌ Error eliminando template de storage: {str(e)}"
            )
            return False


def get_template_sync(use_admin=False) -> TemplateSyncService:
    """
    Factory function para obtener servicio de sincronización.

    Args:
        use_admin: Si True, usa service_role key (bypass RLS)
    """
    return TemplateSyncService(use_admin=use_admin)


# Testing
if __name__ == '__main__':
    import sys
    from dotenv import load_dotenv

    load_dotenv()
    logging.basicConfig(level=logging.INFO)

    print("\n" + "🚀 "*30)
    print("SINCRONIZACIÓN DE TEMPLATES")
    print("🚀 "*30 + "\n")

    # Buscar usuario real en la base de datos
    supabase = get_supabase_client()
    user_id = None

    try:
        # Opción 1: Buscar en instagram_accounts
        logger.info("🔍 Buscando usuarios en instagram_accounts...")
        result = supabase.table('instagram_accounts').select(
            'user_id'
        ).limit(1).execute()

        if result.data:
            user_id = result.data[0]['user_id']
            logger.info(f"✅ Usuario encontrado: {user_id}")
        else:
            # Opción 2: Buscar en posts
            logger.info("🔍 Buscando usuarios en posts...")
            result = supabase.table('posts').select(
                'user_id'
            ).limit(1).execute()

            if result.data:
                user_id = result.data[0]['user_id']
                logger.info(f"✅ Usuario encontrado: {user_id}")

    except Exception as e:
        logger.error(f"❌ Error buscando usuarios: {str(e)}")

    # Si no hay usuario, mostrar instrucciones
    if not user_id:
        print("\n" + "="*60)
        print("⚠️  NO SE ENCONTRARON USUARIOS")
        print("="*60)
        print("\nPara sincronizar templates necesitas un usuario real.")
        print("\nOpciones:")
        print("\n1. Crear usuario en Supabase:")
        print("   - Ve a: Authentication > Users > Add User")
        print("   - Email: test@sociallab.com")
        print("   - Password: TestPassword123!")
        print("\n2. O ejecuta el backend y regístrate desde el frontend")
        print("\n3. Luego ejecuta este script de nuevo\n")
        sys.exit(1)

    # Test de sincronización con admin client
    sync_service = get_template_sync(use_admin=True)

    print(f"\n🔄 Iniciando sincronización de templates...\n")

    result = sync_service.sync_templates_from_drive(user_id)

    # Mostrar resultados
    print("\n" + "="*60)
    print("RESULTADOS")
    print("="*60)

    if result['success']:
        print(f"✅ Sincronización exitosa:")
        print(f"   Templates sincronizados: {result['synced']}")
        print(f"   Errores: {result['errors']}")

        if result['templates']:
            print("\n📋 Templates sincronizados:")
            for t in result['templates']:
                print(f"   - {t['name']} (ID: {t['id']})")
                print(f"     URL: {t['image_url'][:80]}...")

        if result['error_details']:
            print("\n❌ Errores:")
            for err in result['error_details']:
                print(f"   - {err['file']}: {err['error']}")
    else:
        print(f"❌ Error: {result['error']}")
