import os
import sys
import asyncio
import logging
from datetime import date, timedelta
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional
from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from starlette.exceptions import HTTPException as StarletteHTTPException
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

# Import tras basicConfig a propósito: el filtro se instala en los handlers ya creados, antes de
# que cualquier otro módulo registre una URL con el access_token
from utils.redaction import install_log_redaction, redact_secrets
install_log_redaction()

# Reducir verbosidad de httpx
logging.getLogger("httpx").setLevel(logging.WARNING)

# Asegurar que los logs se muestren inmediatamente
sys.stdout.flush()

# Importar cliente de Supabase
from database.supabase_client import get_supabase_client, get_supabase_admin_client
from utils.encryption import decrypt_token
from utils.timezones import utc_now_naive
supabase = get_supabase_client()
admin_supabase = get_supabase_admin_client()

# Límite de concurrencia para la ejecución semanal del agente (rate limits de Gemini/Instagram)
AGENT_CONCURRENCY_LIMIT = 2

# --- Inicialización de la Aplicación FastAPI ---
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Arranca y apaga los servicios con la aplicación."""
    await startup_event()
    yield
    await shutdown_event()


app = FastAPI(
    title="SocialLab API",
    description="La API para el planificador de publicaciones con IA.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.exception_handler(StarletteHTTPException)
async def redacting_http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Los `detail` que incluyen `str(e)` de requests llevan la URL con el access_token."""
    if isinstance(exc.detail, str):
        exc.detail = redact_secrets(exc.detail)
    return await http_exception_handler(request, exc)

# --- Función de Sincronización Automática de Métricas ---
def sync_all_accounts_metrics():
    """
    Job que se ejecuta cada hora para sincronizar métricas
    de todas las cuentas de Instagram activas.
    """
    logger.info("⏰ Iniciando sincronización automática de métricas...")

    try:
        from services.instagram_insights import InstagramInsightsService

        all_accounts = admin_supabase.table('instagram_accounts')\
            .select('id, user_id, long_lived_access_token, instagram_business_account_id, login_type, is_active')\
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
                    access_token=decrypt_token(account['long_lived_access_token']),
                    instagram_account_id=account['instagram_business_account_id'],
                    login_type=account['login_type']
                )

                instagram_service.sync_posts_to_database(
                    db_client=admin_supabase,
                    user_id=account['user_id'],
                    instagram_account_id_db=account['id']
                )

                admin_supabase.table('instagram_accounts')\
                    .update({'last_sync_at': utc_now_naive().isoformat()})\
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

def sync_all_accounts_story_insights():
    """
    Job horario (minuto 30): guarda las Stories activas de cada cuenta y sus métricas
    antes de que caduquen (24 h). Un fallo en una cuenta no afecta a las demás.
    """
    try:
        from services.instagram_insights import InstagramInsightsService

        all_accounts = admin_supabase.table('instagram_accounts')\
            .select('id, user_id, long_lived_access_token, instagram_business_account_id, login_type, is_active')\
            .execute()

        for account in all_accounts.data or []:
            if account.get('is_active') is False:
                continue
            try:
                service = InstagramInsightsService(
                    access_token=decrypt_token(account['long_lived_access_token']),
                    instagram_account_id=account['instagram_business_account_id'],
                    login_type=account['login_type']
                )
                service.sync_story_insights(account=account, db_client=admin_supabase)
            except Exception as e:
                logger.error(f"❌ Error sincronizando Stories de la cuenta {account['id']}: {e}")

    except Exception as e:
        logger.error(f"❌ Error en sync_all_accounts_story_insights: {e}")

