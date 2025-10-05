"""
Post Cleanup Service
Limpia imágenes temporales de Supabase Storage después de publicar.
"""

import logging
from typing import Dict, Optional
from database.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)


class PostCleanupService:
    """Servicio para limpiar storage temporal de posts."""

    def __init__(self):
        self.supabase = get_supabase_client()

    def cleanup_after_publish(
        self,
        post_id: int,
        instagram_url: str
    ) -> Dict:
        """
        Limpia imagen temporal después de publicar en Instagram.

        Flujo:
        1. Obtener post de DB
        2. Si tiene media_url de Supabase Storage → eliminarla
        3. Actualizar post con URL de Instagram
        4. Marcar como published

        Args:
            post_id: ID del post
            instagram_url: URL de la imagen en Instagram

        Returns:
            Diccionario con resultado
        """
        try:
            # 1. Obtener post
            post = self.supabase.table('posts').select(
                '*'
            ).eq('id', post_id).single().execute()

            if not post.data:
                logger.error(f"Post {post_id} no encontrado")
                return {
                    'success': False,
                    'error': 'Post no encontrado'
                }

            old_url = post.data.get('media_url')

            # 2. Verificar si es URL de Supabase Storage (temporal)
            is_supabase_storage = (
                old_url and
                'supabase.co/storage' in old_url and
                '/posts/' in old_url
            )

            if is_supabase_storage:
                # Extraer path del storage
                # URL: https://...supabase.co/storage/v1/object/public/posts/generated/user/file.png
                try:
                    # Obtener parte después de /posts/
                    storage_path = old_url.split('/posts/')[1]

                    # Eliminar de storage
                    self.supabase.storage.from_('posts').remove(
                        [storage_path]
                    )

                    logger.info(
                        f"🗑️  Imagen temporal eliminada: {storage_path}"
                    )
                except Exception as e:
                    logger.warning(
                        f"⚠️  No se pudo eliminar imagen temporal: {str(e)}"
                    )
                    # Continuar de todas formas

            # 3. Actualizar post con URL de Instagram
            self.supabase.table('posts').update({
                'media_url': instagram_url,
                'status': 'published'
            }).eq('id', post_id).execute()

            logger.info(
                f"✅ Post {post_id} actualizado con URL de Instagram"
            )

            return {
                'success': True,
                'old_url': old_url,
                'new_url': instagram_url,
                'cleaned': is_supabase_storage
            }

        except Exception as e:
            logger.error(f"❌ Error en cleanup: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def cleanup_old_drafts(self, days: int = 30) -> Dict:
        """
        Limpia borradores antiguos y sus imágenes temporales.

        Args:
            days: Eliminar drafts más antiguos de X días

        Returns:
            Diccionario con resultado
        """
        try:
            from datetime import datetime, timedelta

            cutoff_date = datetime.now() - timedelta(days=days)

            # Buscar drafts antiguos
            old_drafts = self.supabase.table('posts').select(
                'id, media_url'
            ).eq('status', 'draft').lt(
                'created_at',
                cutoff_date.isoformat()
            ).execute()

            if not old_drafts.data:
                logger.info("No hay drafts antiguos para limpiar")
                return {
                    'success': True,
                    'cleaned': 0
                }

            cleaned = 0

            for draft in old_drafts.data:
                media_url = draft.get('media_url')

                # Si tiene imagen en Supabase Storage, eliminarla
                if (
                    media_url and
                    'supabase.co/storage' in media_url and
                    '/posts/' in media_url
                ):
                    try:
                        storage_path = media_url.split('/posts/')[1]
                        self.supabase.storage.from_('posts').remove(
                            [storage_path]
                        )
                        cleaned += 1
                    except Exception as e:
                        logger.warning(
                            f"Error eliminando {storage_path}: {str(e)}"
                        )

                # Eliminar registro de draft
                self.supabase.table('posts').delete().eq(
                    'id',
                    draft['id']
                ).execute()

            logger.info(
                f"🗑️  {cleaned} drafts antiguos limpiados "
                f"(>{days} días)"
            )

            return {
                'success': True,
                'cleaned': cleaned
            }

        except Exception as e:
            logger.error(f"❌ Error limpiando drafts: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def get_storage_usage(self, user_id: str) -> Dict:
        """
        Obtiene estadísticas de uso de storage.

        Args:
            user_id: UUID del usuario

        Returns:
            Diccionario con estadísticas
        """
        try:
            # Contar posts con imágenes en Supabase Storage
            posts = self.supabase.table('posts').select(
                'id, media_url, status'
            ).eq('user_id', user_id).execute()

            stats = {
                'total_posts': len(posts.data),
                'in_supabase_storage': 0,
                'in_instagram': 0,
                'by_status': {
                    'draft': 0,
                    'scheduled': 0,
                    'published': 0
                }
            }

            for post in posts.data:
                media_url = post.get('media_url', '')
                status = post.get('status', 'draft')

                # Contar por ubicación
                if 'supabase.co/storage' in media_url:
                    stats['in_supabase_storage'] += 1
                elif 'cdninstagram' in media_url or 'fbcdn' in media_url:
                    stats['in_instagram'] += 1

                # Contar por estado
                stats['by_status'][status] = stats['by_status'].get(
                    status,
                    0
                ) + 1

            logger.info(
                f"📊 Storage: {stats['in_supabase_storage']} en Supabase, "
                f"{stats['in_instagram']} en Instagram"
            )

            return {
                'success': True,
                'stats': stats
            }

        except Exception as e:
            logger.error(f"❌ Error obteniendo stats: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }


def get_post_cleanup() -> PostCleanupService:
    """Factory function para obtener servicio de cleanup."""
    return PostCleanupService()


# Testing
if __name__ == '__main__':
    import sys
    from dotenv import load_dotenv

    load_dotenv()
    logging.basicConfig(level=logging.INFO)

    cleanup = get_post_cleanup()

    print("\n🧹 Test de Post Cleanup Service\n")

    # Test 1: Obtener estadísticas
    print("Test 1: Estadísticas de storage")
    result = cleanup.get_storage_usage('test-user-id')

    if result['success']:
        stats = result['stats']
        print(f"   Total posts: {stats['total_posts']}")
        print(f"   En Supabase: {stats['in_supabase_storage']}")
        print(f"   En Instagram: {stats['in_instagram']}")
        print(f"   Por estado: {stats['by_status']}")
    else:
        print(f"   Error: {result['error']}")

    # Test 2: Cleanup de drafts antiguos
    print("\nTest 2: Limpiar drafts antiguos (>30 días)")
    result = cleanup.cleanup_old_drafts(days=30)

    if result['success']:
        print(f"   ✅ Drafts eliminados: {result['cleaned']}")
    else:
        print(f"   ❌ Error: {result['error']}")
