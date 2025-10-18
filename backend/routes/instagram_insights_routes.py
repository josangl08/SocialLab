"""
Rutas para obtener insights de Instagram
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from datetime import datetime
from typing import Dict, List
from pydantic import BaseModel

from auth.jwt_handler import get_current_user
from database import supabase
from services.instagram_insights import InstagramInsightsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/instagram", tags=["Instagram Insights"])


def get_instagram_service(current_user: dict = Depends(get_current_user)) -> InstagramInsightsService:
    """
    Dependency para obtener el servicio de Instagram configurado para el usuario actual
    """
    try:
        # Obtener credenciales de Instagram del usuario
        result = supabase.table('instagram_accounts').select('*').eq('user_id', current_user['id']).eq('is_active', True).single().execute()

        if not result.data:
            raise HTTPException(
                status_code=404,
                detail="No hay cuenta de Instagram conectada. Por favor conecta tu cuenta primero."
            )

        instagram_account = result.data

        # Verificar si el token ha expirado
        expires_at_str = instagram_account.get('expires_at')
        if expires_at_str:
            expires_at = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
            if datetime.now(expires_at.tzinfo) >= expires_at:
                raise HTTPException(
                    status_code=401,
                    detail="El token de Instagram ha expirado. Por favor vuelve a conectar tu cuenta."
                )

        access_token = instagram_account.get('long_lived_access_token')
        instagram_id = instagram_account.get('instagram_business_account_id')

        if not access_token or not instagram_id:
            raise HTTPException(
                status_code=500,
                detail="Datos de Instagram incompletos en la base de datos."
            )

        return InstagramInsightsService(access_token, instagram_id)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo servicio de Instagram: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error al configurar el servicio de Instagram: {str(e)}"
        )

@router.post("/sync", summary="Sincronizar Posts y Métricas de Instagram")
async def sync_instagram_data(
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    instagram_service: InstagramInsightsService = Depends(get_instagram_service)
):
    """
    Inicia un proceso en segundo plano para sincronizar todos los posts y sus métricas
    de rendimiento desde la API de Instagram a la base de datos local.
    """
    try:
        # Obtener el ID de la cuenta de instagram en nuestra BD
        result = supabase.table('instagram_accounts').select('id').eq('user_id', current_user['id']).eq('is_active', True).single().execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="No se encontró una cuenta de Instagram activa para este usuario.")
        
        instagram_account_id_db = result.data['id']

        # Añadir la tarea de sincronización para que se ejecute en segundo plano
        background_tasks.add_task(
            instagram_service.sync_posts_to_database,
            db_client=supabase, 
            user_id=current_user['id'], 
            instagram_account_id_db=instagram_account_id_db
        )

        return {"message": "La sincronización de posts de Instagram ha comenzado en segundo plano. Los datos se actualizarán en breve."}
    except Exception as e:
        logger.error(f"Error al iniciar la sincronización de Instagram: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error interno al iniciar la sincronización: {str(e)}")


@router.get("/profile/insights")
async def get_profile_insights(
    period: str = "day",
    instagram_service: InstagramInsightsService = Depends(get_instagram_service)
) -> Dict:
    """
    Obtener insights generales del perfil de Instagram

    - **period**: 'day', 'week', 'days_28' - Período para las métricas
    """
    try:
        insights = instagram_service.get_account_insights(period=period)
        return {
            "success": True,
            "data": insights,
            "period": period
        }
    except Exception as e:
        logger.error(f"Error obteniendo insights del perfil: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener insights del perfil: {str(e)}"
        )


@router.get("/posts/recent")
async def get_recent_posts(
    limit: int = 25,
    instagram_service: InstagramInsightsService = Depends(get_instagram_service)
) -> Dict:
    """
    Obtener posts recientes

    - **limit**: Número de posts a retornar (máximo 100)
    """
    try:
        limit = min(limit, 100)
        posts = instagram_service.get_media_list(limit=limit)

        return {
            "success": True,
            "data": posts,
            "count": len(posts)
        }
    except Exception as e:
        logger.error(f"Error obteniendo posts recientes: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener posts recientes: {str(e)}"
        )

@router.get("/analytics/cached-overview")
async def get_cached_analytics_overview(
    days: int = 365,
    current_user: dict = Depends(get_current_user)
) -> Dict:
    """
    Obtener resumen de analytics desde la base de datos local (cache).

    Mucho más rápido que llamar a Instagram API.
    Los datos se actualizan automáticamente cada hora via cron job.

    **Parámetros:**
    - days: Número de días hacia atrás para análisis (default: 365, max: 3650)

    **Ventajas:**
    - Carga instantánea (~200ms vs ~2-3seg)
    - No consume API calls de Instagram
    - Datos actualizados automáticamente cada hora

    **Response incluye:**
    - overview: Métricas generales
    - top_posts: Top 3 posts desde DB
    - engagement_trend: Tendencia según días especificados
    - best_posting_times: Mejores horarios
    - insights: Insights dinámicos generados
    - last_sync_at: Timestamp de última sincronización
    """
    # Limitar el rango de días (permitir hasta 10 años de historia)
    days = max(1, min(days, 3650))
    try:
        # Obtener cuenta de Instagram del usuario
        account_result = supabase.table('instagram_accounts')\
            .select('id, instagram_business_account_id, last_sync_at, followers_count, username, account_name')\
            .eq('user_id', current_user['id'])\
            .eq('is_active', True)\
            .single()\
            .execute()

        if not account_result.data:
            raise HTTPException(
                status_code=404,
                detail="No hay cuenta de Instagram conectada"
            )

        instagram_account_id = account_result.data['id']
        last_sync_at = account_result.data.get('last_sync_at')
        follower_count = account_result.data.get('followers_count', 0)

        # --- 1. Obtener posts desde DB para el rango de días especificado ---
        from datetime import datetime, timedelta
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        posts_result = supabase.table('posts')\
            .select(
                'id, content, media_url, '
                'publication_date, instagram_post_id, post_type, '
                'post_performance(likes, comments, saves, reach, impressions)'
            )\
            .eq('instagram_account_id', instagram_account_id)\
            .eq('status', 'published')\
            .gte('publication_date', cutoff_date.isoformat())\
            .order('publication_date', desc=True)\
            .execute()

        posts = posts_result.data or []

        # Filtrar posts None y posts sin datos válidos
        posts = [p for p in posts if p is not None]

        logger.info(f"📊 Obtenidos {len(posts)} posts de los últimos {days} días para cuenta {instagram_account_id}")
        if len(posts) == 0:
            logger.warning(f"⚠️  No se encontraron posts. Cutoff date: {cutoff_date.isoformat()}")

        # --- 2. Calcular métricas agregadas ---
        total_posts = len(posts)
        total_likes = sum(
            (p.get('post_performance') or {}).get('likes', 0) for p in posts
        )
        total_comments = sum(
            (p.get('post_performance') or {}).get('comments', 0) for p in posts
        )
        total_reach = sum(
            (p.get('post_performance') or {}).get('reach', 0) for p in posts
        )
        total_impressions = sum(
            (p.get('post_performance') or {}).get('impressions', 0) for p in posts
        )

        # --- 3. Top posts (ordenar por engagement) ---
        posts_with_engagement = []
        for post in posts:
            perf = post.get('post_performance') or {}
            likes = perf.get('likes', 0)
            comments = perf.get('comments', 0)
            engagement = likes + comments

            # Generar permalink de Instagram si tenemos el post_id
            instagram_post_id = post.get('instagram_post_id', '')
            permalink = f"https://www.instagram.com/p/{instagram_post_id}/" if instagram_post_id else ''

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

        # Ordenar por engagement y tomar top 3
        top_posts = sorted(
            posts_with_engagement,
            key=lambda x: x['engagement'],
            reverse=True
        )[:3]

        # --- 4. Tendencia de engagement ---
        # Los posts ya están filtrados por fecha en la consulta SQL
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

        engagement_trend = sorted(
            daily_engagement.values(),
            key=lambda x: x['date']
        )

        # --- 5. Mejores horarios para publicar ---
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
                engagement = (
                    perf.get('likes', 0) + perf.get('comments', 0)
                )

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

        # --- 6. Calcular engagement rate promedio ---
        avg_engagement_rate = 0
        if total_posts > 0:
            total_engagement = total_likes + total_comments
            # Usar follower_count real si está disponible, sino 1000 como base
            base_followers = follower_count if follower_count > 0 else 1000
            avg_engagement_rate = (total_engagement / total_posts / base_followers) * 100

        # --- 7. Generar insights dinámicos ---
        insights = []

        # Analizar mejor día de la semana
        from collections import defaultdict
        day_engagement = defaultdict(lambda: {'total': 0, 'count': 0})
        day_names = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']

        # Analizar tipo de contenido
        type_engagement = defaultdict(lambda: {'total': 0, 'count': 0})

        for post in posts:
            try:
                pub_date = post.get('publication_date')
                if pub_date:
                    date_obj = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
                    day_of_week = date_obj.weekday()

                    perf = post.get('post_performance') or {}
                    engagement = perf.get('likes', 0) + perf.get('comments', 0)

                    day_engagement[day_of_week]['total'] += engagement
                    day_engagement[day_of_week]['count'] += 1

                    # Tipo de contenido
                    post_type = post.get('post_type', 'image').lower()
                    type_engagement[post_type]['total'] += engagement
                    type_engagement[post_type]['count'] += 1
            except:
                continue

        # Calcular mejor día
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
                "description": f"Los posts del {day_names[best_day]} obtienen {best_day_avg:.0f} interacciones promedio",
                "icon": "calendar-check"
            })

        # Mejor horario (tomamos el primero de best_times)
        if best_times and len(best_times) > 0:
            best_hour = best_times[0]
            insights.append({
                "type": "best_hour",
                "title": "Horario óptimo",
                "description": f"{best_hour['hour']} es tu hora pico con {best_hour['avg_engagement_rate']:.0f} interacciones promedio",
                "icon": "clock"
            })

        # Tipo de contenido
        best_type = None
        best_type_avg = 0
        for ptype, data in type_engagement.items():
            if data['count'] > 0:
                avg = data['total'] / data['count']
                if avg > best_type_avg:
                    best_type_avg = avg
                    best_type = ptype

        if best_type and best_type_avg > 0:
            type_names = {'image': 'imágenes', 'video': 'videos', 'reel': 'reels', 'story': 'historias'}
            type_display = type_names.get(best_type, best_type)
            insights.append({
                "type": "content_type",
                "title": "Tipo de contenido",
                "description": f"Los posts con {type_display} tienen mayor interacción ({best_type_avg:.0f} promedio)",
                "icon": "image"
            })

        # Recomendación combinada
        if best_day is not None and best_times:
            insights.append({
                "type": "recommendation",
                "title": "Recomendación",
                "description": f"Publica los {day_names[best_day]} alrededor de las {best_times[0]['hour']} para maximizar el engagement",
                "icon": "lightbulb"
            })

        return {
            "success": True,
            "source": "cache",  # Indicador de que viene de cache
            "last_sync_at": last_sync_at,
            "data": {
                "overview": {
                    "total_posts": total_posts,
                    "follower_count": follower_count,
                    "profile_views": 0,  # Instagram API no proporciona este dato
                    "reach": total_reach,
                    "impressions": total_impressions,
                    "engagement_rate": round(avg_engagement_rate, 2),
                    "accounts_engaged": 0,
                    "total_interactions": total_likes + total_comments
                },
                "top_posts": top_posts,
                "engagement_trend": engagement_trend,
                "best_posting_times": best_times,
                "insights": insights
            }
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.error(
            f"Error obteniendo cached analytics: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener analytics desde cache: {str(e)}"
        )
