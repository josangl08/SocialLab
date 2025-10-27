"""
Analytics Service

Servicio unificado para análisis de métricas de Instagram.
Proporciona overview, tendencias, análisis por tipo de contenido y recomendaciones.

Author: SocialLab
Date: 2025-01-19
"""
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict
from database.supabase_client import retry_on_network_error

logger = logging.getLogger(__name__)


class AnalyticsService:
    """
    Servicio de analytics para dashboard.

    DECISIÓN DE DISEÑO:
    En lugar de 4 endpoints separados (/overview, /by-content-type, /trends,
    /recommendations), implementamos 1 endpoint optimizado que retorna toda
    la información en una sola llamada.

    Razones:
    - 1 HTTP request vs 4 = 75% menos latencia
    - 1 query a BD vs 4 queries repetidas = más eficiente
    - Datos consistentes (mismo snapshot de BD)
    - El dashboard siempre necesita todos los datos
    - Más simple para el cliente
    """

    def __init__(self, db_client, instagram_service=None):
        """
        Inicializar servicio de analytics.

        Args:
            db_client: Cliente de Supabase para consultas a BD
            instagram_service: Servicio para interactuar con la API de Instagram
        """
        self.db = db_client
        self.instagram_service = instagram_service

    def get_comprehensive_analytics(
        self,
        user_id: str,
        instagram_account_id: int = None,
        days: int = 30,
        compare: bool = False
    ) -> Dict:
        """
        Obtiene análisis completo de métricas desde la base de datos.

        Este método retorna TODOS los analytics en una sola llamada:
        - Overview de métricas (con crecimiento opcional)
        - Análisis por tipo de contenido
        - Tendencias temporales
        - Mejores horarios para publicar
        - Insights y recomendaciones

        Args:
            user_id: ID del usuario
            instagram_account_id: ID de cuenta Instagram (opcional, se obtiene del user)
            days: Número de días hacia atrás (1-3650)
            compare: Si True, incluye crecimiento vs periodo anterior

        Returns:
            Dict con toda la información de analytics
        """
        # Limitar rango de días
        days = max(1, min(days, 3650))

        # 1. Obtener información de la cuenta
        account_info = self._get_account_info(user_id, instagram_account_id)

        # Usar el ID de la cuenta obtenida
        instagram_account_id = account_info['id']

        # 2. Obtener posts desde BD
        posts = self._get_posts_from_db(instagram_account_id, days)

        if not posts:
            return self._get_empty_analytics(account_info)

        # 3. Calcular todas las métricas
        overview = self._calculate_overview(
            posts,
            account_info,
            compare
        )

        # 4. Si compare=True, calcular crecimiento vs periodo anterior
        if compare:
            growth = self._calculate_growth(instagram_account_id, days, posts)
            overview['growth'] = growth

        # 5. Análisis por tipo de contenido
        by_content_type = self._analyze_by_content_type(posts)

        # 6. Top posts
        top_posts = self._get_top_posts(posts, limit=3)

        # 7. Tendencias temporales
        engagement_trend = self._calculate_trends(posts, days)

        # 8. Analizar datos de audiencia (PRIMERO para obtener online_hours)
        audience = self._analyze_audience(instagram_account_id, days)

        # 9. Mejores horarios con algoritmo avanzado (actividad + performance histórico)
        # Score = (online_followers * 0.4) + (engagement_rate * 0.6)
        best_posting_times = self._calculate_best_posting_times(
            instagram_account_id,
            audience.get('online_hours', {}),
            days
        )

        # 10. Insights y recomendaciones
        insights = self._generate_insights(
            posts,
            best_posting_times,
            by_content_type
        )

        return {
            'success': True,
            'source': 'cache',
            'last_sync_at': account_info['last_sync_at'],
            'data': {
                'overview': overview,
                'audience': audience,
                'by_content_type': by_content_type,
                'top_posts': top_posts,
                'engagement_trend': engagement_trend,
                'best_posting_times': best_posting_times,
                'insights': insights
            }
        }

    def _get_account_info(
        self,
        user_id: str,
        instagram_account_id: int = None
    ) -> Dict:
        """
        Obtiene información de la cuenta de Instagram.

        Args:
            user_id: ID del usuario
            instagram_account_id: ID específico de cuenta (opcional)

        Returns:
            Dict con información de la cuenta
        """
        def _execute_query():
            query = self.db.table('instagram_accounts').select(
                'id, instagram_business_account_id, last_sync_at, '
                'followers_count, username, account_name, reach, profile_views'
            ).eq('user_id', user_id).eq('is_active', True)

            # Si se proporciona instagram_account_id, filtrar por él
            if instagram_account_id is not None:
                query = query.eq('id', instagram_account_id)

            return query.single().execute()

        result = retry_on_network_error(_execute_query)

        if not result.data:
            raise ValueError("No hay cuenta de Instagram conectada")

        return {
            'id': result.data['id'],
            'instagram_business_account_id': result.data.get(
                'instagram_business_account_id'
            ),
            'last_sync_at': result.data.get('last_sync_at'),
            'follower_count': result.data.get('followers_count', 0),
            'username': result.data.get('username'),
            'account_name': result.data.get('account_name'),
            'reach': result.data.get('reach', 0),
            'profile_views': result.data.get('profile_views', 0)
        }

    def _get_posts_from_db(
        self,
        instagram_account_id: int,
        days: int
    ) -> List[Dict]:
        """
        Obtiene posts desde la base de datos.

        Args:
            instagram_account_id: ID de cuenta
            days: Días hacia atrás (si >= 3650, trae TODOS los posts)

        Returns:
            Lista de posts con performance
        """
        query = self.db.table('posts').select(
            'id, content, media_url, publication_date, '
            'instagram_post_id, post_type, '
            'post_performance(likes, comments, saves, reach, impressions, total_interactions)'
        ).eq('instagram_account_id', instagram_account_id).eq(
            'status', 'published'
        )

        # Solo aplicar filtro de fecha si NO es "all time"
        if days < 3650:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            query = query.gte('publication_date', cutoff_date.isoformat())
            logger.info(
                f"📊 Obteniendo posts de los últimos {days} días "
                f"(desde {cutoff_date.strftime('%Y-%m-%d')})"
            )
        else:
            logger.info("📊 Obteniendo TODOS los posts (sin filtro de fecha)")

        result = query.order('publication_date', desc=True).execute()

        posts = [p for p in (result.data or []) if p is not None]

        logger.info(
            f"📊 Obtenidos {len(posts)} posts para cuenta {instagram_account_id}"
        )

        return posts

    def _calculate_overview(
        self,
        posts: List[Dict],
        account_info: Dict,
        include_growth: bool = False
    ) -> Dict:
        """
        Calcula métricas generales de overview.

        Args:
            posts: Lista de posts
            account_info: Diccionario con datos de la cuenta (incluye reach, profile_views)
            include_growth: Si True, prepara estructura para growth

        Returns:
            Dict con métricas agregadas
        """
        total_posts = len(posts)

        # Obtener métricas a nivel de cuenta desde la BD (ya sincronizadas)
        # NOTA: Estas métricas vienen del último sync almacenado en instagram_accounts
        reach = account_info.get('reach', 0)
        profile_views = account_info.get('profile_views', 0)

        # Calcular total de interacciones
        total_interactions = sum(
            (p.get('post_performance') or {}).get('total_interactions', 0) for p in posts
        )

        # Calcular impressions totales sumando las de todos los posts
        # NOTA: impressions no existe a nivel de cuenta, solo a nivel de post
        total_impressions = sum(
            (p.get('post_performance') or {}).get('impressions', 0) for p in posts
        )

        # Calcular promedio de interacciones por post
        avg_interactions_per_post = total_interactions / total_posts if total_posts > 0 else 0

        # Calcular engagement rate usando OPCIÓN 2 (estándar de industria):
        # (interactions promedio por post) / (followers) * 100
        # Esto responde: "¿Qué % de mis followers interactúa en promedio con cada post?"
        avg_engagement_rate = 0
        if total_posts > 0 and account_info['follower_count'] > 0:
            avg_engagement_rate = (avg_interactions_per_post / account_info['follower_count']) * 100

        logger.info(
            f"📊 Overview calculado: {total_posts} posts, "
            f"{avg_interactions_per_post:.1f} interactions/post, "
            f"engagement_rate={avg_engagement_rate:.2f}%"
        )

        overview = {
            'total_posts': total_posts,
            'follower_count': account_info['follower_count'],
            'profile_views': profile_views,
            'reach': reach,
            'impressions': total_impressions,
            'avg_interactions_per_post': round(avg_interactions_per_post, 1),
            'engagement_rate': round(avg_engagement_rate, 2),
            'total_interactions': total_interactions
        }

        # Preparar estructura para growth si se solicita
        if include_growth:
            overview['growth'] = {}

        return overview

    def _calculate_growth(
        self,
        instagram_account_id: int,
        current_period_days: int,
        current_posts: List[Dict]
    ) -> Dict:
        """
        Calcula crecimiento vs periodo anterior.

        Compara el periodo actual con el periodo anterior de la misma duración.
        Por ejemplo: últimos 30 días vs 30 días anteriores.

        Args:
            instagram_account_id: ID de cuenta
            current_period_days: Días del periodo actual
            current_posts: Posts del periodo actual (ya calculados)

        Returns:
            Dict con porcentajes de crecimiento
        """
        # Obtener posts del periodo anterior (mismo número de días)
        previous_start = datetime.utcnow() - timedelta(
            days=current_period_days * 2
        )
        previous_end = datetime.utcnow() - timedelta(days=current_period_days)

        previous_posts_result = self.db.table('posts').select(
            'id, post_performance(likes, comments, saves, reach, impressions)'
        ).eq('instagram_account_id', instagram_account_id).eq(
            'status', 'published'
        ).gte('publication_date', previous_start.isoformat()).lt(
            'publication_date', previous_end.isoformat()
        ).execute()

        previous_posts = previous_posts_result.data or []

        # Calcular métricas del periodo anterior
        prev_total_posts = len(previous_posts)
        prev_total_likes = sum(
            (p.get('post_performance') or {}).get('likes', 0)
            for p in previous_posts
        )
        prev_total_comments = sum(
            (p.get('post_performance') or {}).get('comments', 0)
            for p in previous_posts
        )

        # Calcular métricas del periodo actual
        curr_total_posts = len(current_posts)
        curr_total_likes = sum(
            (p.get('post_performance') or {}).get('likes', 0)
            for p in current_posts
        )
        curr_total_comments = sum(
            (p.get('post_performance') or {}).get('comments', 0)
            for p in current_posts
        )

        # Calcular porcentajes de crecimiento
        def calc_growth_pct(current, previous):
            if previous == 0:
                return 100.0 if current > 0 else 0.0
            return round(((current - previous) / previous) * 100, 1)

        return {
            'posts': calc_growth_pct(curr_total_posts, prev_total_posts),
            'likes': calc_growth_pct(curr_total_likes, prev_total_likes),
            'comments': calc_growth_pct(curr_total_comments, prev_total_comments),
            'engagement': calc_growth_pct(
                curr_total_likes + curr_total_comments,
                prev_total_likes + prev_total_comments
            )
        }

    def _analyze_audience(self, instagram_account_id: int, days: int) -> Dict:
        """
        Analiza y formatea los datos de audiencia desde la BD.

        Args:
            instagram_account_id: ID de la cuenta
            days: Días hacia atrás para análisis

        Returns:
            Dict con:
                - follower_growth: Array de {date, follower_count, change}
                - demographics: Dict con audience_gender_age, audience_country, etc.
                - online_hours: Dict con {hour: count}
                - top_locations: Array de top países/ciudades
        """
        audience_data = {
            "follower_growth": [],
            "demographics": {},
            "online_hours": {},
            "top_locations": {
                "countries": [],
                "cities": []
            }
        }

        # 1. Crecimiento de seguidores (snapshots diarios)
        cutoff_date = datetime.utcnow().date() - timedelta(days=days)
        try:
            growth_result = self.db.table('instagram_account_snapshots').select(
                'date, follower_count'
            ).eq(
                'instagram_account_id', instagram_account_id
            ).gte(
                'date', cutoff_date.isoformat()
            ).order('date', desc=False).execute()

            if growth_result.data:
                # Calcular cambios día a día
                snapshots = growth_result.data
                for i, snapshot in enumerate(snapshots):
                    change = 0
                    if i > 0:
                        change = snapshot['follower_count'] - snapshots[i-1]['follower_count']

                    audience_data["follower_growth"].append({
                        'date': snapshot['date'],
                        'follower_count': snapshot['follower_count'],
                        'change': change
                    })

        except Exception as e:
            logger.warning(f"No se pudo obtener el crecimiento de seguidores: {e}")

        # 2. Datos demográficos (audience_demographics table)
        try:
            demo_result = self.db.table('audience_demographics').select(
                'metric_type, data, sync_date'
            ).eq('instagram_account_id', instagram_account_id).execute()

            if demo_result.data:
                for row in demo_result.data:
                    metric_type = row['metric_type']
                    data = row['data']

                    # Asegurar que los datos sean un diccionario
                    if isinstance(data, str):
                        try:
                            data = json.loads(data)
                        except json.JSONDecodeError:
                            logger.warning(f"No se pudo decodificar el JSON para {metric_type}")
                            data = {}

                    audience_data["demographics"][metric_type] = data

                    # DEBUG: Ver qué datos tenemos para gender_age
                    if metric_type == 'audience_gender_age':
                        logger.info(f"📊 DEBUG audience_gender_age desde BD (primeras 5 keys): {list(data.keys())[:5] if data else 'vacío'}")

                    # Extraer top países y ciudades para vista rápida
                    if metric_type == 'audience_country' and data:
                        # Calcular total para porcentajes
                        total_audience = sum(data.values())

                        countries = []
                        for code, count in data.items():
                            percentage = (count / total_audience * 100) if total_audience > 0 else 0
                            countries.append({
                                'country_code': code,
                                'audience_count': count,
                                'percentage': percentage
                            })
                        countries.sort(key=lambda x: x['audience_count'], reverse=True)
                        audience_data["top_locations"]["countries"] = countries[:5]

                    elif metric_type == 'audience_city' and data:
                        # Calcular total para porcentajes
                        total_audience = sum(data.values())

                        cities = []
                        for city_name, count in data.items():
                            percentage = (count / total_audience * 100) if total_audience > 0 else 0
                            cities.append({
                                'city_name': city_name,
                                'audience_count': count,
                                'percentage': percentage
                            })
                        cities.sort(key=lambda x: x['audience_count'], reverse=True)
                        audience_data["top_locations"]["cities"] = cities[:5]

        except Exception as e:
            logger.warning(f"No se pudieron obtener datos demográficos: {e}")

        # 3. Horas de actividad (online_followers_data más reciente)
        try:
            online_result = self.db.table('online_followers_data').select(
                'hour_data, sync_date'
            ).eq(
                'instagram_account_id', instagram_account_id
            ).order('sync_date', desc=True).limit(1).maybe_single().execute()

            if online_result and online_result.data and online_result.data.get('hour_data'):
                audience_data["online_hours"] = online_result.data['hour_data']

        except Exception as e:
            logger.warning(f"No se pudieron obtener las horas de actividad: {e}")

        return audience_data

    def get_audience_detailed(
        self,
        instagram_account_id: int,
        days: int = 30
    ) -> Dict:
        """
        Obtiene análisis COMPLETO de audiencia para Dashboard Avanzado.

        Este método retorna:
        - Crecimiento histórico de seguidores
        - Demografía completa (género/edad, países, ciudades, idiomas)
        - Actividad por hora (online_followers)
        - Mejores horarios para publicar (combinando actividad + performance)
        - Top ubicaciones

        Args:
            instagram_account_id: ID de cuenta
            days: Días hacia atrás para análisis

        Returns:
            Dict con datos completos de audiencia
        """
        # Obtener datos base
        audience = self._analyze_audience(instagram_account_id, days)

        # Calcular mejores horarios (combinando actividad + performance histórico)
        best_times = self._calculate_best_posting_times(
            instagram_account_id,
            audience.get('online_hours', {}),
            days
        )

        audience['best_posting_times'] = best_times

        return audience

    def _calculate_best_posting_times(
        self,
        instagram_account_id: int,
        online_hours: Dict,
        days: int
    ) -> list:
        """
        Calcula los mejores momentos para publicar combinando:
        1. Cuándo están online los seguidores (online_hours)
        2. Cuándo han tenido mejor performance los posts históricos

        Algoritmo: Score = (online_normalized * 0.4) + (engagement_rate * 0.6)

        Args:
            instagram_account_id: ID de cuenta
            online_hours: Dict con {hour: count} de seguidores online
            days: Días hacia atrás para performance histórico

        Returns:
            Lista de top 5 horarios con score combinado
        """
        recommendations = []

        # 1. Obtener performance histórico por hora
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        try:
            # Query para obtener engagement promedio por hora del día
            posts = self._get_posts_from_db(instagram_account_id, days)

            # Agrupar por hora
            hourly_performance = {}
            for post in posts:
                try:
                    pub_date = post.get('publication_date')
                    if not pub_date:
                        continue

                    post_date = datetime.fromisoformat(
                        pub_date.replace('Z', '+00:00')
                    )
                    hour = post_date.hour

                    perf = post.get('post_performance') or {}
                    likes = perf.get('likes', 0)
                    comments = perf.get('comments', 0)
                    reach = perf.get('reach', 0)

                    # Calcular engagement rate
                    engagement_rate = 0
                    if reach > 0:
                        engagement_rate = ((likes + comments) / reach) * 100

                    if hour not in hourly_performance:
                        hourly_performance[hour] = {
                            'total_engagement': 0,
                            'count': 0
                        }

                    hourly_performance[hour]['total_engagement'] += engagement_rate
                    hourly_performance[hour]['count'] += 1

                except Exception:
                    continue

            # Calcular promedios
            for hour in hourly_performance:
                count = hourly_performance[hour]['count']
                if count > 0:
                    hourly_performance[hour]['avg_engagement'] = (
                        hourly_performance[hour]['total_engagement'] / count
                    )

        except Exception as e:
            logger.warning(f"Error calculando performance por hora: {e}")
            hourly_performance = {}

        # 2. Combinar online_followers con performance histórico
        if not online_hours:
            online_hours = {}

        # Normalizar online followers (0-100)
        max_online = max(online_hours.values()) if online_hours else 1
        online_hours_normalized = {
            str(h): (count / max_online) * 100
            for h, count in online_hours.items()
        }

        # Calcular score combinado para cada hora (0-23)
        for hour in range(24):
            hour_str = str(hour)

            # Score de actividad (0-100)
            online_score = online_hours_normalized.get(hour_str, 0)

            # Score de performance (0-100)
            engagement_score = 0
            if hour in hourly_performance:
                engagement_score = hourly_performance[hour].get('avg_engagement', 0)

            # Score combinado: 40% actividad + 60% performance
            combined_score = (online_score * 0.4) + (engagement_score * 0.6)

            recommendations.append({
                'hour': f"{hour:02d}:00",
                'day_of_week': None,  # TODO: Analizar por día de semana también
                'score': round(combined_score, 1),
                'online_followers': online_hours.get(hour_str, 0),
                'avg_engagement': round(engagement_score, 1),
                'posts_count': hourly_performance.get(hour, {}).get('count', 0)
            })

        # Ordenar por score y retornar top 5
        recommendations.sort(key=lambda x: x['score'], reverse=True)
        return recommendations[:5]

    def _analyze_by_content_type(self, posts: List[Dict]) -> Dict:
        """
        Analiza engagement por tipo de contenido.

        Args:
            posts: Lista de posts

        Returns:
            Dict con estadísticas por tipo de contenido
        """
        type_stats = defaultdict(lambda: {
            'count': 0,
            'total_likes': 0,
            'total_comments': 0,
            'total_engagement': 0,
            'avg_engagement': 0
        })

        for post in posts:
            post_type = post.get('post_type', 'IMAGE').upper()
            perf = post.get('post_performance') or {}
            likes = perf.get('likes', 0)
            comments = perf.get('comments', 0)
            engagement = likes + comments

            type_stats[post_type]['count'] += 1
            type_stats[post_type]['total_likes'] += likes
            type_stats[post_type]['total_comments'] += comments
            type_stats[post_type]['total_engagement'] += engagement

        # Calcular promedios
        for post_type, stats in type_stats.items():
            if stats['count'] > 0:
                stats['avg_engagement'] = round(
                    stats['total_engagement'] / stats['count'], 2
                )

        # Convertir a dict normal y agregar nombres legibles
        type_names = {
            'IMAGE': 'Imágenes',
            'VIDEO': 'Videos',
            'CAROUSEL_ALBUM': 'Carruseles',
            'REELS': 'Reels',
            'STORY': 'Historias'
        }

        result = {}
        for post_type, stats in type_stats.items():
            result[post_type] = {
                **stats,
                'type_name': type_names.get(post_type, post_type.title())
            }

        return result

    def _get_top_posts(self, posts: List[Dict], limit: int = 3) -> List[Dict]:
        """
        Obtiene los posts con mejor engagement.

        Args:
            posts: Lista de posts
            limit: Número de posts a retornar

        Returns:
            Lista de top posts
        """
        posts_with_engagement = []

        for post in posts:
            perf = post.get('post_performance') or {}
            likes = perf.get('likes', 0)
            comments = perf.get('comments', 0)
            engagement = likes + comments

            instagram_post_id = post.get('instagram_post_id', '')
            permalink = (
                f"https://www.instagram.com/p/{instagram_post_id}/"
                if instagram_post_id else ''
            )

            posts_with_engagement.append({
                'id': instagram_post_id,
                'caption': post.get('content', '')[:100],
                'media_url': post.get('media_url', ''),
                'permalink': permalink,
                'timestamp': post.get('publication_date', ''),
                'likes': likes,
                'comments': comments,
                'engagement': engagement,
                'impressions': perf.get('impressions', 0),
                'reach': perf.get('reach', 0),
                'saved': perf.get('saves', 0)
            })

        # Ordenar por engagement y tomar top N
        top = sorted(
            posts_with_engagement,
            key=lambda x: x['engagement'],
            reverse=True
        )[:limit]

        return top

    def _calculate_trends(self, posts: List[Dict], days: int) -> List[Dict]:
        """
        Calcula tendencia de engagement por día.

        Args:
            posts: Lista de posts
            days: Número de días del periodo

        Returns:
            Lista con engagement por día ordenada
        """
        daily_engagement = {}

        for post in posts:
            try:
                pub_date = post.get('publication_date')
                if not pub_date:
                    continue

                post_date = datetime.fromisoformat(
                    pub_date.replace('Z', '+00:00')
                )
                date_key = post_date.strftime('%Y-%m-%d')

                perf = post.get('post_performance') or {}
                likes = perf.get('likes', 0)
                comments = perf.get('comments', 0)

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
                daily_engagement[date_key]['engagement'] += likes + comments
                daily_engagement[date_key]['posts_count'] += 1

            except Exception as e:
                logger.warning(f"Error procesando tendencia de post: {e}")
                continue

        # Convertir a lista y ordenar por fecha
        trend = sorted(daily_engagement.values(), key=lambda x: x['date'])

        return trend

    def _analyze_best_times(self, posts: List[Dict]) -> List[Dict]:
        """
        Analiza mejores horarios para publicar.

        Args:
            posts: Lista de posts

        Returns:
            Lista de horarios con engagement promedio (top 4)
        """
        hourly_engagement = {}
        hourly_count = {}

        for post in posts:
            try:
                pub_date = post.get('publication_date')
                if not pub_date:
                    continue

                post_date = datetime.fromisoformat(
                    pub_date.replace('Z', '+00:00')
                )
                hour = post_date.hour

                perf = post.get('post_performance') or {}
                engagement = perf.get('likes', 0) + perf.get('comments', 0)

                if hour not in hourly_engagement:
                    hourly_engagement[hour] = 0
                    hourly_count[hour] = 0

                hourly_engagement[hour] += engagement
                hourly_count[hour] += 1

            except Exception:
                continue

        best_times = []
        for hour in sorted(hourly_engagement.keys()):
            avg_engagement = (
                hourly_engagement[hour] / hourly_count[hour]
                if hourly_count[hour] > 0 else 0
            )
            best_times.append({
                'hour': f"{hour:02d}:00",
                'avg_engagement_rate': round(avg_engagement, 2),
                'posts_count': hourly_count[hour]
            })

        # Ordenar por engagement y tomar top 4
        best_times = sorted(
            best_times,
            key=lambda x: x['avg_engagement_rate'],
            reverse=True
        )[:4]

        return best_times

    def _generate_insights(
        self,
        posts: List[Dict],
        best_posting_times: List[Dict],
        by_content_type: Dict
    ) -> List[Dict]:
        """
        Genera insights y recomendaciones basados en datos.

        Args:
            posts: Lista de posts
            best_posting_times: Mejores horarios
            by_content_type: Análisis por tipo de contenido

        Returns:
            Lista de insights
        """
        insights = []
        day_names = [
            'Lunes', 'Martes', 'Miércoles', 'Jueves',
            'Viernes', 'Sábado', 'Domingo'
        ]

        # Analizar mejor día de la semana
        day_engagement = defaultdict(lambda: {'total': 0, 'count': 0})

        for post in posts:
            try:
                pub_date = post.get('publication_date')
                if not pub_date:
                    continue

                date_obj = datetime.fromisoformat(
                    pub_date.replace('Z', '+00:00')
                )
                day_of_week = date_obj.weekday()

                perf = post.get('post_performance') or {}
                engagement = perf.get('likes', 0) + perf.get('comments', 0)

                day_engagement[day_of_week]['total'] += engagement
                day_engagement[day_of_week]['count'] += 1

            except Exception:
                continue

        # Mejor día
        best_day = None
        best_day_avg = 0
        for day, data in day_engagement.items():
            if data['count'] > 0:
                avg = data['total'] / data['count']
                if avg > best_day_avg:
                    best_day_avg = avg
                    best_day = day

        if best_day is not None and best_day_avg > 0:
            insights.append({
                "type": "best_day",
                "title": "Mejor día para publicar",
                "description": (
                    f"Los posts del {day_names[best_day]} obtienen "
                    f"{best_day_avg:.0f} interacciones promedio"
                ),
                "icon": "calendar-check"
            })

        # Mejor horario
        if best_posting_times and len(best_posting_times) > 0:
            best_hour = best_posting_times[0]
            insights.append({
                "type": "best_hour",
                "title": "Horario óptimo",
                "description": (
                    f"{best_hour['hour']} es tu hora pico con "
                    f"{best_hour['avg_engagement']:.1f}% "
                    f"engagement promedio y {best_hour['online_followers']} seguidores online"
                ),
                "icon": "clock"
            })

        # Mejor tipo de contenido
        best_type = None
        best_type_avg = 0
        for ptype, data in by_content_type.items():
            if data['count'] > 0:
                avg = data['avg_engagement']
                if avg > best_type_avg:
                    best_type_avg = avg
                    best_type = ptype

        if best_type and best_type_avg > 0:
            type_display = by_content_type[best_type]['type_name'].lower()
            insights.append({
                "type": "content_type",
                "title": "Tipo de contenido",
                "description": (
                    f"Los posts con {type_display} tienen mayor interacción "
                    f"({best_type_avg:.0f} promedio)"
                ),
                "icon": "image"
            })

        # Recomendación combinada
        if best_day is not None and best_posting_times:
            insights.append({
                "type": "recommendation",
                "title": "Recomendación",
                "description": (
                    f"Publica los {day_names[best_day]} alrededor de las "
                    f"{best_posting_times[0]['hour']} para maximizar el engagement"
                ),
                "icon": "lightbulb"
            })

        return insights

    def _get_empty_analytics(self, account_info: Dict) -> Dict:
        """
        Retorna estructura vacía cuando no hay posts.

        Args:
            account_info: Información de la cuenta

        Returns:
            Dict con estructura vacía
        """
        return {
            'success': True,
            'source': 'cache',
            'last_sync_at': account_info['last_sync_at'],
            'data': {
                'overview': {
                    'total_posts': 0,
                    'follower_count': account_info['follower_count'],
                    'profile_views': account_info.get('profile_views', 0),
                    'reach': account_info.get('reach', 0),
                    'impressions': 0,
                    'avg_interactions_per_post': 0,
                    'engagement_rate': 0,
                    'accounts_engaged': 0,
                    'total_interactions': 0
                },
                'by_content_type': {},
                'top_posts': [],
                'engagement_trend': [],
                'best_posting_times': [],
                'insights': []
            }
        }
