"""
Analytics Routes

Endpoints para gestión de métricas y sincronización de analytics
de Instagram según especificación del Master Plan.

Author: SocialLab
Date: 2025-01-19
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from datetime import datetime
from typing import Dict, List
from pydantic import BaseModel

from auth.jwt_handler import get_current_user
from database import supabase
from services.instagram_insights import InstagramInsightsService
from services.analytics import AnalyticsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


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

@router.post(
    "/sync/{instagram_account_id}",
    summary="Sincronizar Posts y Métricas de Cuenta Instagram"
)
async def sync_instagram_analytics(
    instagram_account_id: int,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    instagram_service: InstagramInsightsService = Depends(get_instagram_service)
):
    """
    Inicia sincronización de posts y métricas de una cuenta Instagram específica.

    Este endpoint permite sincronizar cualquier cuenta Instagram especificada
    por su ID, con validación de permisos del usuario actual.

    Args:
        instagram_account_id: ID de la cuenta Instagram en la base de datos
        background_tasks: FastAPI background tasks
        current_user: Usuario autenticado actual
        instagram_service: Servicio de Instagram Insights

    Returns:
        {
            "message": "Mensaje de confirmación",
            "instagram_account_id": ID de la cuenta sincronizada
        }

    Raises:
        HTTPException 403: Si el usuario no tiene permisos
        HTTPException 404: Si la cuenta no existe
        HTTPException 500: Error interno
    """
    try:
        # Verificar que la cuenta existe y pertenece al usuario
        result = supabase.table('instagram_accounts').select(
            'id, user_id, is_active'
        ).eq('id', instagram_account_id).single().execute()

        if not result.data:
            raise HTTPException(
                status_code=404,
                detail=f"Cuenta Instagram {instagram_account_id} no encontrada"
            )

        account = result.data

        # Verificar permisos: el usuario debe ser dueño de la cuenta
        if account['user_id'] != current_user['id']:
            raise HTTPException(
                status_code=403,
                detail="No tienes permiso para sincronizar esta cuenta"
            )

        # Verificar que la cuenta esté activa
        if not account.get('is_active', True):
            raise HTTPException(
                status_code=400,
                detail="La cuenta Instagram está inactiva"
            )

        # Añadir tarea de sincronización en segundo plano
        background_tasks.add_task(
            instagram_service.sync_posts_to_database,
            db_client=supabase,
            user_id=current_user['id'],
            instagram_account_id_db=instagram_account_id
        )

        logger.info(
            f"Iniciada sincronización para cuenta Instagram "
            f"{instagram_account_id} (user: {current_user['id']})"
        )

        return {
            "message": (
                "La sincronización de posts y métricas de Instagram "
                "ha comenzado en segundo plano. "
                "Los datos se actualizarán en breve."
            ),
            "instagram_account_id": instagram_account_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error al iniciar sincronización para cuenta "
            f"{instagram_account_id}: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Error interno al iniciar la sincronización: {str(e)}"
        )


@router.post(
    "/sync",
    summary="[DEPRECATED] Sincronizar Posts y Métricas de Instagram",
    deprecated=True
)
async def sync_instagram_data_deprecated(
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    instagram_service: InstagramInsightsService = Depends(get_instagram_service)
):
    """
    **DEPRECATED**: Usar /sync/{instagram_account_id} en su lugar.

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

@router.get("/overview")
async def get_analytics_overview(
    days: int = 365,
    compare: bool = False,
    current_user: dict = Depends(get_current_user)
) -> Dict:
    """
    Obtener análisis completo de métricas desde la base de datos (OPTIMIZADO).

    DECISIÓN DE DISEÑO (Fase 7):
    En lugar de 4 endpoints separados (/overview, /by-content-type, /trends,
    /recommendations), este endpoint retorna TODA la información en una sola
    llamada para máxima eficiencia.

    Razones de esta decisión:
    - 1 HTTP request vs 4 = 75% menos latencia
    - 1 query a BD vs 4 queries repetidas = más eficiente
    - Datos consistentes (mismo snapshot de BD)
    - El dashboard siempre necesita todos los datos
    - Más simple para el cliente

    **Parámetros:**
    - days: Número de días hacia atrás (1-3650, default: 365)
    - compare: Si True, incluye crecimiento vs periodo anterior

    **Ventajas:**
    - Carga instantánea (~200ms vs ~2-3seg de Instagram API)
    - No consume API calls de Instagram
    - Datos actualizados automáticamente cada hora via cron job

    **Response incluye:**
    - overview: Métricas generales (con growth opcional)
    - by_content_type: Análisis por tipo de contenido
    - top_posts: Top 3 posts por engagement
    - engagement_trend: Tendencia temporal
    - best_posting_times: Mejores horarios (top 4)
    - insights: Recomendaciones dinámicas
    - last_sync_at: Timestamp de última sincronización
    """
    try:
        # Inicializar servicio de analytics
        analytics_service = AnalyticsService(db_client=supabase)

        # Obtener análisis completo
        result = analytics_service.get_comprehensive_analytics(
            user_id=current_user['id'],
            instagram_account_id=None,  # Se obtiene internamente
            days=days,
            compare=compare
        )

        return result

    except ValueError as e:
        # Error de negocio (cuenta no encontrada, etc.)
        raise HTTPException(status_code=404, detail=str(e))

    except Exception as e:
        logger.error(
            f"Error obteniendo analytics para user {current_user['id']}: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener analytics: {str(e)}"
        )
