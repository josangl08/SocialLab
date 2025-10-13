"""
Servicio para obtener insights de Instagram Graph API
"""
import logging
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from fastapi import HTTPException

logger = logging.getLogger(__name__)


class InstagramInsightsService:
    """Servicio para interactuar con Instagram Graph API y obtener insights"""

    BASE_URL = "https://graph.facebook.com/v19.0"

    def __init__(self, access_token: str, instagram_account_id: str):
        self.access_token = access_token
        self.instagram_account_id = instagram_account_id

    def _make_request(self, endpoint: str, params: Dict = None) -> Dict:
        """Hacer petición a Instagram Graph API"""
        if params is None:
            params = {}

        params['access_token'] = self.access_token
        url = f"{self.BASE_URL}/{endpoint}"

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            return data
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error en petición a Instagram API: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error al obtener datos de Instagram: {str(e)}"
            )

    def get_account_insights(self, period: str = "day", metrics: List[str] = None) -> Dict:
        """
        Obtener insights de la cuenta de Instagram

        Args:
            period: 'day', 'week', 'days_28'
            metrics: Lista de métricas a obtener

        Returns:
            Dict con los insights
        """
        insights = {}

        valid_period_metrics = [
            'reach',
            'accounts_engaged',
            'total_interactions',
        ]

        if metrics is None:
            metrics = valid_period_metrics
        else:
            metrics = [m for m in metrics if m in valid_period_metrics]

        # Métricas que no son compatibles con 'days_28'
        # Estas métricas solo soportan 'day' period
        days_28_incompatible = ['reach', 'accounts_engaged', 'total_interactions']
        
        compatible_metrics = []
        incompatible_metrics_to_fetch = []

        if period == 'days_28':
            for metric in metrics:
                if metric in days_28_incompatible:
                    incompatible_metrics_to_fetch.append(metric)
                else:
                    compatible_metrics.append(metric)
        else:
            compatible_metrics = metrics

        # 1. Petición para métricas incompatibles con 'days_28', usando 'day'
        if incompatible_metrics_to_fetch:
            try:
                metrics_str = ','.join(incompatible_metrics_to_fetch)
                endpoint = f"{self.instagram_account_id}/insights"
                params = {
                    'metric': metrics_str,
                    'period': 'day',  # Usar período compatible
                    'metric_type': 'total_value'
                }
                data = self._make_request(endpoint, params)
                for item in data.get('data', []):
                    metric_name = item.get('name')
                    values = item.get('values', [])
                    if values:
                        insights[metric_name] = values[-1].get('value', 0)
            except HTTPException as e:
                logger.warning(f"⚠️  No se pudieron obtener métricas ('day'): {e.detail}")

        # 2. Petición para métricas compatibles con el período original
        if compatible_metrics:
            try:
                metrics_str = ','.join(compatible_metrics)
                endpoint = f"{self.instagram_account_id}/insights"
                params = {
                    'metric': metrics_str,
                    'period': period,
                    'metric_type': 'total_value'
                }
                data = self._make_request(endpoint, params)
                for item in data.get('data', []):
                    metric_name = item.get('name')
                    values = item.get('values', [])
                    if values:
                        insights[metric_name] = values[-1].get('value', 0)
            except HTTPException as e:
                logger.warning(f"⚠️  No se pudieron obtener métricas ('{period}'): {e.detail}")

        # Obtener datos del perfil (campos que no requieren periodo)
        try:
            profile_endpoint = f"{self.instagram_account_id}"
            profile_params = {
                'fields': 'followers_count,media_count,follows_count,name,username,profile_picture_url'
            }
            profile_data = self._make_request(profile_endpoint, profile_params)
            insights['follower_count'] = profile_data.get('followers_count', 0)
            insights['media_count'] = profile_data.get('media_count', 0)
            insights['follows_count'] = profile_data.get('follows_count', 0)
        except Exception as e:
            logger.warning(f"⚠️  No se pudieron obtener datos del perfil: {e}")
            insights['follower_count'] = 0
            insights['media_count'] = 0

        # Nota: profile_views no está disponible como campo del perfil
        # y no acepta el parámetro period en insights
        # Por lo tanto, lo establecemos en 0 para evitar errores en el frontend
        if 'profile_views' not in insights:
            insights['profile_views'] = 0

        return insights

    def get_media_list(self, limit: int = 25) -> List[Dict]:
        """
        Obtener lista de posts publicados

        Args:
            limit: Número de posts a obtener (default 25, max 100 por petición)
            NOTA: Instagram Graph API usa paginación. Este método obtiene solo
            la primera página de resultados.

        Returns:
            Lista de posts con información básica
        """
        endpoint = f"{self.instagram_account_id}/media"
        params = {
            'fields': 'id,caption,media_type,media_url,permalink,timestamp,like_count,comments_count',
            'limit': min(limit, 100)  # Instagram API max is 100 per request
        }

        data = self._make_request(endpoint, params)
        posts = data.get('data', [])
        return posts

    def get_media_insights(self, media_id: str) -> Dict:
        """
        Obtener insights de un post específico

        Args:
            media_id: ID del post de Instagram

        Returns:
            Dict con métricas del post
        """
        endpoint = f"{media_id}/insights"

        # Métricas válidas según Instagram Graph API oficial
        # Docs: https://developers.facebook.com/docs/instagram-platform/reference/instagram-media/insights/
        metrics = [
            'reach',          # Unique accounts that viewed the media
            'saved',          # Number of saves
            'total_interactions',  # Sum of likes, comments, saves, shares
            'views'           # Total views (for videos/reels)
        ]

        params = {
            'metric': ','.join(metrics)
        }

        data = self._make_request(endpoint, params)

        # Formatear respuesta
        insights = {}
        for item in data.get('data', []):
            metric_name = item.get('name')
            values = item.get('values', [])
            if values:
                insights[metric_name] = values[0].get('value', 0)

        # Mapear total_interactions a engagement para compatibilidad
        if 'total_interactions' in insights:
            insights['engagement'] = insights['total_interactions']

        # Mapear views a impressions para compatibilidad (aproximación)
        if 'views' in insights and 'impressions' not in insights:
            insights['impressions'] = insights['views']
        elif 'reach' in insights and 'impressions' not in insights:
            insights['impressions'] = insights['reach']

        return insights

    def get_top_posts(self, limit: int = 10) -> List[Dict]:
        """
        Obtener los posts con mejor engagement
        Args:
            limit: Número de top posts a retornar
        Returns:
            Lista de posts ordenados por engagement
        """
        # Limitar a 25 posts para evitar rate limiting al pedir insights
        posts = self.get_media_list(limit=25)

        # Calcular engagement directamente desde la lista de media
        posts_with_engagement = []
        for post in posts:
            likes = post.get('like_count', 0)
            comments = post.get('comments_count', 0)
            engagement = likes + comments

            post_data = {
                'id': post['id'],
                'caption': post.get('caption', '')[:100],
                'media_url': post.get('media_url', ''),
                'permalink': post.get('permalink', ''),
                'timestamp': post.get('timestamp', ''),
                'likes': likes,
                'comments': comments,
                'engagement': engagement,
                'impressions': 0,  # No se puede obtener sin una llamada extra
                'reach': 0,        # No se puede obtener sin una llamada extra
                'saved': 0         # No se puede obtener sin una llamada extra
            }
            posts_with_engagement.append(post_data)

        # Ordenar por engagement
        posts_with_engagement.sort(key=lambda x: x['engagement'], reverse=True)

        return posts_with_engagement[:limit]

    def analyze_best_posting_times(self, days_back: int = 30) -> List[Dict]:
        """
        Analizar mejores horarios para publicar basándose en engagement histórico

        Args:
            days_back: Días hacia atrás para analizar

        Returns:
            Lista de horarios con promedio de engagement
        """
        # Limitar a 50 posts para evitar rate limiting
        posts = self.get_media_list(limit=min(50, 100))

        # Agrupar posts por hora del día
        hourly_engagement = {}
        hourly_count = {}

        for post in posts:
            try:
                # Parsear timestamp
                timestamp_str = post.get('timestamp', '')
                if not timestamp_str:
                    continue

                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))

                # Verificar si está dentro del rango de días
                if (datetime.now(timestamp.tzinfo) - timestamp).days > days_back:
                    continue

                hour = timestamp.hour

                # Usar datos ya disponibles: likes + comments como engagement
                likes = post.get('like_count', 0)
                comments = post.get('comments_count', 0)
                engagement = likes + comments

                # Acumular por hora
                if hour not in hourly_engagement:
                    hourly_engagement[hour] = 0
                    hourly_count[hour] = 0

                hourly_engagement[hour] += engagement
                hourly_count[hour] += 1

            except Exception as e:
                logger.warning(f"⚠️  Error procesando post para análisis de horarios: {e}")
                continue

        # Calcular promedios
        best_times = []
        for hour in sorted(hourly_engagement.keys()):
            avg_engagement = hourly_engagement[hour] / hourly_count[hour]
            best_times.append({
                'hour': f"{hour:02d}:00",
                'avg_engagement_rate': round(avg_engagement, 2),
                'posts_count': hourly_count[hour]
            })

        # Ordenar por engagement
        best_times.sort(key=lambda x: x['avg_engagement_rate'], reverse=True)

        return best_times

    def get_engagement_trend(self, days: int = 7) -> List[Dict]:
        """
        Obtener tendencia de engagement de los últimos días

        Args:
            days: Número de días hacia atrás

        Returns:
            Lista con engagement por día
        """
        # Limitar a 50 posts para evitar rate limiting
        posts = self.get_media_list(limit=min(50, 100))

        # Agrupar por día
        daily_engagement = {}

        cutoff_date = datetime.now() - timedelta(days=days)

        for post in posts:
            try:
                timestamp_str = post.get('timestamp', '')
                if not timestamp_str:
                    continue

                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))

                # Verificar si está dentro del rango
                if timestamp.replace(tzinfo=None) < cutoff_date:
                    continue

                date_key = timestamp.strftime('%Y-%m-%d')

                # Usar datos ya disponibles en lugar de hacer peticiones adicionales
                likes = post.get('like_count', 0)
                comments = post.get('comments_count', 0)
                # Calcular engagement básico: likes + comments
                engagement = likes + comments

                if date_key not in daily_engagement:
                    daily_engagement[date_key] = {
                        'date': date_key,
                        'likes': 0,
                        'comments': 0,
                        'engagement': 0,
                        'posts_count': 0
                    }

                daily_engagement[date_key]['likes'] += likes
                daily_engagement[date_key]['comments'] += comments
                daily_engagement[date_key]['engagement'] += engagement
                daily_engagement[date_key]['posts_count'] += 1

            except Exception as e:
                logger.warning(f"⚠️  Error procesando post para tendencia: {e}")
                continue

        # Convertir a lista y ordenar por fecha
        trend = sorted(daily_engagement.values(), key=lambda x: x['date'])

        return trend

    def _get_all_media_paginated(self) -> List[Dict]:
        """
        Obtiene toda la media de una cuenta, manejando paginación.
        """
        all_media = []
        endpoint = f"{self.instagram_account_id}/media"
        params = {
            'fields': 'id,caption,media_type,media_url,permalink,timestamp,like_count,comments_count',
            'limit': 100  # Usar el límite máximo por página
        }

        while endpoint:
            try:
                data = self._make_request(endpoint, params if not all_media else {})
                media = data.get('data', [])
                all_media.extend(media)
                
                # Obtener la URL de la siguiente página
                endpoint = data.get('paging', {}).get('next')
                # Los parámetros ya vienen en la URL de paginación
                params = {}

            except Exception as e:
                logger.error(f"❌ Error durante la paginación de media: {e}")
                break # Salir del bucle en caso de error
        return all_media

    def sync_posts_to_database(self, db_client, user_id: str, instagram_account_id_db: int):
        """
        Sincroniza todos los posts y su performance desde Instagram a la BD de Supabase.
        """
        logger.info("🚀 Iniciando sincronización con Instagram...")
        
        # 1. Obtener todos los posts de la API de Instagram
        all_posts_from_api = self._get_all_media_paginated()

        if not all_posts_from_api:
            logger.warning("⚠️  No se encontraron posts en la API para sincronizar.")
            return

        # 2. Preparar los datos para las tablas `posts` y `post_performance`
        posts_to_upsert = []
        performance_to_upsert = []

        for post_data in all_posts_from_api:
            # Datos para la tabla `posts`
            posts_to_upsert.append({
                'user_id': user_id,
                'instagram_account_id': instagram_account_id_db,
                'instagram_post_id': post_data['id'],
                'content': post_data.get('caption', ''),
                'media_url': post_data.get('media_url'),
                'post_type': post_data.get('media_type'),
                'publication_date': post_data.get('timestamp'),
                'status': 'published',
            })

        # 3. Upsert en la tabla `posts`
        try:
            post_response = db_client.table('posts').upsert(posts_to_upsert, on_conflict='instagram_post_id').execute()
            if not post_response.data:
                logger.error(f"❌ Error en el upsert de posts: {post_response.error}")
                # No continuar si el upsert de posts falla
                return

            # Mapear instagram_post_id a nuestro post.id interno para la FK
            db_posts = {p['instagram_post_id']: p['id'] for p in post_response.data}

            # 4. Obtener insights y preparar datos para `post_performance`
            for post_data in all_posts_from_api:
                instagram_post_id = post_data['id']
                if instagram_post_id not in db_posts:
                    continue

                internal_post_id = db_posts[instagram_post_id]
                
                # Obtener insights para este post
                try:
                    insights = self.get_media_insights(instagram_post_id)
                    
                    performance_to_upsert.append({
                        'post_id': internal_post_id,
                        'likes': post_data.get('like_count', 0),
                        'comments': post_data.get('comments_count', 0),
                        'shares': insights.get('shares', 0), # No disponible directamente
                        'saves': insights.get('saved', 0),
                        'reach': insights.get('reach', 0),
                        'impressions': insights.get('impressions', 0),
                        'published_at': post_data.get('timestamp'),
                        'last_synced_at': datetime.now().isoformat()
                    })
                except Exception as e:
                    logger.warning(f"⚠️  No se pudieron obtener insights para el post {instagram_post_id}: {e}")
                    continue

            # 5. Upsert en la tabla `post_performance`
            if performance_to_upsert:
                perf_response = db_client.table('post_performance').upsert(performance_to_upsert, on_conflict='post_id').execute()
                if perf_response.error:
                    logger.error(f"❌ Error en el upsert de performance: {perf_response.error}")

        except Exception as e:
            logger.error(f"❌ Error durante el proceso de guardado en base de datos: {e}", exc_info=True)

        logger.info(f"✅ Sincronización completada: {len(posts_to_upsert)} posts procesados")