async def _run_agent_for_all_accounts_async(accounts_data):
    """Ejecuta run_agent para cada cuenta de forma concurrente, acotado por AGENT_CONCURRENCY_LIMIT."""
    from services.agent_service import run_agent

    semaphore = asyncio.Semaphore(AGENT_CONCURRENCY_LIMIT)

    async def _run_one(account):
        async with semaphore:
            try:
                await asyncio.to_thread(run_agent, account['id'])
                logger.info(f"✅ Agente ejecutado con éxito para cuenta {account['id']}")
            except Exception as e:
                logger.error(f"❌ Error ejecutando agente para cuenta {account['id']}: {e}")

    await asyncio.gather(*(_run_one(account) for account in accounts_data))


def run_agent_for_all_accounts():
    """
    Cron job semanal (domingos 22:00) para ejecutar el agente en todas las cuentas.
    Procesa hasta AGENT_CONCURRENCY_LIMIT cuentas en paralelo.
    """
    logger.info("⏰ Iniciando ejecución automática semanal de agentes...")
    try:
        all_accounts = admin_supabase.table('instagram_accounts')\
            .select('id, is_active')\
            .execute()

        accounts_data = [
            acc for acc in (all_accounts.data or [])
            if acc.get('is_active') is not False
        ]

        asyncio.run(_run_agent_for_all_accounts_async(accounts_data))
    except Exception as e:
        logger.error(f"❌ Error en run_agent_for_all_accounts: {e}")


async def _run_monthly_strategy_for_all_accounts_async(accounts_data):
    """Ejecuta run_monthly_strategy_session para cada cuenta de forma concurrente,
    acotado por AGENT_CONCURRENCY_LIMIT, y envía la tarjeta de aprobación por
    Telegram solo cuando el borrador fue realmente creado (design.md — decisión #6:
    no reenviar tarjeta si ya había una campaña pendiente)."""
    from services.hermes.monthly_strategy import run_monthly_strategy_session
    from services.telegram_service import TelegramService

    semaphore = asyncio.Semaphore(AGENT_CONCURRENCY_LIMIT)

    async def _run_one(account):
        async with semaphore:
            try:
                result = await run_monthly_strategy_session(account['id'])
                if result.created and result.campaign_id and account.get('telegram_chat_id'):
                    campaign_res = admin_supabase.table('monthly_campaigns')\
                        .select('*').eq('id', result.campaign_id).execute()
                    if campaign_res.data:
                        await TelegramService().send_campaign_approval_card(
                            str(account['telegram_chat_id']), campaign_res.data[0]
                        )
                logger.info(
                    f"✅ Estrategia mensual procesada para cuenta {account['id']} "
                    f"(created={result.created}, error={result.error})"
                )
            except Exception as e:
                logger.error(f"❌ Error ejecutando estrategia mensual para cuenta {account['id']}: {e}")

    await asyncio.gather(*(_run_one(account) for account in accounts_data))


def _days_until_month_end(today: Optional[date] = None) -> int:
    """Días restantes (incluyendo hoy) hasta el último día del mes en curso."""
    today = today or date.today()
    if today.month == 12:
        next_month_first = date(today.year + 1, 1, 1)
    else:
        next_month_first = date(today.year, today.month + 1, 1)
    last_day_of_month = next_month_first - timedelta(days=1)
    return (last_day_of_month - today).days


def run_monthly_strategy_for_all_accounts():
    """
    Cron job diario (08:00). A partir de 2 días antes de fin de mes, dispara para
    cada cuenta activa la sesión de Hermes que redacta el borrador de campaña del
    mes siguiente (idempotente — ver supabase_create_monthly_campaign).
    """
    logger.info("⏰ Iniciando comprobación diaria de estrategia mensual...")
    try:
        days_left = _days_until_month_end()
        if days_left > 2:
            logger.info(f"📅 Faltan {days_left} días para fin de mes — aún no toca generar campañas")
            return

        all_accounts = admin_supabase.table('instagram_accounts')\
            .select('id, telegram_chat_id, is_active')\
            .execute()

        accounts_data = [
            acc for acc in (all_accounts.data or [])
            if acc.get('is_active') is not False
        ]

        asyncio.run(_run_monthly_strategy_for_all_accounts_async(accounts_data))
    except Exception as e:
        logger.error(f"❌ Error en run_monthly_strategy_for_all_accounts: {e}")


