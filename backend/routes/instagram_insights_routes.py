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


@router.get("/posts/top")
async def get_top_posts(
    limit: int = 10,
    instagram_service: InstagramInsightsService = Depends(get_instagram_service)
) -> Dict:
    """
    Obtener los posts con mejor engagement

    - **limit**: Número de posts a retornar (máximo 25)
    """
    try:
        limit = min(limit, 25)  # Limitar a 25 posts
        top_posts = instagram_service.get_top_posts(limit=limit)

        return {
            "success": True,
            "data": top_posts,
            "count": len(top_posts)
        }
    except Exception as e:
        logger.error(f"Error obteniendo top posts: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener top posts: {str(e)}"
        )


@router.get("/analytics/best-times")
async def get_best_posting_times(
    days_back: int = 30,
    instagram_service: InstagramInsightsService = Depends(get_instagram_service)
) -> Dict:
    """
    Analizar mejores horarios para publicar

    - **days_back**: Días hacia atrás para analizar (máximo 90)
    """
    try:
        days_back = min(days_back, 90)  # Limitar a 90 días
        best_times = instagram_service.analyze_best_posting_times(days_back=days_back)

        return {
            "success": True,
            "data": best_times,
            "days_analyzed": days_back
        }
    except Exception as e:
        logger.error(f"Error analizando mejores horarios: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error al analizar mejores horarios: {str(e)}"
        )


@router.get("/analytics/engagement-trend")
async def get_engagement_trend(
    days: int = 7,
    instagram_service: InstagramInsightsService = Depends(get_instagram_service)
) -> Dict:
    """
    Obtener tendencia de engagement de los últimos días

    - **days**: Número de días hacia atrás (máximo 30)
    """
    try:
        days = min(days, 30)  # Limitar a 30 días
        trend = instagram_service.get_engagement_trend(days=days)

        return {
            "success": True,
            "data": trend,
            "days": days
        }
    except Exception as e:
        logger.error(f"Error obteniendo tendencia de engagement: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener tendencia: {str(e)}"
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


@router.get("/analytics/overview")
async def get_analytics_overview(
    instagram_service: InstagramInsightsService = Depends(get_instagram_service)
) -> Dict:
    """
    Obtener resumen completo de analytics (para el Dashboard)

    Combina:
    - Insights del perfil (período de 28 días)
    - Top 3 posts
    - Tendencia de 7 días
    - Mejores 4 horarios
    """
    try:
        # --- Obtención de datos de la API ---
        # Usamos 'days_28' para obtener un alcance más representativo
        profile_insights = instagram_service.get_account_insights(period='days_28')
        top_posts = instagram_service.get_top_posts(limit=3)
        engagement_trend = instagram_service.get_engagement_trend(days=7)
        best_times = instagram_service.analyze_best_posting_times(days_back=30)
        
        # --- Cálculo de Tasa de Engagement Real ---
        follower_count = profile_insights.get('follower_count', 0)
        avg_engagement_rate = 0

        # Usamos una lista más amplia de posts recientes para un promedio más fiable
        recent_posts = instagram_service.get_media_list(limit=25)

        if follower_count > 0 and recent_posts:
            total_rate = 0
            posts_with_rate = 0
            for post in recent_posts:
                likes = post.get('like_count', 0)
                comments = post.get('comments_count', 0)
                engagement_count = likes + comments
                
                # Tasa de engagement para este post
                rate = (engagement_count / follower_count) * 100
                total_rate += rate
                posts_with_rate += 1
            
            if posts_with_rate > 0:
                avg_engagement_rate = total_rate / posts_with_rate

        return {
            "success": True,
            "data": {
                "overview": {
                    "total_posts": profile_insights.get('media_count', 0),
                    "follower_count": follower_count,
                    "profile_views": profile_insights.get('profile_views', 0), # Sigue siendo 0 por limitación de API
                    "reach": profile_insights.get('reach', 0), # Ahora es de 28 días
                    "impressions": profile_insights.get('impressions', 0),
                    "engagement_rate": round(avg_engagement_rate, 2), # Tasa de engagement real
                    "accounts_engaged": profile_insights.get('accounts_engaged', 0),
                    "total_interactions": profile_insights.get('total_interactions', 0)
                },
                "top_posts": top_posts,
                "engagement_trend": engagement_trend,
                "best_posting_times": best_times[:4]
            }
        }
    except Exception as e:
        logger.error(f"Error obteniendo overview de analytics: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener overview: {str(e)}"
        )
