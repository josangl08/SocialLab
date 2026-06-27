"""
Servicio para obtener insights de Instagram Graph API
"""
import logging
import requests
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from fastapi import HTTPException
from httpx import ReadError

logger = logging.getLogger(__name__)


class InstagramInsightsService:
    """Servicio para interactuar con Instagram Graph API y obtener insights"""

    BASE_URL = "https://graph.facebook.com/v24.0"

    def __init__(self, access_token: str, instagram_account_id: str):
        self.access_token = access_token
        self.instagram_account_id = instagram_account_id

    def _make_request(self, endpoint: str, params: Dict = None) -> Dict:
        """Hacer petición a Instagram Graph API"""
        if params is None:
            params = {}

        params['access_token'] = self.access_token

        if endpoint.startswith('http://') or endpoint.startswith('https://'):
            url = endpoint
        else:
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

    def get_account_insights(self, period: str = "day", days_back: int = 7) -> Dict:
        """
        Obtiene insights básicos de la cuenta, separando las llamadas por
        compatibilidad de métricas para mayor robustez.

        Args:
            period: Período por defecto (ignorado, se usan los períodos correctos)
            days_back: Días hacia atrás para métricas diarias (default: 7)

        Returns:
            Dict con métricas básicas de la cuenta
        """
        insights = {}

        # 1. Obtener datos básicos del perfil
        try:
            profile_endpoint = f"{self.instagram_account_id}"
            profile_params = {'fields': 'followers_count,media_count,name,username,profile_picture_url'}
            profile_data = self._make_request(profile_endpoint, profile_params)
            insights.update({
                'follower_count': profile_data.get('followers_count', 0),
                'media_count': profile_data.get('media_count', 0),
                'name': profile_data.get('name', ''),
                'username': profile_data.get('username', ''),
                'profile_picture_url': profile_data.get('profile_picture_url', '')
            })
        except Exception as e:
            logger.warning(f"⚠️  No se pudieron obtener datos del perfil: {e}")

        endpoint = f"{self.instagram_account_id}/insights"

        # Calcular rango de fechas para métricas diarias
        until_date = datetime.now()
        since_date = until_date - timedelta(days=days_back)

        # 2. Métricas con period=day y metric_type=total_value
        day_metrics = ['profile_views', 'total_interactions']
        try:
            request_params = {
                'metric': ",".join(day_metrics),
                'period': 'day',
                'metric_type': 'total_value',
                'since': int(since_date.timestamp()),
                'until': int(until_date.timestamp())
            }
            data = self._make_request(endpoint, request_params)
            for item in data.get('data', []):
                metric_name = item.get('name')
                # Con metric_type=total_value, la API retorna 'total_value' no 'values'
                if item.get('total_value'):
                    total = item['total_value'].get('value', 0)
                    insights[metric_name] = total
                elif item.get('values'):
                    # Fallback: Si retorna array de valores, sumarlos
                    total = sum(v.get('value', 0) for v in item['values'])
                    insights[metric_name] = total
        except Exception as e:
            logger.warning(f"⚠️  No se pudieron obtener métricas diarias ({','.join(day_metrics)}): {e}")

        # 3. Métrica 'reach' con period=days_28
        try:
            request_params = {
                'metric': 'reach',
                'period': 'days_28'
            }
            data = self._make_request(endpoint, request_params)
            if data.get('data') and data['data'][0].get('values'):
                 insights['reach'] = data['data'][0]['values'][0].get('value', 0)
        except Exception as e:
            logger.warning(f"⚠️  No se pudo obtener la métrica 'reach': {e}")


        # Asegurar que todas las claves esperadas existan para evitar KeyErrors
        expected_metrics = [
            'follower_count', 'media_count', 'name', 'username', 'profile_picture_url',
            'profile_views', 'total_interactions', 'reach'
        ]
        for key in expected_metrics:
            if key not in insights:
                # Asignar un valor por defecto apropiado
                if any(k in key for k in ['count', 'views', 'reach', 'interactions']):
                    insights[key] = 0
                else:
                    insights[key] = ''

        logger.info(
            f"✅ Métricas de cuenta obtenidas: followers={insights.get('follower_count')}, "
            f"reach={insights.get('reach')}, profile_views={insights.get('profile_views')}"
        )

        return insights

    def get_account_insights_detailed(
        self,
        period: str = "days_28",
        metrics: List[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None
    ) -> Dict:
        """
        Obtiene métricas detalladas de la cuenta de forma robusta,
        utilizando la configuración correcta para cada métrica.

        Args:
            period: Período por defecto (ignorado, cada métrica usa su período óptimo)
            metrics: Lista de métricas a obtener
            since: Fecha inicio para métricas que soportan rangos (opcional)
            until: Fecha fin para métricas que soportan rangos (opcional)

        Returns:
            Dict con métricas de la cuenta
        """
        if metrics is None:
            metrics = ['reach', 'profile_views', 'total_interactions', 'website_clicks']

        # Configuración validada para cada métrica
        # NOTA: impressions NO existe para account-level insights, solo para media-level
        metric_configs = {
            'reach': {'period': 'days_28'},
            'profile_views': {'period': 'day', 'metric_type': 'total_value'},
            'total_interactions': {'period': 'day', 'metric_type': 'total_value'},
            'website_clicks': {'period': 'day', 'metric_type': 'total_value'},
            'follower_count': {'period': 'day'}
        }

        insights = {}
        endpoint = f"{self.instagram_account_id}/insights"

        for metric in metrics:
            if metric not in metric_configs:
                logger.warning(f"⚠️  Métrica '{metric}' no soportada o sin configuración válida.")
                insights[metric] = 0
                continue

            try:
                params = {'metric': metric, **metric_configs[metric]}

                # Añadir since/until para métricas que los soportan
                if since and until and params.get('period') == 'day':
                    params['since'] = int(since.timestamp())
                    params['until'] = int(until.timestamp())

                data = self._make_request(endpoint, params)

                if data.get('data') and data['data'][0].get('values'):
                    metric_data = data['data'][0]['values']
                    # Las métricas con 'total_value' o 'day' suelen devolver un solo valor relevante al final
                    if params.get('metric_type') == 'total_value' or params.get('period') == 'day':
                        # Si hay múltiples valores (por rango de fechas), sumarlos
                        if len(metric_data) > 1:
                            insights[metric] = sum(d.get('value', 0) for d in metric_data)
                        else:
                            insights[metric] = metric_data[-1].get('value', 0)
                    else:
                        # Para métricas como 'reach' o 'impressions' que pueden devolver
                        # un array, sumamos todos los valores si es necesario.
                        # En este caso, 'days_28' para reach/impressions ya da un total.
                        insights[metric] = metric_data[0].get('value', 0)
                else:
                    insights[metric] = 0

            except Exception as e:
                logger.warning(f"⚠️  No se pudo obtener la métrica '{metric}': {e}")
                insights[metric] = 0

        return insights

    def get_audience_insights(self) -> Dict:
        """
        Obtiene datos demográficos y de actividad de la audiencia, usando
        los endpoints y parámetros correctos validados con el script de diagnóstico.
        """
        audience_data = {
            'demographics': {},
            'online_hours': {}
        }
        endpoint = f"{self.instagram_account_id}/insights"

        # 1. Demografía de audiencia con breakdowns
        demographic_breakdowns = {
            'audience_city': 'city',
            'audience_country': 'country',
            'audience_gender_age': 'gender,age'
        }

        for friendly_name, breakdown in demographic_breakdowns.items():
            try:
                params = {
                    'metric': 'follower_demographics',
                    'period': 'lifetime',
                    'breakdown': breakdown,
                    'metric_type': 'total_value'
                }
                data = self._make_request(endpoint, params)
                logger.info(f"📊 DEBUG API Response para {friendly_name}: {data}")

                # Con metric_type=total_value, la API retorna estructura con 'breakdowns'
                if data.get('data') and len(data['data']) > 0:
                    item = data['data'][0]

                    # La estructura real es: total_value.breakdowns[0].results
                    if item.get('total_value') and item['total_value'].get('breakdowns'):
                        breakdowns = item['total_value']['breakdowns']
                        if breakdowns and len(breakdowns) > 0:
                            results = breakdowns[0].get('results', [])

                            # Convertir array de results a diccionario
                            parsed_data = {}
                            for result in results:
                                try:
                                    dimension_values = result.get('dimension_values', [])
                                    # Asegurar que todos los valores son strings
                                    # Para gender_age usar punto, para otros usar coma
                                    if friendly_name == 'audience_gender_age':
                                        # Formato: "F.18-24" (punto sin espacios)
                                        key = '.'.join(str(v) for v in dimension_values)
                                    else:
                                        # Formato: "London, England" (coma con espacio)
                                        key = ', '.join(str(v) for v in dimension_values)

                                    value = result.get('value', 0)
                                    parsed_data[key] = value
                                except Exception as parse_error:
                                    logger.warning(f"Error parseando resultado individual: {parse_error}")
                                    continue

                            audience_data['demographics'][friendly_name] = parsed_data
                        else:
                            audience_data['demographics'][friendly_name] = {}
                    else:
                        audience_data['demographics'][friendly_name] = {}
                else:
                    audience_data['demographics'][friendly_name] = {}

                logger.info(f"📊 {friendly_name}: {len(audience_data['demographics'][friendly_name])} entradas")
            except Exception as e:
                logger.warning(f"⚠️  No se pudo obtener {friendly_name}: {e}")
                audience_data['demographics'][friendly_name] = {}

        # 2. Horas de actividad de seguidores
        try:
            params = {'metric': 'online_followers', 'period': 'lifetime'}
            data = self._make_request(endpoint, params)
            logger.info(f"📊 DEBUG API Response para online_followers: {data}")

            if data.get('data') and len(data['data']) > 0:
                item = data['data'][0]
                # online_followers devuelve 'values' (array) no total_value
                if item.get('values'):
                    audience_data['online_hours'] = item['values'][0].get('value', {})
                    logger.info(f"📊 online_followers: {len(audience_data['online_hours'])} horas")
                else:
                    logger.warning(f"⚠️  online_followers estructura: {item.keys()}")
        except Exception as e:
            logger.warning(f"⚠️  No se pudieron obtener datos de actividad de seguidores: {e}")

        return audience_data

    def get_media_list(self, limit: int = 25) -> List[Dict]:
        endpoint = f"{self.instagram_account_id}/media"
        params = {
            'fields': 'id,caption,media_type,media_url,permalink,timestamp,like_count,comments_count',
            'limit': min(limit, 100)
        }
        data = self._make_request(endpoint, params)
        return data.get('data', [])

    def get_media_insights(self, media_id: str) -> Dict:
        endpoint = f"{media_id}/insights"
        metrics = ['reach', 'saved', 'total_interactions', 'views']
        params = {'metric': ','.join(metrics)}
        data = self._make_request(endpoint, params)

        insights = {}
        for item in data.get('data', []):
            metric_name = item.get('name')
            values = item.get('values', [])
            if values:
                insights[metric_name] = values[0].get('value', 0)

        if 'total_interactions' in insights:
            insights['engagement'] = insights['total_interactions']
        if 'views' in insights and 'impressions' not in insights:
            insights['impressions'] = insights['views']
        elif 'reach' in insights and 'impressions' not in insights:
            insights['impressions'] = insights['reach']

        return insights

    def _get_all_media_paginated(self) -> List[Dict]:
        all_media = []
        endpoint = f"{self.instagram_account_id}/media"
        params = {
            'fields': 'id,caption,media_type,media_url,permalink,timestamp,like_count,comments_count',
            'limit': 100
        }
        while endpoint:
            try:
                data = self._make_request(endpoint, params if not all_media else {})
                media = data.get('data', [])
                all_media.extend(media)
                endpoint = data.get('paging', {}).get('next')
                params = {}
            except Exception as e:
                logger.error(f"❌ Error durante la paginación de media: {e}")
                break
        return all_media

    def sync_posts_to_database(self, db_client, user_id: str, instagram_account_id_db: int):
        logger.info("🚀 Iniciando sincronización de posts...")
        all_posts_from_api = self._get_all_media_paginated()
        if not all_posts_from_api:
            logger.warning("⚠️  No se encontraron posts en la API para sincronizar.")
            return

        posts_to_upsert = []
        for post_data in all_posts_from_api:
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

        BATCH_SIZE = 50
        MAX_RETRIES = 3
        db_posts = {}
        try:
            for i in range(0, len(posts_to_upsert), BATCH_SIZE):
                batch = posts_to_upsert[i:i + BATCH_SIZE]
                logger.info(f"📦 Procesando lote de posts {i//BATCH_SIZE + 1}/{(len(posts_to_upsert) + BATCH_SIZE - 1)//BATCH_SIZE}")
                for attempt in range(MAX_RETRIES):
                    try:
                        post_response = db_client.table('posts').upsert(batch, on_conflict='instagram_post_id').execute()
                        if post_response.data:
                            for p in post_response.data:
                                db_posts[p['instagram_post_id']] = p['id']
                            time.sleep(0.5)
                            break
                    except (ReadError, Exception) as e:
                        if attempt < MAX_RETRIES - 1:
                            wait_time = 2 ** attempt
                            logger.warning(f"⚠️  Error en lote de posts, reintentando en {wait_time}s...")
                            time.sleep(wait_time)
                        else:
                            raise
            # SELECT explícito para completar db_posts — el upsert no devuelve
            # filas sin cambios, por lo que posts ya existentes quedarían fuera
            try:
                all_result = db_client.table('posts').select(
                    'id, instagram_post_id'
                ).eq('instagram_account_id', instagram_account_id_db).execute()
                for p in (all_result.data or []):
                    db_posts.setdefault(p['instagram_post_id'], p['id'])
                logger.info(f"📊 db_posts completo: {len(db_posts)} posts mapeados")
            except Exception as e:
                logger.warning(f"⚠️  Error al completar db_posts con SELECT: {e}")

            if not db_posts:
                logger.error("❌ No se pudieron procesar posts")
                return

            performance_to_upsert = []
            cutoff_date = datetime.now() - timedelta(days=90)
            recent_posts_count = 0
            posts_with_insights = 0

            skipped_posts = []
            for post_data in all_posts_from_api:
                instagram_post_id = post_data['id']
                if instagram_post_id not in db_posts:
                    skipped_posts.append(instagram_post_id)
                    continue
                internal_post_id = db_posts[instagram_post_id]
                post_date = None
                if post_data.get('timestamp'):
                    ts = post_data['timestamp'].replace('Z', '+00:00')
                    # Instagram devuelve +0000 (sin ':'); Python <3.11 requiere +00:00
                    if len(ts) >= 5 and ts[-5] in ('+', '-') and ':' not in ts[-5:]:
                        ts = ts[:-2] + ':' + ts[-2:]
                    post_date = datetime.fromisoformat(ts)

                likes = post_data.get('like_count', 0)
                comments = post_data.get('comments_count', 0)
                shares = 0
                saves = 0

                perf_data = {
                    'post_id': internal_post_id,
                    'likes': likes,
                    'comments': comments,
                    'last_synced_at': datetime.now().isoformat()
                }

                if post_date and post_date.replace(tzinfo=None) > cutoff_date:
                    recent_posts_count += 1
                    try:
                        insights = self.get_media_insights(instagram_post_id)
                        shares = insights.get('shares', 0)
                        saves = insights.get('saved', 0)
                        impressions = insights.get('impressions', 0)
                        reach = insights.get('reach', 0)

                        perf_data.update({
                            'shares': shares,
                            'saves': saves,
                            'reach': reach,
                            'impressions': impressions
                        })

                        if impressions > 0 or reach > 0:
                            posts_with_insights += 1
                    except Exception as e:
                        logger.warning(f"⚠️  No se pudieron obtener insights para post reciente {instagram_post_id}: {e}")

                # total_interactions es valor derivado; se calcula en lectura, no se persiste
                performance_to_upsert.append(perf_data)

            if skipped_posts:
                logger.warning(
                    f"⚠️  {len(skipped_posts)} posts de Instagram API no encontrados "
                    f"en db_posts (instagram_post_id posiblemente null en DB): {skipped_posts[:5]}"
                )
            logger.info(
                f"📊 Posts analizados: {len(all_posts_from_api)} total, "
                f"{recent_posts_count} recientes (<90 días), "
                f"{posts_with_insights} con insights disponibles, "
                f"{len(skipped_posts)} omitidos"
            )

            if performance_to_upsert:
                logger.info(f"📊 Guardando métricas de {len(performance_to_upsert)} posts...")
                logger.debug(f"🔍 Columnas en perf_data: {list(performance_to_upsert[0].keys())}")
                saved_count = 0
                for i in range(0, len(performance_to_upsert), BATCH_SIZE):
                    batch = performance_to_upsert[i:i + BATCH_SIZE]
                    for attempt in range(MAX_RETRIES):
                        try:
                            db_client.table('post_performance').upsert(batch, on_conflict='post_id').execute()
                            saved_count += len(batch)
                            time.sleep(0.5)
                            break
                        except (ReadError, Exception) as e:
                            if attempt < MAX_RETRIES - 1:
                                wait_time = 2 ** attempt
                                logger.warning(f"⚠️  Error guardando métricas (intento {attempt+1}): {e}")
                                time.sleep(wait_time)
                            else:
                                logger.error(f"❌ Fallo definitivo en batch {i//BATCH_SIZE+1}: {e}")
                                raise
                logger.info(f"✅ post_performance guardado para {saved_count} posts")
            else:
                logger.warning("⚠️  performance_to_upsert vacío — ningún post procesado para métricas")
        except Exception as e:
            logger.error(f"❌ Error durante el guardado en BD: {e}", exc_info=True)

        logger.info(f"✅ Sincronización de posts completada: {len(posts_to_upsert)} posts procesados")

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