def send_daily_briefings_for_all_accounts():
    """
    Cron job diario (09:00) que envía por Telegram las publicaciones de hoy.
    """
    logger.info("⏰ Enviando resúmenes diarios de publicaciones...")
    try:
        import asyncio
        from services.telegram_service import TelegramService

        all_accounts = admin_supabase.table('instagram_accounts')\
            .select('id, telegram_chat_id, is_active')\
            .execute()

        accounts_data = [
            acc for acc in (all_accounts.data or [])
            if acc.get('is_active') is not False and acc.get('telegram_chat_id')
        ]

        for account in accounts_data:
            try:
                asyncio.run(TelegramService().send_daily_briefing(
                    account['id'],
                    str(account['telegram_chat_id'])
                ))
                logger.info(f"✅ Briefing enviado para cuenta {account['id']}")
            except Exception as e:
                logger.error(f"❌ Error enviando briefing para cuenta {account['id']}: {e}")
    except Exception as e:
        logger.error(f"❌ Error en send_daily_briefings_for_all_accounts: {e}")


def renew_drive_channels():
    """
    Cron job (cada 15 min) que renueva los canales de notificación push de Drive
    próximos a caducar — confirmado empíricamente que Google los expira en ~1h
    para este tipo de recurso, no en 24h/7 días como cabría asumir.
    """
    try:
        from services.drive_webhook_service import renew_expiring_channels
        renewed = renew_expiring_channels()
        if renewed:
            logger.info(f"✅ {renewed} canal(es) de Drive renovado(s)")
    except Exception as e:
        logger.error(f"❌ Error renovando canales de Drive: {e}")


def refresh_niche_insights():
    """
    Cron job mensual que refresca los niche_insights de todos los nichos detectados
    entre las cuentas existentes, para que estén vigentes sin depender de que una
    sesión de Hermes los pida bajo demanda. run_niche_research_skill ya evita la
    llamada real a Gemini si el insight sigue fresco.
    """
    try:
        from services.hermes.skills import resolve_niche, run_niche_research_skill
        supabase = get_supabase_admin_client()
        accounts = supabase.table('instagram_accounts').select('sector,purpose').execute().data or []
        niches = set()
        for account in accounts:
            niches.update(resolve_niche(account))
        for niche in niches:
            run_niche_research_skill(niche)
        logger.info(f"✅ Insights de nicho refrescados: {sorted(niches)}")
    except Exception as e:
        logger.error(f"❌ Error refrescando insights de nicho: {e}")

