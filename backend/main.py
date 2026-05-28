import os
import sys
import logging
from datetime import datetime
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Reducir verbosidad de httpx
logging.getLogger("httpx").setLevel(logging.WARNING)

# Asegurar que los logs se muestren inmediatamente
sys.stdout.flush()

# Importar cliente de Supabase
from database.supabase_client import get_supabase_client
supabase = get_supabase_client()

# --- Inicialización de la Aplicación FastAPI ---
app = FastAPI(
    title="SocialLab API",
    description="La API para el planificador de publicaciones con IA.",
    version="0.1.0"
)

# --- Función de Sincronización Automática de Métricas ---
def sync_all_accounts_metrics():
    """
    Job que se ejecuta cada hora para sincronizar métricas
    de todas las cuentas de Instagram activas.
    """
    logger.info("⏰ Iniciando sincronización automática de métricas...")

    try:
        from services.instagram_insights import InstagramInsightsService

        all_accounts = supabase.table('instagram_accounts')\
            .select('id, user_id, long_lived_access_token, instagram_business_account_id, is_active')\
            .execute()

        accounts_data = [
            acc for acc in (all_accounts.data or [])
            if acc.get('is_active') is not False
        ]

        if not accounts_data:
            logger.info("No hay cuentas activas para sincronizar")
            return

        logger.info(f"📋 Encontradas {len(accounts_data)} cuentas activas para sincronizar")

        synced_count = 0
        failed_count = 0

        for account in accounts_data:
            try:
                instagram_service = InstagramInsightsService(
                    access_token=account['long_lived_access_token'],
                    instagram_account_id=account['instagram_business_account_id']
                )

                instagram_service.sync_posts_to_database(
                    db_client=supabase,
                    user_id=account['user_id'],
                    instagram_account_id_db=account['id']
                )

                supabase.table('instagram_accounts')\
                    .update({'last_sync_at': datetime.utcnow().isoformat()})\
                    .eq('id', account['id'])\
                    .execute()

                synced_count += 1
                logger.info(f"✅ Cuenta {account['id']} sincronizada correctamente")

            except Exception as e:
                logger.error(f"❌ Error sincronizando cuenta {account['id']}: {e}")
                failed_count += 1

        logger.info(f"📊 Sincronización completada: {synced_count} exitosas, {failed_count} fallidas")

    except Exception as e:
        logger.error(f"❌ Error en sync_all_accounts_metrics: {e}")

# --- Lifecycle Events ---
@app.on_event("startup")
async def startup_event():
    """Inicializa servicios al arrancar la aplicación."""
    logger.info("🚀 Iniciando SocialLab API...")

    try:
        from services.scheduler.post_scheduler import PostScheduler
        scheduler = PostScheduler()
        logger.info("✅ PostScheduler inicializado correctamente")
    except Exception as e:
        logger.error(f"❌ Error al inicializar PostScheduler: {e}")

    try:
        from apscheduler.triggers.cron import CronTrigger
        from services.scheduler.post_scheduler import PostScheduler

        scheduler = PostScheduler()
        scheduler.scheduler.add_job(
            sync_all_accounts_metrics,
            trigger=CronTrigger(hour='*'),  # Cada hora
            id='sync_instagram_metrics',
            replace_existing=True,
            max_instances=1
        )
        logger.info("✅ Cron job de sincronización de métricas configurado (ejecuta cada hora)")
    except Exception as e:
        logger.error(f"❌ Error configurando cron job de métricas: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """Cierra servicios al apagar la aplicación."""
    logger.info("🛑 Apagando SocialLab API...")

    try:
        from services.scheduler.post_scheduler import PostScheduler
        scheduler = PostScheduler()
        scheduler.shutdown(wait=True)
        logger.info("✅ PostScheduler cerrado correctamente")
    except Exception as e:
        logger.error(f"❌ Error al cerrar PostScheduler: {e}")

# --- Configuración de CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Importar routers core existentes ---
from routes.templates import router as templates_router
from routes.content_generation import router as content_router
from routes.template_sync_routes import router as template_sync_router
from routes.analytics_routes import router as analytics_router
from routes.drive_routes import router as drive_router
from routes.scheduler_routes import router as scheduler_router
from routes.posts_routes import router as posts_router

# --- Importar nuevos routers segregados ---
from routes.auth_routes import router as auth_router
from routes.ai_routes import router as ai_router
from routes.instagram_routes import router_no_prefix as instagram_router
from routes.posts_crud_routes import router as posts_crud_router

# --- Registrar todos los routers ---
app.include_router(auth_router)
app.include_router(ai_router)
app.include_router(instagram_router)
app.include_router(posts_crud_router)

app.include_router(templates_router)
app.include_router(content_router)
app.include_router(template_sync_router)
app.include_router(analytics_router)
app.include_router(drive_router)
app.include_router(scheduler_router)
app.include_router(posts_router)

@app.get("/")
def read_root():
    """Endpoint raíz para verificar que la API está funcionando."""
    return {"status": "ok", "message": "Bienvenido a la API de SocialLab"}