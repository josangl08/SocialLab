"""
Analytics Routes

Endpoints para gestión de métricas y sincronización de analytics
de Instagram según especificación del Master Plan.

Author: SocialLab
Date: 2025-01-19
"""
import logging
import json
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

def full_sync_account(instagram_service, db_client, user_id, instagram_account_id_db):
    """
    Realiza una sincronización completa: métricas de cuenta, audiencia y posts.

    Guarda datos en:
    - instagram_accounts (métricas básicas)
    - instagram_account_snapshots (snapshot diario)
    - audience_demographics (demografía)
    - online_followers_data (actividad por hora)
    - posts + post_performance (contenido)
    """
    today = datetime.utcnow().date()

    # 1. Sincronizar métricas principales de la cuenta (15+ métricas)
    logger.info(f"🔄 Sincronizando métricas de cuenta {instagram_account_id_db}")
    try:
        # Obtener datos básicos del perfil + métricas (usa rango de últimos 7 días por defecto)
        account_insights = instagram_service.get_account_insights(days_back=7)

        # Log para debug: ver qué métricas obtuvimos
        logger.info(f"📊 Métricas obtenidas: "
                   f"followers={account_insights.get('follower_count')}, "
                   f"reach={account_insights.get('reach')}, "
                   f"profile_views={account_insights.get('profile_views')}, "
                   f"interactions={account_insights.get('total_interactions')}")

        # Actualizar tabla principal instagram_accounts
        update_data = {
            "followers_count": account_insights.get("follower_count", 0),
            "reach": account_insights.get("reach", 0),
            "profile_views": account_insights.get("profile_views", 0),
            "username": account_insights.get("username", ""),
            "account_name": account_insights.get("name", ""),
            "profile_picture_url": account_insights.get("profile_picture_url", ""),
            "last_sync_at": datetime.now().isoformat(),
        }
        db_client.table("instagram_accounts").update(update_data).eq("id", instagram_account_id_db).execute()
        logger.info(f"✅ Cuenta {instagram_account_id_db} actualizada")

        # Guardar snapshot diario en instagram_account_snapshots
        # NOTA: impressions NO existe en account-level insights de Instagram API
        # account_insights viene de get_account_insights() que incluye perfil + métricas
        snapshot_data = {
            "instagram_account_id": instagram_account_id_db,
            "date": today.isoformat(),
            "follower_count": account_insights.get("follower_count", 0),  # Del perfil
            "following_count": 0,  # No disponible en API básica
            "media_count": account_insights.get("media_count", 0),  # Del perfil
            "reach": account_insights.get("reach", 0),  # De insights
            "impressions": 0,  # No disponible en account-level (solo media-level)
            "profile_views": account_insights.get("profile_views", 0),  # De insights (últimos 7 días)
            "website_clicks": 0,  # No incluida en get_account_insights básico
            "email_contacts": 0,  # Requiere configuración especial
            "phone_call_clicks": 0,  # Requiere configuración especial
            "text_message_clicks": 0,  # Requiere configuración especial
            "get_directions_clicks": 0  # Requiere configuración especial
        }
        # Delete + Insert para evitar problemas con upsert en múltiples columnas
        db_client.table("instagram_account_snapshots").delete().match({
            'instagram_account_id': instagram_account_id_db,
            'date': today.isoformat()
        }).execute()

        result = db_client.table("instagram_account_snapshots").insert(snapshot_data).execute()
        logger.info(f"✅ Snapshot diario guardado: {snapshot_data['date']}")

    except Exception as e:
        logger.error(f"❌ Error sincronizando métricas de cuenta {instagram_account_id_db}: {e}")

    # 2. Sincronizar datos de audiencia (demografía + actividad)
    logger.info(f"🔄 Sincronizando datos de audiencia para cuenta {instagram_account_id_db}")
    try:
        audience_insights = instagram_service.get_audience_insights()
        logger.info(f"📊 DEBUG audience_insights retornado: {audience_insights}")

        # Guardar demografía en audience_demographics
        if audience_insights.get('demographics'):
            demographics_to_upsert = []
            for metric_type, data in audience_insights['demographics'].items():
                logger.info(f"📊 DEBUG {metric_type}: {len(data) if isinstance(data, dict) else 0} entradas")
                # Solo guardar si hay datos reales (no dict vacío)
                if data and len(data) > 0:
                    demographics_to_upsert.append({
                        'instagram_account_id': instagram_account_id_db,
                        'sync_date': today.isoformat(),
                        'metric_type': metric_type,
                        'data': data
                    })
                else:
                    logger.warning(f"⚠️  {metric_type} está vacío, omitiendo...")

            if demographics_to_upsert:
                # Buscar el constraint único correcto para demographics
                # Por simplicidad, hacer delete + insert individual por cada metric_type
                for demo_data in demographics_to_upsert:
                    # Eliminar registro anterior si existe
                    db_client.table('audience_demographics').delete().match({
                        'instagram_account_id': demo_data['instagram_account_id'],
                        'metric_type': demo_data['metric_type']
                    }).execute()
                    # Insertar nuevo registro
                    db_client.table('audience_demographics').insert(demo_data).execute()
                logger.info(f"✅ Datos demográficos actualizados ({len(demographics_to_upsert)} métricas)")

        # Guardar actividad de seguidores en online_followers_data
        # Solo guardar si hay datos reales (no dict vacío {})
        online_hours = audience_insights.get('online_hours')
        if online_hours and len(online_hours) > 0:
            # Delete + Insert para evitar problemas con upsert
            db_client.table('online_followers_data').delete().match({
                'instagram_account_id': instagram_account_id_db,
                'sync_date': today.isoformat()
            }).execute()

            online_data = {
                'instagram_account_id': instagram_account_id_db,
                'sync_date': today.isoformat(),
                'hour_data': online_hours  # Supabase maneja JSONB automáticamente
            }
            db_client.table('online_followers_data').insert(online_data).execute()
            logger.info(f"✅ Actividad de seguidores actualizada ({len(online_hours)} horas)")
        else:
            logger.warning(f"⚠️  No hay datos de actividad de seguidores disponibles aún")

    except Exception as e:
        logger.error(f"❌ Error sincronizando datos de audiencia: {e}")

    # 3. Sincronizar posts y su performance
    logger.info(f"🔄 Sincronizando posts para cuenta {instagram_account_id_db}")
    try:
        instagram_service.sync_posts_to_database(
            db_client=db_client,
            user_id=user_id,
            instagram_account_id_db=instagram_account_id_db
        )
        logger.info(f"✅ Posts sincronizados correctamente")
    except Exception as e:
        logger.error(f"❌ Error sincronizando posts: {e}")

    logger.info(f"✅ Sincronización completa finalizada para cuenta {instagram_account_id_db}")

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
            full_sync_account,
            instagram_service=instagram_service,
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
    current_user: dict = Depends(get_current_user),
    instagram_service: InstagramInsightsService = Depends(get_instagram_service)
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
        # Inicializar servicio de analytics con el servicio de Instagram inyectado
        analytics_service = AnalyticsService(
            db_client=supabase,
            instagram_service=instagram_service
        )

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