# --- Lifecycle Events ---
async def startup_event():
    """Inicializa servicios al arrancar la aplicación."""
    logger.info("🚀 Iniciando SocialLab API...")

    from utils.graph_api import warn_if_outdated
    warn_if_outdated()

    try:
        from services.scheduler.post_scheduler import PostScheduler
        scheduler = PostScheduler()
        logger.info("✅ PostScheduler inicializado correctamente")
    except Exception as e:
        logger.error(f"❌ Error al inicializar PostScheduler: {e}")

    try:
        from services.telegram_service import TelegramService
        await TelegramService().register_webhook(os.getenv("TELEGRAM_WEBHOOK_URL"))
        logger.info("✅ Telegram webhook registrado correctamente")
    except Exception as e:
        logger.error(f"❌ Error al registrar Telegram webhook: {e}")

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

        scheduler.scheduler.add_job(
            sync_all_accounts_story_insights,
            trigger=CronTrigger(minute=30),
            id='sync_story_insights',
            replace_existing=True,
            max_instances=1
        )
        logger.info("✅ Cron job de métricas de Stories configurado (cada hora, minuto 30)")

        from services.instagram_token import check_account_tokens
        scheduler.scheduler.add_job(
            check_account_tokens,
            trigger=CronTrigger(hour=7),
            id='check_instagram_tokens',
            replace_existing=True,
            max_instances=1
        )
        logger.info("✅ Cron job de caducidad de tokens de Instagram configurado (diario 07:00)")

        from services.instagram_token import refresh_expiring_tokens
        scheduler.scheduler.add_job(
            refresh_expiring_tokens,
            trigger=CronTrigger(hour=3),
            id='refresh_instagram_tokens',
            replace_existing=True,
            max_instances=1
        )
        logger.info("✅ Cron job de renovación de tokens de Instagram Login configurado (diario 03:00)")
        
        scheduler.scheduler.add_job(
            run_agent_for_all_accounts,
            trigger=CronTrigger(day_of_week='sun', hour=22),
            id='run_weekly_agents',
            replace_existing=True,
            max_instances=1
        )
        logger.info("✅ Cron job de agente semanal configurado (domingos 22:00)")

        scheduler.scheduler.add_job(
            run_monthly_strategy_for_all_accounts,
            trigger=CronTrigger(hour=8),
            id='run_monthly_strategy',
            replace_existing=True,
            max_instances=1
        )
        logger.info("✅ Cron job de estrategia mensual configurado (diario 08:00)")

        scheduler.scheduler.add_job(
            send_daily_briefings_for_all_accounts,
            trigger=CronTrigger(hour=9),
            id='send_daily_briefings',
            replace_existing=True,
            max_instances=1
        )
        logger.info("✅ Cron job de briefing diario configurado (09:00)")

        scheduler.scheduler.add_job(
            renew_drive_channels,
            trigger=CronTrigger(minute='*/15'),
            id='renew_drive_channels',
            replace_existing=True,
            max_instances=1
        )
        logger.info("✅ Cron job de renovación de canales Drive configurado (cada 15 min)")

        scheduler.scheduler.add_job(
            refresh_niche_insights,
            trigger=CronTrigger(day=1, hour=6),
            id='refresh_niche_insights',
            replace_existing=True,
            max_instances=1
        )
        logger.info("✅ Cron job de refresco de insights de nicho configurado (día 1 de cada mes, 06:00)")

        from services.thumbnail_store import cleanup_orphan_thumbnails
        scheduler.scheduler.add_job(
            cleanup_orphan_thumbnails,
            trigger=CronTrigger(hour=4),
            id='cleanup_orphan_thumbnails',
            replace_existing=True,
            max_instances=1
        )
        logger.info("✅ Cron job de limpieza de miniaturas huérfanas configurado (diario 04:00)")
    except Exception as e:
        logger.error(f"❌ Error configurando cron job de métricas: {e}")

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
from routes.drive_webhook_routes import router as drive_webhook_router
from routes.scheduler_routes import router as scheduler_router
from routes.posts_routes import router as posts_router

# --- Importar nuevos routers segregados ---
from routes.auth_routes import router as auth_router
from routes.ai_routes import router as ai_router
from routes.instagram_routes import router_no_prefix as instagram_router
from routes.telegram_routes import router as telegram_router
from routes.agent_routes import router as agent_router
from routes.drive_oauth_routes import router as drive_oauth_router

# --- Registrar todos los routers ---
app.include_router(auth_router)
app.include_router(ai_router)
app.include_router(instagram_router)
app.include_router(telegram_router)
app.include_router(agent_router)
app.include_router(drive_oauth_router)

app.include_router(templates_router)
app.include_router(content_router)
app.include_router(template_sync_router)
app.include_router(analytics_router)
app.include_router(drive_router)
app.include_router(drive_webhook_router)
app.include_router(scheduler_router)
app.include_router(posts_router)

@app.get("/")
def read_root():
    """Endpoint raíz para verificar que la API está funcionando."""
    return {"status": "ok", "message": "Bienvenido a la API de SocialLab"}