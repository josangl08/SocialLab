"""
Analytics Service

Servicio unificado para análisis de métricas de Instagram.
Proporciona overview, tendencias, análisis por tipo de contenido y recomendaciones.

Author: SocialLab
Date: 2025-01-19
"""
import logging
import json
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict

# Zona horaria de la cuenta — Instagram guarda timestamps en UTC
from database.supabase_client import retry_on_network_error
from utils.timezones import effective_timezone, local_today, to_local
from services.content_quality import score_hook
from services.content_formats import get_strategy_mode

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

    @staticmethod
    def calculate_sends_per_reach(shares: Optional[int], reach: Optional[int]) -> Optional[float]:
        """
        Calcula el ratio de Sends per Reach (shares / reach).
        Retorna None si reach es 0 o no está disponible (evita división por cero).
        """
        if reach is None or reach <= 0:
            return None
        shares_val = shares or 0
        return round(shares_val / reach, 4)

    @staticmethod
    def calculate_median_views(views_list: List[int]) -> Optional[float]:
        """
        Mediana de vistas de los posts con vistas (> 0).
        Retorna None si hay menos de 5 (datos insuficientes).
        """
        with_views = [v for v in views_list if v and v > 0]
        if len(with_views) < 5:
            return None
        return float(statistics.median(with_views))

    @staticmethod
    def calculate_outlier_multiple(views: Optional[int], median_views: Optional[float]) -> Optional[float]:
        """
        Cuántas veces supera un post la mediana de vistas de 90 días (views / median_views).
        Retorna None si no hay mediana (datos insuficientes) o el post no tiene vistas.
        """
        if not median_views or median_views <= 0 or views is None or views < 0:
            return None
        return round(views / median_views, 2)

    @staticmethod
    def calculate_growth_series(daily_data: List[Dict]) -> List[Dict]:
        """
        Deriva la serie diaria de crecimiento de seguidores:
        altas (follows), bajas (unfollows) y neto por día — AD-9.
        """
        series = []
        for item in daily_data:
            follows = int(item.get('follows') or 0)
            unfollows = int(item.get('unfollows') or 0)
            series.append({
                'date': item.get('date') or '',
                'follows': follows,
                'unfollows': unfollows,
                'net': follows - unfollows,
            })
        return series

    def _get_median_views_90d(self, instagram_account_id: int) -> Optional[float]:
        """Mediana de vistas de los posts publicados en los últimos 90 días."""
        cutoff = datetime.utcnow() - timedelta(days=90)
        result = self.db.table('posts').select(
            'id, post_performance(impressions)'
        ).eq('instagram_account_id', instagram_account_id).eq(
            'status', 'published'
        ).gte('publication_date', cutoff.isoformat()).execute()
        views = [
            int((p.get('post_performance') or {}).get('impressions') or 0)
            for p in (result.data or []) if p
        ]
        return self.calculate_median_views(views)

    def _get_follower_growth(self, instagram_account_id: int, days: int) -> Dict:
        """Serie de altas/bajas y toques en botones de contacto desde los snapshots diarios — AD-9."""
        cutoff = (datetime.utcnow() - timedelta(days=days)).date()
        result = self.db.table('instagram_account_snapshots').select(
            'date, follows, unfollows, profile_links_taps'
        ).eq('instagram_account_id', instagram_account_id).gte(
            'date', cutoff.isoformat()
        ).order('date').execute()
        rows = result.data or []
        series = self.calculate_growth_series(rows)
        return {
            'follower_growth': {
                'series': series,
                'follows': sum(d['follows'] for d in series),
                'unfollows': sum(d['unfollows'] for d in series),
                'net': sum(d['net'] for d in series),
            },
            'contact_button_taps': sum(int(r.get('profile_links_taps') or 0) for r in rows),
        }

    def get_swipe_file(self, instagram_account_id: int) -> Dict:
        """
        Swipe File: primera línea de los posts publicados en los últimos 90 días,
        clasificada por fórmula de gancho y ordenada por Outlier Multiple, más el
        agregado por fórmula. Sin Gemini (score_hook es determinista).
        Los Trial Reels llevan su reels_skip_rate para comparar ganchos (AD-10).
        """
        cutoff = datetime.utcnow() - timedelta(days=90)
        result = self.db.table('posts').select(
            'id, content, trial_graduation, '
            'post_performance(impressions, reach, shares, reels_skip_rate)'
        ).eq('instagram_account_id', instagram_account_id).eq(
            'status', 'published'
        ).gte('publication_date', cutoff.isoformat()).execute()
        posts = [p for p in (result.data or []) if p]

        def _perf(post: Dict) -> Dict:
            perf = post.get('post_performance') or {}
            return (perf[0] if perf else {}) if isinstance(perf, list) else perf

        median_views = self.calculate_median_views(
            [int(_perf(p).get('impressions') or 0) for p in posts]
        )

        items: List[Dict] = []
        by_formula: Dict[int, Dict] = {}
        for post in posts:
            lines = [l.strip() for l in (post.get('content') or '').splitlines() if l.strip()]
            if not lines:
                continue
            perf = _perf(post)
            scored = score_hook(lines[0])
            outlier = self.calculate_outlier_multiple(int(perf.get('impressions') or 0), median_views)
            items.append({
                'post_id': post.get('id'),
                'hook_text': lines[0],
                'formula_id': scored['formula_id'],
                'formula_name': scored['formula_name'],
                'outlier_multiple': outlier,
                'sends_per_reach': self.calculate_sends_per_reach(
                    int(perf.get('shares') or 0), int(perf.get('reach') or 0)
                ),
                'is_trial': post.get('trial_graduation') is not None,
                'reels_skip_rate': perf.get('reels_skip_rate'),
            })
            if scored['formula_id'] is not None:
                agg = by_formula.setdefault(scored['formula_id'], {
                    'formula_id': scored['formula_id'],
                    'formula_name': scored['formula_name'],
                    'count': 0,
                    'outliers': [],
                })
                agg['count'] += 1
                if outlier is not None:
                    agg['outliers'].append(outlier)

        def _by_outlier(value: Optional[float]):
            return (value is not None, value or 0)

        items.sort(key=lambda it: _by_outlier(it['outlier_multiple']), reverse=True)
        formulas = [
            {
                'formula_id': agg['formula_id'],
                'formula_name': agg['formula_name'],
                'count': agg['count'],
                'avg_outlier': (
                    round(sum(agg['outliers']) / len(agg['outliers']), 2) if agg['outliers'] else None
                ),
            }
            for agg in by_formula.values()
        ]
        formulas.sort(key=lambda f: _by_outlier(f['avg_outlier']), reverse=True)
        return {'items': items, 'by_formula': formulas}

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
        tz = account_info['timezone']

        # 2. Obtener posts desde BD
        posts = self._get_posts_from_db(instagram_account_id, days)

        if not posts:
            # Siempre incluir audiencia aunque no haya posts en el período
            audience = self._analyze_audience(instagram_account_id, days)
            result = self._get_empty_analytics(account_info)
            result['data']['audience'] = audience
            result['data']['timezone'] = tz
            # Altas/bajas y toques de contacto son de cuenta: se muestran aunque no haya posts
            result['data']['overview'].update(
                self._get_follower_growth(instagram_account_id, days)
            )
            result['data']['overview']['strategy_mode'] = get_strategy_mode(instagram_account_id)
            return result

        # 3. Calcular todas las métricas
        median_views = self._get_median_views_90d(instagram_account_id)
        overview = self._calculate_overview(
            posts,
            account_info,
            compare,
            median_views=median_views
        )
        overview.update(self._get_follower_growth(instagram_account_id, days))
        overview['strategy_mode'] = get_strategy_mode(instagram_account_id)

        # 4. Si compare=True, calcular crecimiento vs periodo anterior
        if compare:
            growth = self._calculate_growth(instagram_account_id, days, posts)
            overview['growth'] = growth

        # 5. Análisis por tipo de contenido
        by_content_type = self._analyze_by_content_type(posts)

        # 6. Top posts (por engagement), posts recientes (por fecha) y mejores horarios por día
        top_posts = self._get_top_posts(posts, limit=3, median_views=median_views)
        top_posts_by_outlier = self._get_top_posts(
            posts, limit=3, median_views=median_views, sort_by='outlier'
        )
        recent_posts = self._get_recent_posts(posts, limit=5, median_views=median_views)
        best_times_by_weekday = self._calculate_best_times_by_weekday(posts, tz)

        # 7. Tendencias temporales
        engagement_trend = self._calculate_trends(posts, days, tz)

        # 8. Analizar datos de audiencia (PRIMERO para obtener online_hours)
        audience = self._analyze_audience(instagram_account_id, days)

        # 9. Mejores horarios con algoritmo avanzado (actividad + performance histórico)
        # Score = (online_followers * 0.4) + (engagement_rate * 0.6)
        best_posting_times = self._calculate_best_posting_times(
            instagram_account_id,
            audience.get('online_hours', {}),
            days,
            tz
        )

        # 10. Insights y recomendaciones
        insights = self._generate_insights(
            posts,
            best_posting_times,
            by_content_type,
            tz
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
                'top_posts_by_outlier': top_posts_by_outlier,
                'recent_posts': recent_posts,
                'best_times_by_weekday': best_times_by_weekday,
                'engagement_trend': engagement_trend,
                'best_posting_times': best_posting_times,
                'insights': insights,
                'timezone': tz
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
                'followers_count, username, account_name, reach, profile_views, '
                'primary_timezone, detected_timezone'
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
            'profile_views': result.data.get('profile_views', 0),
            # Zona en la que se calculan horas, días y tendencias (AD-14)
            'timezone': effective_timezone(result.data),
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
            'post_performance(likes, comments, shares, saves, reach, impressions, '
            'total_interactions, reels_skip_rate)'
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

        # Excluir posts sin instagram_post_id — son posts marcados como "published"
        # por el sistema pero que nunca se publicaron realmente en Instagram
        all_rows = [p for p in (result.data or []) if p is not None]
        posts = [p for p in all_rows if p.get('instagram_post_id')]

        skipped = len(all_rows) - len(posts)
        if skipped:
            logger.warning(
                f"⚠️  {skipped} posts sin instagram_post_id excluidos del análisis "
                f"(publicados via stub, no están en Instagram)"
            )

        logger.info(
            f"📊 Obtenidos {len(posts)} posts para cuenta {instagram_account_id}"
        )

        return posts

    def _calculate_overview(
        self,
        posts: List[Dict],
        account_info: Dict,
        include_growth: bool = False,
        median_views: Optional[float] = None
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
        reach = account_info.get('reach', 0)

        def _perf_int(perf: dict, key: str) -> int:
            return int(perf.get(key) or 0)

        # Descomponer métricas individuales (fixes hardcoded-0 bug for comments/saves)
        total_likes = sum(_perf_int(p.get('post_performance') or {}, 'likes') for p in posts)
        total_comments = sum(_perf_int(p.get('post_performance') or {}, 'comments') for p in posts)
        total_saves = sum(_perf_int(p.get('post_performance') or {}, 'saves') for p in posts)
        total_interactions = total_likes + total_comments + total_saves

        # Views = sum of post-level impressions (no account-level impressions in v22.0+)
        total_impressions = sum(
            _perf_int(p.get('post_performance') or {}, 'impressions') for p in posts
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

        # Sends per Reach medio: los posts sin alcance no cuentan (AD-7)
        sends_ratios = [
            r for r in (
                self.calculate_sends_per_reach(
                    _perf_int(p.get('post_performance') or {}, 'shares'),
                    _perf_int(p.get('post_performance') or {}, 'reach'),
                )
                for p in posts
            ) if r is not None
        ]
        avg_sends_per_reach = round(sum(sends_ratios) / len(sends_ratios), 4) if sends_ratios else None

        overview = {
            'total_posts': total_posts,
            'follower_count': account_info['follower_count'],
            'reach': reach,
            'views': total_impressions,
            'impressions': total_impressions,  # keep for backwards compat
            'total_likes': total_likes,
            'total_comments': total_comments,
            'total_saves': total_saves,
            'total_interactions': total_interactions,
            'avg_interactions_per_post': round(avg_interactions_per_post, 1),
            'engagement_rate': round(avg_engagement_rate, 2),
            'median_views': median_views,
            'avg_sends_per_reach': avg_sends_per_reach,
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
            "engaged_demographics": {},
            "online_hours": {},
            "top_locations": {
                "countries": [],
                "cities": []
            }
        }

        # 1. Crecimiento de seguidores (snapshots diarios)
        # Limitar a 365 días máximo para evitar payloads enormes con 'all'
        display_days = min(days, 365)
        cutoff_date = datetime.utcnow().date() - timedelta(days=display_days)
        try:
            growth_result = self.db.table('instagram_account_snapshots').select(
                'date, follower_count'
            ).eq(
                'instagram_account_id', instagram_account_id
            ).gte(
                'date', cutoff_date.isoformat()
            ).order('date', desc=False).execute()

            if growth_result.data:
                snapshots = growth_result.data
                snapshot_dict = {s['date']: s['follower_count'] for s in snapshots}

                # Forward-fill: generar un punto por cada día del rango para que
                # el eje X del gráfico siempre cubra el período seleccionado.
                # Días sin sync heredan el último valor conocido (no se pone 0).
                today = datetime.utcnow().date()
                prev_count = snapshots[0]['follower_count']
                result = []
                current = cutoff_date + timedelta(days=1)
                while current <= today:
                    dk = current.isoformat()
                    count = snapshot_dict.get(dk, prev_count)
                    change = count - prev_count if result else 0
                    result.append({
                        'date': dk,
                        'follower_count': count,
                        'change': change
                    })
                    prev_count = count
                    current += timedelta(days=1)

                audience_data["follower_growth"] = result

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

                    if metric_type == 'engaged_audience_demographics':
                        audience_data["engaged_demographics"] = data
                    else:
                        audience_data["demographics"][metric_type] = data

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
        tz = self._account_timezone(instagram_account_id)
        best_times = self._calculate_best_posting_times(
            instagram_account_id,
            audience.get('online_hours', {}),
            days,
            tz
        )

        audience['best_posting_times'] = best_times
        audience['timezone'] = tz

        return audience

    def _account_timezone(self, instagram_account_id: int) -> str:
        """Zona efectiva de la cuenta: primary ?? detected ?? UTC (AD-14)."""
        res = self.db.table('instagram_accounts')\
            .select('primary_timezone, detected_timezone')\
            .eq('id', instagram_account_id)\
            .execute()
        return effective_timezone(res.data[0] if res.data else None)

    def _calculate_best_posting_times(
        self,
        instagram_account_id: int,
        online_hours: Dict,
        days: int,
        tz: str
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

                    post_date = to_local(datetime.fromisoformat(
                        pub_date.replace('Z', '+00:00')
                    ), tz)
                    hour = post_date.hour

                    perf = post.get('post_performance') or {}
                    likes = perf.get('likes') or 0
                    comments = perf.get('comments') or 0
                    reach = perf.get('reach') or 0
                    total_interactions = likes + comments + (perf.get('saves') or 0)

                    # Usar engagement_rate cuando hay reach; si no, total_interactions como proxy
                    if reach > 0:
                        engagement_rate = ((likes + comments) / reach) * 100
                    else:
                        engagement_rate = float(
                            total_interactions or (likes + comments)
                        )

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

    def _get_top_posts(
        self,
        posts: List[Dict],
        limit: int = 3,
        median_views: Optional[float] = None,
        sort_by: str = 'engagement'
    ) -> List[Dict]:
        """
        Obtiene los posts con mejor engagement (o mayor Outlier Multiple).

        Args:
            posts: Lista de posts
            limit: Número de posts a retornar
            median_views: Mediana de vistas de 90 días para el Outlier Multiple
            sort_by: 'engagement' u 'outlier' (sin dato de outlier van al final)

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
                'caption': (post.get('content') or '')[:100],
                'media_url': post.get('media_url') or '',
                'permalink': permalink,
                'timestamp': post.get('publication_date') or '',
                'post_type': (post.get('post_type') or 'IMAGE').upper(),
                'likes': int(likes or 0),
                'comments': int(comments or 0),
                'engagement': int(engagement or 0),
                'shares': int(perf.get('shares') or 0),
                'impressions': int(perf.get('impressions') or 0),
                'reach': int(perf.get('reach') or 0),
                'saved': int(perf.get('saves') or 0),
                'sends_per_reach': self.calculate_sends_per_reach(
                    int(perf.get('shares') or 0), int(perf.get('reach') or 0)
                ),
                'outlier_multiple': self.calculate_outlier_multiple(
                    int(perf.get('impressions') or 0), median_views
                ),
                'avg_watch_time_ms': 0,
                'total_watch_time_ms': 0,
            })

        if sort_by == 'outlier':
            def sort_key(x: Dict):
                return (x['outlier_multiple'] is not None, x['outlier_multiple'] or 0)
        else:
            def sort_key(x: Dict):
                return x['engagement']

        top = sorted(posts_with_engagement, key=sort_key, reverse=True)[:limit]

        return top

    def _get_recent_posts(
        self,
        posts: List[Dict],
        limit: int = 3,
        median_views: Optional[float] = None
    ) -> List[Dict]:
        """Retorna los posts más recientes por fecha de publicación."""
        posts_with_data = []

        for post in posts:
            raw_perf = post.get('post_performance')  # None si aún no se sincronizó
            perf = raw_perf or {}
            likes = perf.get('likes', 0)
            comments = perf.get('comments', 0)
            shares = perf.get('shares', 0)
            reach_val = int(perf.get('reach') or 0)
            impressions_val = int(perf.get('impressions') or 0)
            sends_per_reach = self.calculate_sends_per_reach(int(shares or 0), reach_val)
            outlier_multiple = self.calculate_outlier_multiple(impressions_val, median_views)

            instagram_post_id = post.get('instagram_post_id', '')
            permalink = (
                f"https://www.instagram.com/p/{instagram_post_id}/"
                if instagram_post_id else ''
            )
            posts_with_data.append({
                'id': instagram_post_id,
                'caption': (post.get('content') or '')[:100],
                'media_url': post.get('media_url') or '',
                'permalink': permalink,
                'timestamp': post.get('publication_date') or '',
                'post_type': (post.get('post_type') or 'IMAGE').upper(),
                'likes': int(likes or 0),
                'comments': int(comments or 0),
                'shares': int(shares or 0),
                'engagement': int((likes or 0) + (comments or 0)),
                'impressions': impressions_val,
                'reach': reach_val,
                'saved': int(perf.get('saves') or 0),
                'sends_per_reach': sends_per_reach,
                'outlier_multiple': outlier_multiple,
                'avg_watch_time_ms': 0,
                'total_watch_time_ms': 0,
                'has_stats': raw_perf is not None,
            })

        recent = sorted(
            posts_with_data,
            key=lambda x: x['timestamp'] or '',
            reverse=True
        )[:limit]

        return recent

    def _calculate_best_times_by_weekday(self, posts: List[Dict], tz: str) -> Dict:
        """
        Calcula los mejores horarios de publicación por día de semana.

        Usa solo performance histórico (engagement_rate por hora × día).
        Solo incluye días con >= 3 posts para que el dato sea estadísticamente confiable.

        Returns:
            Dict con claves 0-6 (0=lunes, 6=domingo), cada una con lista
            de hasta 3 slots [{ hour, avg_engagement, posts_count }] ordenados desc.
        """
        by_day_hour: Dict[int, Dict[int, Dict]] = {}

        for post in posts:
            pub_date = post.get('publication_date')
            if not pub_date:
                continue
            try:
                dt = to_local(datetime.fromisoformat(
                    pub_date.replace('Z', '+00:00')
                ), tz)
                weekday = dt.weekday()   # 0=lunes … 6=domingo
                hour = dt.hour

                perf = post.get('post_performance') or {}
                likes = perf.get('likes') or 0
                comments = perf.get('comments') or 0
                reach = perf.get('reach') or 0
                total_interactions = likes + comments + (perf.get('shares') or 0) + (perf.get('saves') or 0)
                if reach > 0:
                    engagement_rate = ((likes + comments) / reach) * 100
                else:
                    engagement_rate = float(total_interactions or (likes + comments))

                by_day_hour.setdefault(weekday, {}).setdefault(
                    hour, {'total_engagement': 0.0, 'count': 0}
                )
                by_day_hour[weekday][hour]['total_engagement'] += engagement_rate
                by_day_hour[weekday][hour]['count'] += 1
            except Exception:
                continue

        result: Dict[int, list] = {}
        for weekday, hours in by_day_hour.items():
            total_posts_for_day = sum(h['count'] for h in hours.values())
            if total_posts_for_day < 3:
                continue

            slots = [
                {
                    'hour': f"{hour:02d}:00",
                    'avg_engagement': round(
                        data['total_engagement'] / data['count'], 1
                    ),
                    'posts_count': data['count']
                }
                for hour, data in hours.items()
            ]
            slots.sort(key=lambda x: x['avg_engagement'], reverse=True)
            result[weekday] = slots[:3]

        return result

    def get_empirical_scheduling_data(
        self,
        instagram_account_id: int,
        days: int = 90
    ) -> Dict:
        """
        Resumen compacto de horarios óptimos basado en histórico real de la cuenta,
        listo para inyectar en un prompt de Gemini o usar directamente (sin llamar a IA).

        Reutiliza _get_posts_from_db, _analyze_audience, _calculate_best_posting_times
        y _calculate_best_times_by_weekday sin modificarlos (ver design.md §1).

        Returns:
            Dict con 'has_data', 'top_times' (top 3 horas globales), 'best_times_by_weekday'
            (weekday idx 0=lunes -> mejor hora "HH:00", solo días con >=3 posts) y
            'summary_text' (resumen de 1 línea para el prompt).
        """
        posts = self._get_posts_from_db(instagram_account_id, days)
        tz = self._account_timezone(instagram_account_id)
        if not posts:
            return {
                'timezone': tz,
                'has_data': False,
                'top_times': [],
                'best_times_by_weekday': {},
                'summary_text': ""
            }

        audience = self._analyze_audience(instagram_account_id, days)
        best_posting_times = self._calculate_best_posting_times(
            instagram_account_id, audience.get('online_hours', {}), days, tz
        )
        weekday_slots = self._calculate_best_times_by_weekday(posts, tz)

        def _slot_count(slot: Dict) -> int:
            return slot.get('posts_count', slot.get('count', 0))

        best_times_by_weekday = {
            day: slots[0]['hour']
            for day, slots in weekday_slots.items()
            if slots and sum(_slot_count(s) for s in slots) >= 3
        }

        has_data = bool(best_times_by_weekday)
        top_times = [slot['hour'] for slot in best_posting_times[:3]] if has_data else []

        summary_text = ""
        if has_data:
            day_names = ['Lun', 'Mar', 'Miér', 'Jue', 'Vie', 'Sáb', 'Dom']
            parts = [
                f"{day_names[day] if isinstance(day, int) and 0 <= day < 7 else str(day)[:3]} {hour}"
                for day, hour in best_times_by_weekday.items()
            ]
            summary_text = ", ".join(parts) + " — basado en tu histórico real"

        return {
            'timezone': tz,
            'has_data': has_data,
            'top_times': top_times,
            'best_times_by_weekday': best_times_by_weekday,
            'summary_text': summary_text
        }

    def get_visual_performance_data(
        self,
        instagram_account_id: int,
        days: int = 180
    ) -> List[Dict]:
        """
        Fila cruda por post publicado: tema/objetos/mood visual (de visual_analyses,
        vía drive_file_id) + métricas reales de rendimiento. No agrega ni calcula
        ninguna correlación — eso lo hace el código que genera Gemini con
        code_execution (ver services/hermes/skills.py); esto solo junta los datos.
        """
        query = self.db.table('posts').select(
            'drive_file_id, post_type, publication_date, '
            'post_performance(likes, comments, shares, saves, reach, impressions, '
            'total_interactions, reels_skip_rate)'
        ).eq('instagram_account_id', instagram_account_id).eq(
            'status', 'published'
        ).not_.is_('drive_file_id', 'null')

        if days < 3650:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            query = query.gte('publication_date', cutoff_date.isoformat())

        posts_res = query.execute()
        posts = [p for p in (posts_res.data or []) if p is not None]
        if not posts:
            return []

        drive_file_ids = [p['drive_file_id'] for p in posts if p.get('drive_file_id')]
        analyses_res = self.db.table('visual_analyses').select(
            'drive_file_id, gemini_description'
        ).in_('drive_file_id', drive_file_ids).execute()
        analyses_by_file = {
            row['drive_file_id']: row.get('gemini_description') or {}
            for row in (analyses_res.data or [])
        }

        rows = []
        for post in posts:
            description = analyses_by_file.get(post['drive_file_id'])
            if not description:
                continue
            perf = post.get('post_performance') or {}
            if isinstance(perf, list):
                perf = perf[0] if perf else {}
            rows.append({
                'objects': description.get('objects', []),
                'theme': description.get('theme', ''),
                'mood': description.get('mood', ''),
                'post_type': post.get('post_type'),
                'publication_date': post.get('publication_date'),
                'likes': perf.get('likes', 0),
                'comments': perf.get('comments', 0),
                'saves': perf.get('saves', 0),
                'reach': perf.get('reach', 0),
                'impressions': perf.get('impressions', 0),
                'total_interactions': perf.get('total_interactions', 0),
            })
        return rows

    def _calculate_trends(self, posts: List[Dict], days: int, tz: str) -> List[Dict]:
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

                post_date = to_local(datetime.fromisoformat(
                    pub_date.replace('Z', '+00:00')
                ), tz)
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

        # Zero-pad solo para rangos cortos/medios (<=180 días) para no generar payloads enormes
        if days <= 180:
            today = local_today(tz)
            start_date = today - timedelta(days=days)
            for i in range(days):
                dk = (start_date + timedelta(days=i + 1)).isoformat()
                daily_engagement.setdefault(dk, {
                    'date': dk, 'likes': 0, 'comments': 0, 'engagement': 0, 'posts_count': 0
                })

        return sorted(daily_engagement.values(), key=lambda x: x['date'])

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
        by_content_type: Dict,
        tz: str
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

                date_obj = to_local(datetime.fromisoformat(
                    pub_date.replace('Z', '+00:00')
                ), tz)
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
                    'reach': account_info.get('reach', 0),
                    'views': 0,
                    'impressions': 0,
                    'total_likes': 0,
                    'total_comments': 0,
                    'total_saves': 0,
                    'total_interactions': 0,
                    'avg_interactions_per_post': 0,
                    'engagement_rate': 0,
                },
                'by_content_type': {},
                'top_posts': [],
                'engagement_trend': [],
                'best_posting_times': [],
                'insights': []
            }
        }
