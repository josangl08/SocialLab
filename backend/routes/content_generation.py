"""
Content Generation API Routes
Endpoint principal para generación automática de contenido.
Integra: PROJECT 1 exports + Template Selector + Image Composer + Caption Generator.
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, ValidationError
from datetime import datetime
import asyncio
import json
import logging

import requests

from auth.dependencies import get_current_user, get_user_supabase_client
from models.schemas import (
    User,
    LintRequest,
    QualityReport,
    HumanizeRequest,
    HumanizeResponse,
    HookScoreRequest,
    HookScoreResponse,
    HookFormula,
    BeatsRequest,
    BeatsResponse,
    ReelRequest,
    ReelOut,
    CarouselRequest,
    CarouselOut,
    StoryRequest,
    StoryOut,
    RepurposeRequest,
    RepurposeOut,
    ProfileAuditRequest,
    ProfileAuditItem,
    ProfileAuditResponse,
    SwipeFileResponse,
    CommentsTriageResponse,
    CommentsTriageManualRequest,
    ProspectCommentsRequest,
    ProspectCommentsResponse,
    DmFunnelRequest,
    DmFunnelResponse,
)
from services import content_formats
from services.analytics import AnalyticsService
from services.instagram_insights import fetch_live_profile, fetch_media_comments
from services.content_quality import (
    lint_caption,
    humanize,
    score_hook,
    get_hook_formulas,
    time_beats,
    audit_profile,
)
from database.supabase_client import get_supabase_client
from supabase import Client
from services.google_drive_connector import get_drive_connector
from services.template_selector import get_template_selector
from services.image_composer import get_image_composer
from services.gemini_service import generate_gemini_content

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/content", tags=["Content Generation"])


# Schemas
class ContentGenerationRequest(BaseModel):
    """Schema para solicitud de generación."""
    export_id: Optional[str] = Field(None, description="ID del export de PROJECT 1")
    topic: Optional[str] = Field(None, description="Tema para generación genérica de caption")
    instagram_account_id: Optional[int] = Field(
        None,
        description="ID de cuenta Instagram destino"
    )
    format_type: str = Field(
        default='square',
        description="Formato de imagen: square | portrait | story"
    )
    caption_style: Optional[str] = Field(
        default='informative',
        description="Estilo del caption (informative, engaging, viral, analytical)"
    )
    language: Optional[str] = Field(
        default='es',
        description="Idioma del caption: 'es' (español) o 'en' (inglés)"
    )
    auto_publish: bool = Field(
        default=False,
        description="Publicar automáticamente"
    )
    scheduled_time: Optional[datetime] = Field(
        None,
        description="Hora programada (si no es inmediato)"
    )


class ContentGenerationResponse(BaseModel):
    """Schema de respuesta de generación."""
    success: bool
    message: str
    post_id: Optional[int] = None
    preview_url: Optional[str] = None
    caption: Optional[str] = None
    template_used: Optional[dict] = None
    metadata: Optional[dict] = None


class QueueStatusResponse(BaseModel):
    """Schema de estado de cola."""
    total_pending: int
    total_processing: int
    total_completed: int
    total_failed: int
    recent_items: List[dict]


# Endpoints
@router.post("/generate", response_model=ContentGenerationResponse)
async def generate_content(
    request: ContentGenerationRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    supabase: Client = Depends(get_user_supabase_client)
):
    """
    Genera contenido automáticamente desde export de PROJECT 1.

    Flujo:
    1. Lee metadata.json del export
    2. Selecciona template apropiado
    3. Compone imagen final
    4. Genera caption con IA
    5. Guarda en posts (borrador o programado)
    6. Opcionalmente: publica en Instagram
    """
    try:
        user_id = current_user.id

        if not request.export_id and not request.topic:
            raise HTTPException(
                status_code=400,
                detail="Se requiere export_id o topic para generar contenido"
            )

        language = request.language if request.language else 'es'
        caption_style = request.caption_style if request.caption_style else 'informative'

        metadata = None
        template = None
        final_image_url = None
        is_mock_export = False

        if request.export_id:
            logger.info(f"🎬 Iniciando generación para export: {request.export_id}")

            export_data = None

            try:
                # 1. Obtener export de PROJECT 1 desde Google Drive
                drive = get_drive_connector()
                project1_folder_id = get_project1_folder_id(user_id)

                if project1_folder_id and drive.service:
                    logger.info("📂 Buscando export en Google Drive...")
                    exports = drive.list_project1_exports(project1_folder_id)
                    export_data = next(
                        (e for e in exports if e['folder_name'] == request.export_id),
                        None
                    )

                    if export_data:
                        metadata = export_data.get('metadata')
                        if metadata:
                            logger.info("✅ Export encontrado en Google Drive")
                        else:
                            logger.warning("⚠️ Export encontrado pero sin metadata válido")
                    else:
                        logger.warning(f"⚠️ Export {request.export_id} no encontrado en Google Drive")
            except Exception as drive_error:
                logger.warning(f"⚠️ Error accediendo a Google Drive: {str(drive_error)}")

            if not metadata:
                logger.info("🎭 Intentando con datos mock...")
                metadata = get_mock_metadata(request.export_id)
                if metadata:
                    is_mock_export = True
                    logger.info("✅ Usando datos mock para generación")
                else:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Export {request.export_id} no encontrado ni en Google Drive ni en datos mock"
                    )

            logger.info(f"✅ Metadata cargado: {metadata.get('export_type')}")

            # 2. Seleccionar template apropiado
            template_selector = get_template_selector(supabase)
            template = template_selector.select_template(
                metadata=metadata,
                user_id=user_id,
                instagram_account_id=request.instagram_account_id
            )

            if not template:
                raise HTTPException(
                    status_code=404,
                    detail="No hay templates disponibles para este tipo de contenido"
                )

            logger.info(f"✅ Template seleccionado: {template['name']}")

            # 3. Procesar imagen (solo para exports reales, no mock)
            if not is_mock_export:
                main_graphic_name = metadata.get('files', {}).get('main_graphic')
                logger.info(f"🔍 Buscando gráfico: {main_graphic_name}")

                if not main_graphic_name:
                    raise HTTPException(
                        status_code=400,
                        detail="Export sin gráfico principal (main_graphic) en metadata.json"
                    )

                logger.info(f"📁 Listando archivos en folder {export_data['folder_id']}...")
                files_in_folder = drive.list_files(export_data['folder_id'])
                logger.info(f"📁 Archivos encontrados:")
                for f in files_in_folder:
                    logger.info(f"   - {f['name']}")

                graphic_file = next(
                    (f for f in files_in_folder if f['name'] == main_graphic_name),
                    None
                )

                if not graphic_file:
                    logger.error(f"❌ Gráfico '{main_graphic_name}' NO encontrado entre los archivos")
                    raise HTTPException(
                        status_code=404,
                        detail=f"Gráfico '{main_graphic_name}' no encontrado en la carpeta. Archivos disponibles: {[f['name'] for f in files_in_folder]}"
                    )

                logger.info(f"✅ Gráfico '{main_graphic_name}' encontrado con ID: {graphic_file['id']}")

                graphic_image_bytes = drive.download_file_bytes(graphic_file['id'])
                if graphic_image_bytes is None:
                    raise HTTPException(
                        status_code=500,
                        detail=f"No se pudo descargar el gráfico '{main_graphic_name}' desde Drive"
                    )

                logger.info(f"✅ Gráfico descargado: {main_graphic_name}")

                template_path = template.get('file_path') or template.get('image_url')

                if not template_path:
                    raise HTTPException(
                        status_code=400,
                        detail="Template sin imagen configurada"
                    )

                logger.info(f"🔍 Template path original: {template_path}")

                if template_path.startswith('http'):
                    if '/templates/' in template_path:
                        template_path = template_path.split('/templates/')[-1]
                        logger.info(f"✅ Ruta relativa extraída: {template_path}")
                    else:
                        raise HTTPException(
                            status_code=400,
                            detail=f"URL de template inválida: {template_path}"
                        )

                logger.info(f"⬇️ Descargando template desde Supabase Storage...")
                template_response = supabase.storage.from_('templates').download(template_path)
                template_image_bytes = template_response

                logger.info(f"✅ Template descargado: {template.get('name')}")

                image_composer = get_image_composer()
                template_config = template.get('layout_config', {})

                final_image_bytes = image_composer.compose_post(
                    template_image=template_image_bytes,
                    graphic_image=graphic_image_bytes,
                    template_config=template_config,
                    format_type=request.format_type
                )

                if not final_image_bytes:
                    raise HTTPException(
                        status_code=500,
                        detail="Error componiendo imagen final"
                    )

                logger.info("✅ Imagen final compuesta con template + gráfico")

                import base64
                final_image_base64 = base64.b64encode(final_image_bytes).decode('utf-8')
                final_image_url = f"data:image/png;base64,{final_image_base64}"

                logger.info("✅ Imagen convertida a base64 para preview (no guardada aún)")
            else:
                logger.info("🎭 Export mock: usando imagen del template")
                template_path = template.get('file_path') or template.get('image_url')

                if template_path:
                    if not template_path.startswith('http'):
                        final_image_url = supabase.storage.from_('templates').get_public_url(template_path)
                    else:
                        final_image_url = template_path
                    logger.info(f"✅ Usando imagen del template: {template.get('name')}")
                else:
                    logger.warning("⚠️ Template sin ruta de archivo, usando None")
                    final_image_url = None

            caption_prompt = build_caption_prompt(metadata, caption_style, language)

        else:
            logger.info(f"🎬 Iniciando generación genérica para tema: {request.topic}")
            metadata = {'export_type': 'generic', 'topic': request.topic}
            caption_prompt = build_generic_caption_prompt(request.topic, caption_style, language)

        # 4. Generar caption con IA
        logger.info(f"🎨 Generando caption - Estilo: {caption_style}, Idioma: {language}")

        try:
            caption = await generate_gemini_content(caption_prompt)
        except Exception as e:
            logger.error(f"❌ Error generando caption con Gemini: {str(e)}")
            caption = None

        if not caption:
            caption = generate_fallback_caption(metadata)

        logger.info("✅ Caption generado")

        # 5. NO crear post todavía - solo devolver datos para preview
        logger.info("📦 Preparando respuesta con preview (sin guardar en DB)")

        return ContentGenerationResponse(
            success=True,
            message='Preview generado - usa "Guardar" para almacenar' + (' (modo prueba)' if is_mock_export else ''),
            post_id=None,
            preview_url=final_image_url,
            caption=caption,
            template_used={
                'id': template.get('id') if template else 0,
                'name': template.get('name') if template else 'mock_template'
            } if template else None,
            metadata={
                'export_id': request.export_id,
                'topic': request.topic,
                'export_type': metadata.get('export_type'),
                'instagram_account_id': request.instagram_account_id,
                'format_type': request.format_type,
                'caption_style': request.caption_style,
                'template_id': template.get('id') if template else None,
                'is_mock': is_mock_export,
                'user_id': user_id
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error generando contenido: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/queue/status", response_model=QueueStatusResponse)
async def get_queue_status(
    current_user: User = Depends(get_current_user),
    supabase: Client = Depends(get_user_supabase_client)
):
    """Obtiene estado de la cola de generación."""
    try:
        user_id = current_user.id

        # Contar por estado
        pending = supabase.table('content_generation_queue').select(
            'id',
            count='exact'
        ).eq('user_id', user_id).eq('status', 'pending').execute()

        processing = supabase.table('content_generation_queue').select(
            'id',
            count='exact'
        ).eq('user_id', user_id).eq('status', 'processing').execute()

        completed = supabase.table('content_generation_history').select(
            'id',
            count='exact'
        ).eq('user_id', user_id).eq('status', 'completed').execute()

        failed = supabase.table('content_generation_history').select(
            'id',
            count='exact'
        ).eq('user_id', user_id).eq('status', 'failed').execute()

        # Items recientes
        recent = supabase.table('content_generation_queue').select(
            '*'
        ).eq('user_id', user_id).order(
            'created_at',
            desc=True
        ).limit(10).execute()

        return QueueStatusResponse(
            total_pending=pending.count or 0,
            total_processing=processing.count or 0,
            total_completed=completed.count or 0,
            total_failed=failed.count or 0,
            recent_items=recent.data
        )

    except Exception as e:
        logger.error(f"❌ Error obteniendo estado de cola: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history", response_model=List[dict])
async def get_generation_history(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    supabase: Client = Depends(get_user_supabase_client)
):
    """Obtiene historial de generaciones."""
    try:
        user_id = current_user.id

        result = supabase.table('content_generation_history').select(
            '*',
            'posts(id, caption, image_url, status)',
            'templates(id, name)'
        ).eq('user_id', user_id).order(
            'generated_at',
            desc=True
        ).limit(limit).execute()

        return result.data

    except Exception as e:
        logger.error(f"❌ Error obteniendo historial: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Motor de calidad determinista (sin Gemini, sin DB)
@router.post("/lint", response_model=QualityReport)
async def lint_content(
    request: LintRequest,
    current_user: User = Depends(get_current_user)
) -> dict:
    """Informe de calidad de un caption: corte móvil, hashtags, slop y gancho."""
    return lint_caption(request.caption, keywords=request.keywords, format=request.format or "post")


@router.post("/humanize", response_model=HumanizeResponse)
async def humanize_content(
    request: HumanizeRequest,
    current_user: User = Depends(get_current_user)
) -> dict:
    """Devuelve el texto limpio de léxico sintético, invisibles y em dashes repetidos."""
    text, changes = humanize(request.text, language=request.language or "es", extra_banned=request.extra_banned)
    return {"text": text, "changes": changes}


@router.post("/score-hook", response_model=HookScoreResponse)
async def score_hook_content(
    request: HookScoreRequest,
    current_user: User = Depends(get_current_user)
) -> dict:
    """Identifica la fórmula del gancho y lo puntúa de 0 a 100."""
    return score_hook(request.hook, strategy_mode=request.strategy_mode)


@router.post("/beats", response_model=BeatsResponse)
async def time_beats_content(
    request: BeatsRequest,
    current_user: User = Depends(get_current_user)
) -> dict:
    """Timecodes de cada beat de un guion de Reel a la velocidad de locución indicada."""
    return time_beats([b.model_dump() for b in request.beats], wpm=request.wpm or 165)


@router.get("/hook-formulas", response_model=List[HookFormula])
async def list_hook_formulas(
    strategy_mode: Optional[Literal["commercial_campaign", "personal_storyline"]] = None,
    current_user: User = Depends(get_current_user)
) -> list:
    """Catálogo de las 26 fórmulas; las recomendadas para `strategy_mode` primero."""
    return get_hook_formulas(strategy_mode)


# Generadores de formato (Gemini + caché 1 h, salida humanizada + QualityReport)
def _verify_account_access(account_id: int, supabase: Client) -> None:
    """La cuenta debe ser visible para el usuario (RLS del cliente de usuario)."""
    res = supabase.table('instagram_accounts').select('id').eq('id', account_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Cuenta de Instagram no encontrada")


async def _run_generator(coro):
    try:
        return await coro
    except ValidationError as e:
        # Hereda de ValueError: la salida de Gemini no encaja con los modelos de salida
        logger.error(f"Respuesta de Gemini no encaja con el schema: {e}")
        raise HTTPException(status_code=502, detail="La IA devolvió una respuesta no válida. Inténtalo de nuevo.")
    except ValueError as e:
        # json.JSONDecodeError hereda de ValueError: respuesta de Gemini no parseable
        if isinstance(e, json.JSONDecodeError):
            logger.error(f"Respuesta de Gemini no es JSON válido: {e}")
            raise HTTPException(status_code=502, detail="La IA devolvió una respuesta no válida. Inténtalo de nuevo.")
        raise HTTPException(status_code=422, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generando formato: {e}")
        raise HTTPException(status_code=502, detail="No se pudo generar el contenido con la IA.")


@router.post("/formats/reel", response_model=ReelOut)
async def generate_reel_format(
    request: ReelRequest,
    current_user: User = Depends(get_current_user),
    supabase: Client = Depends(get_user_supabase_client)
) -> ReelOut:
    """Guion de Reel: 3 ganchos puntuados, beats temporizados y texto en pantalla."""
    _verify_account_access(request.account_id, supabase)
    return await _run_generator(content_formats.generate_reel(
        request.account_id, request.topic, request.strategy_mode, request.language or "es"
    ))


@router.post("/formats/carousel", response_model=CarouselOut)
async def generate_carousel_format(
    request: CarouselRequest,
    current_user: User = Depends(get_current_user),
    supabase: Client = Depends(get_user_supabase_client)
) -> CarouselOut:
    """Carrusel de 6–10 diapositivas (cover, stake, ideas, recap, CTA)."""
    _verify_account_access(request.account_id, supabase)
    return await _run_generator(content_formats.generate_carousel(
        request.account_id, request.topic, request.slides, request.strategy_mode, request.language or "es"
    ))


@router.post("/formats/story", response_model=StoryOut)
async def generate_story_format(
    request: StoryRequest,
    current_user: User = Depends(get_current_user),
    supabase: Client = Depends(get_user_supabase_client)
) -> StoryOut:
    """Secuencia de 3–4 Stories con sticker interactivo."""
    _verify_account_access(request.account_id, supabase)
    return await _run_generator(content_formats.generate_story(
        request.account_id, request.topic, request.strategy_mode, request.language or "es"
    ))


@router.post("/formats/repurpose", response_model=RepurposeOut)
async def generate_repurpose_format(
    request: RepurposeRequest,
    current_user: User = Depends(get_current_user),
    supabase: Client = Depends(get_user_supabase_client)
) -> RepurposeOut:
    """Una transcripción → 3 Reels + 2 carruseles en una sola llamada a la IA."""
    _verify_account_access(request.account_id, supabase)
    return await _run_generator(content_formats.generate_repurpose(
        request.account_id, request.transcript, request.strategy_mode, request.language or "es"
    ))


@router.post("/audit-profile", response_model=ProfileAuditResponse)
async def audit_profile_endpoint(
    request: ProfileAuditRequest,
    current_user: User = Depends(get_current_user),
    supabase: Client = Depends(get_user_supabase_client)
) -> ProfileAuditResponse:
    """Auditoría de perfil: score determinista (rúbrica de 12 puntos) + bio sugerida (Gemini, cacheada).
    La bio del perfil no se modifica."""
    res = supabase.table('instagram_accounts').select('*').eq('id', request.account_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Cuenta de Instagram no encontrada")
    account = res.data[0]

    # bio y web no se guardan en BD: se leen del perfil en vivo (1 llamada, acción del usuario)
    try:
        profile = await asyncio.to_thread(fetch_live_profile, account)
        account = {**account, **{k: v for k, v in profile.items() if v}}
    except Exception as e:
        logger.warning(f"Auditoría sin datos en vivo del perfil {request.account_id}: {e}")

    audit = audit_profile(account)
    failed_tips = [it['tip'] for it in audit['items'] if not it['passed']]
    try:
        bio_rewrite: Optional[str] = await content_formats.generate_bio_rewrite(
            request.account_id,
            account.get('biography') or '',
            failed_tips,
            language=account.get('default_language') or 'es',
        )
    except Exception as e:
        # El score es determinista: si Gemini falla, la auditoría se devuelve sin bio
        logger.warning(f"No se pudo generar la bio sugerida para {request.account_id}: {e}")
        bio_rewrite = None

    return ProfileAuditResponse(
        score=audit['score'],
        items=[ProfileAuditItem(**it) for it in audit['items']],
        bio_rewrite=bio_rewrite,
    )


@router.get("/swipe-file/{account_id}", response_model=SwipeFileResponse)
async def get_swipe_file_endpoint(
    account_id: int,
    current_user: User = Depends(get_current_user),
    supabase: Client = Depends(get_user_supabase_client)
) -> SwipeFileResponse:
    """Swipe File de ganchos propios ordenados por Outlier Multiple y agregados por fórmula (sin Gemini)."""
    _verify_account_access(account_id, supabase)
    return SwipeFileResponse(**AnalyticsService(supabase).get_swipe_file(account_id))


# --- Endpoints de Conversión y Comunidad (Fase F): solo sugerencias, nada se escribe en Graph API ---

@router.get("/comments/{post_id}/triage", response_model=CommentsTriageResponse)
async def get_post_comments_triage(
    post_id: int,
    current_user: User = Depends(get_current_user),
    supabase: Client = Depends(get_user_supabase_client),
) -> CommentsTriageResponse:
    """Triaje de los comentarios de un post publicado (lectura Graph API cacheada 15 min)."""
    post_res = supabase.table('posts').select('id, instagram_account_id, instagram_post_id').eq('id', post_id).execute()
    if not post_res.data:
        raise HTTPException(status_code=404, detail="Post no encontrado")
    post = post_res.data[0]

    account_id = post.get('instagram_account_id')
    media_id = post.get('instagram_post_id')
    if not account_id or not media_id:
        return CommentsTriageResponse(source="unavailable", comments=[])

    acc_res = supabase.table('instagram_accounts').select('*').eq('id', account_id).execute()
    if not acc_res.data:
        raise HTTPException(status_code=404, detail="Cuenta de Instagram no encontrada")
    account = acc_res.data[0]

    raw_comments = content_formats.get_comments_from_cache(str(media_id))
    if raw_comments is None:
        try:
            raw_comments = await asyncio.to_thread(fetch_media_comments, account, str(media_id))
        except requests.HTTPError as e:
            # No se registra el mensaje: la URL lleva el access_token
            status = e.response.status_code if e.response is not None else None
            logger.warning(f"Graph API rechazó la lectura de comentarios del post {post_id} (HTTP {status})")
            return CommentsTriageResponse(source="unavailable", comments=[])
        except Exception as e:
            logger.warning(f"No se pudieron leer los comentarios del post {post_id}: {type(e).__name__}")
            return CommentsTriageResponse(source="unavailable", comments=[])
        content_formats.set_comments_in_cache(str(media_id), raw_comments)

    mode = await content_formats.resolve_strategy_mode(account_id)
    comments = await _run_generator(content_formats.triage_comments(
        raw_comments, strategy_mode=mode, language=account.get('default_language') or 'es',
        account_id=account_id,
    ))
    return CommentsTriageResponse(source="api", comments=comments)


async def _optional_account_mode(
    account_id: Optional[int], strategy_mode: Optional[str], supabase: Client
) -> str:
    """Estrategia explícita > campaña de la cuenta > personal (AD-2)."""
    if account_id:
        _verify_account_access(account_id, supabase)
    if strategy_mode:
        return strategy_mode
    if account_id:
        return await content_formats.resolve_strategy_mode(account_id)
    return "personal_storyline"


@router.post("/comments/triage", response_model=CommentsTriageResponse)
async def post_manual_comments_triage(
    request: CommentsTriageManualRequest,
    current_user: User = Depends(get_current_user),
    supabase: Client = Depends(get_user_supabase_client),
) -> CommentsTriageResponse:
    """Triaje de comentarios pegados por el usuario (fallback sin permiso de comentarios)."""
    mode = await _optional_account_mode(request.account_id, request.strategy_mode, supabase)
    raw_comments = [
        {"id": str(i), "text": text.strip()}
        for i, text in enumerate((c for c in request.comments if c.strip()), start=1)
    ]
    comments = await _run_generator(content_formats.triage_comments(
        raw_comments, strategy_mode=mode, language=request.language or "es",
        account_id=request.account_id or 0,
    ))
    return CommentsTriageResponse(source="manual", comments=comments)


@router.post("/prospect-comments", response_model=ProspectCommentsResponse)
async def post_prospect_comments(
    request: ProspectCommentsRequest,
    current_user: User = Depends(get_current_user),
    supabase: Client = Depends(get_user_supabase_client),
) -> ProspectCommentsResponse:
    """Comentarios de prospección (9 tipos) para publicaciones de otras cuentas del sector."""
    mode = await _optional_account_mode(request.account_id, request.strategy_mode, supabase)
    suggestions = await _run_generator(content_formats.generate_prospect_comments(
        request.target_post_text, strategy_mode=mode, language=request.language or "es",
        account_id=request.account_id or 0,
    ))
    return ProspectCommentsResponse(suggestions=suggestions)


@router.post("/dm-funnel", response_model=DmFunnelResponse)
async def post_dm_funnel(
    request: DmFunnelRequest,
    current_user: User = Depends(get_current_user),
    supabase: Client = Depends(get_user_supabase_client),
) -> DmFunnelResponse:
    """DM de entrega del recurso por palabra clave + 2 seguimientos."""
    if request.account_id:
        _verify_account_access(request.account_id, supabase)
    return await _run_generator(content_formats.generate_dm_funnel(
        request.keyword, request.resource_description, language=request.language or "es",
        account_id=request.account_id or 0,
    ))


# Helper functions
def get_project1_folder_id(user_id: str) -> Optional[str]:
    """Obtiene folder ID de PROJECT 1 desde configuración del usuario."""
    # TODO: Implementar obtención desde DB o env
    import os
    return os.getenv('GOOGLE_DRIVE_PROJECT1_FOLDER_ID')


def build_caption_prompt(metadata: dict, style: str, language: str = 'es') -> str:
    """
    Construye prompt para generación de caption basado en metadata.

    Args:
        metadata: Metadata del export
        style: Estilo del caption (informative, engaging, viral, etc)
        language: Idioma del caption ('es' o 'en')

    Returns:
        Prompt para el generador de captions
    """
    export_type = metadata.get('export_type')

    # Texto base según idioma
    if language == 'en':
        base_prompt = f"Generate an Instagram caption for {export_type}.\n\n"
    else:
        base_prompt = f"Genera un caption de Instagram para {export_type}.\n\n"

    # Agregar contexto según tipo
    if export_type == 'player':
        player = metadata.get('player', {})
        stats = metadata.get('stats', {})
        context = metadata.get('context', 'season')

        base_prompt += f"Jugador: {player.get('name')}\n"
        base_prompt += f"Equipo: {metadata.get('team', {}).get('name')}\n"
        base_prompt += f"Contexto: {context}\n"
        base_prompt += f"Estadísticas: {stats}\n"

    elif export_type == 'team':
        team = metadata.get('team', {})
        stats = metadata.get('stats', {})

        base_prompt += f"Equipo: {team.get('name')}\n"
        base_prompt += f"Competición: {metadata.get('competition', {}).get('name')}\n"
        base_prompt += f"Estadísticas: {stats}\n"

    elif export_type == 'match':
        match = metadata.get('match', {})
        home = match.get('home_team', {})
        away = match.get('away_team', {})

        base_prompt += f"Partido: {home.get('name')} vs {away.get('name')}\n"

        if match.get('status') == 'finished':
            base_prompt += (
                f"Resultado: {home.get('score')} - {away.get('score')}\n"
            )

    elif export_type == 'competition':
        comp = metadata.get('competition', {})
        base_prompt += f"Competición: {comp.get('name')}\n"
        base_prompt += f"Jornada: {comp.get('matchday')}\n"

    # Agregar instrucciones de estilo e idioma
    if language == 'en':
        style_instructions = {
            'informative': 'Use an informative and professional tone.',
            'engaging': 'Use an engaging and exciting tone.',
            'viral': 'Use a viral and catchy tone with emojis.',
            'analytical': 'Use an analytical and detailed tone.',
        }
        base_prompt += f"\nStyle: {style_instructions.get(style, style)}\n"
        base_prompt += "Include relevant hashtags.\n"
        base_prompt += "Maximum 2200 characters.\n"
        base_prompt += "\n**IMPORTANT: Write the ENTIRE caption in ENGLISH.**\n"
    else:
        style_instructions = {
            'informative': 'Usa un tono informativo y profesional.',
            'engaging': 'Usa un tono engaging y emocionante.',
            'viral': 'Usa un tono viral y llamativo con emojis.',
            'analytical': 'Usa un tono analítico y detallado.',
        }
        base_prompt += f"\nEstilo: {style_instructions.get(style, style)}\n"
        base_prompt += "Incluye hashtags relevantes.\n"
        base_prompt += "Máximo 2200 caracteres.\n"
        base_prompt += "\n**IMPORTANTE: Escribe TODO el caption en ESPAÑOL.**\n"

    return base_prompt


def generate_fallback_caption(metadata: dict) -> str:
    """Genera caption básico si falla IA."""
    export_type = metadata.get('export_type')

    if export_type == 'player':
        player = metadata.get('player', {}).get('name', 'Jugador')
        return f"📊 Estadísticas de {player} #Football #Stats"

    elif export_type == 'team':
        team = metadata.get('team', {}).get('name', 'Equipo')
        return f"📈 Rendimiento de {team} #TeamStats #Football"

    elif export_type == 'match':
        match = metadata.get('match', {})
        home = match.get('home_team', {}).get('name', 'Local')
        away = match.get('away_team', {}).get('name', 'Visitante')
        return f"⚽ {home} vs {away} #MatchDay #Football"

    elif export_type == 'competition':
        comp = metadata.get('competition', {}).get('name', 'Liga')
        return f"🏆 Tabla de {comp} #Standings #Football"

    return "⚽ Contenido de fútbol #Football #Stats"


def build_generic_caption_prompt(topic: Optional[str], style: str, language: str = 'es') -> str:
    """Construye prompt para generación de caption sobre un tema libre."""
    if language == 'en':
        prompt = f"Generate an Instagram caption about: {topic}\n\n"
        style_instructions = {
            'informative': 'Use an informative and professional tone.',
            'engaging': 'Use an engaging and exciting tone.',
            'viral': 'Use a viral and catchy tone with emojis.',
            'analytical': 'Use an analytical and detailed tone.',
        }
        prompt += f"Style: {style_instructions.get(style, style)}\n"
        prompt += "Include relevant hashtags.\nMaximum 2200 characters.\n"
        prompt += "\n**IMPORTANT: Write the ENTIRE caption in ENGLISH.**\n"
    else:
        prompt = f"Genera un caption de Instagram sobre el tema: {topic}\n\n"
        style_instructions = {
            'informative': 'Usa un tono informativo y profesional.',
            'engaging': 'Usa un tono engaging y emocionante.',
            'viral': 'Usa un tono viral y llamativo con emojis.',
            'analytical': 'Usa un tono analítico y detallado.',
        }
        prompt += f"Estilo: {style_instructions.get(style, style)}\n"
        prompt += "Incluye hashtags relevantes.\nMáximo 2200 caracteres.\n"
        prompt += "\n**IMPORTANTE: Escribe TODO el caption en ESPAÑOL.**\n"
    return prompt


def get_mock_metadata(export_id: str) -> Optional[dict]:
    """
    Devuelve metadata mock para exports de prueba.

    Args:
        export_id: ID del export mock (ej: "export_1", "export_player_messi_2025_01")

    Returns:
        Diccionario con metadata o None si no existe
    """
    mock_data = {
        "export_1": {
            "export_type": "player",
            "player": {
                "name": "Lionel Messi",
                "position": "Forward",
                "team": "Inter Miami"
            },
            "stats": {
                "goals": 12,
                "assists": 9,
                "shots": 54,
                "pass_accuracy": "89%",
                "minutes_played": 1350
            },
            "context": "season"
        },
        "export_2": {
            "export_type": "match",
            "match": {
                "home_team": {"name": "Barcelona"},
                "away_team": {"name": "Real Madrid"},
                "score": "3-1",
                "status": "finished",
                "date": "2025-01-14"
            },
            "stats": {
                "possession": {"home": 58, "away": 42},
                "shots": {"home": 15, "away": 8},
                "corners": {"home": 7, "away": 3}
            }
        },
        "export_3": {
            "export_type": "team",
            "team": {
                "name": "Manchester City"
            },
            "stats": {
                "wins": 20,
                "draws": 3,
                "losses": 2,
                "goals_scored": 65,
                "goals_conceded": 18,
                "points": 63
            }
        },
        "export_player_messi_2025_01": {
            "export_type": "player",
            "player": {
                "name": "Lionel Messi",
                "position": "Forward",
                "team": "Inter Miami"
            },
            "stats": {
                "goals": 12,
                "assists": 9,
                "shots": 54,
                "pass_accuracy": "89%",
                "minutes_played": 1350
            }
        },
        "export_match_barcelona_real_2025_01": {
            "export_type": "match",
            "match": {
                "home_team": {"name": "Barcelona"},
                "away_team": {"name": "Real Madrid"},
                "score": "3-1",
                "status": "finished"
            },
            "stats": {
                "possession": {"home": 58, "away": 42},
                "shots": {"home": 15, "away": 8}
            }
        },
        "export_team_man_city_2025_01": {
            "export_type": "team",
            "team": {
                "name": "Manchester City"
            },
            "stats": {
                "wins": 20,
                "draws": 3,
                "losses": 2,
                "goals_scored": 65,
                "goals_conceded": 18
            }
        },
        "export_player_haaland_2025_01": {
            "export_type": "player",
            "player": {
                "name": "Erling Haaland",
                "position": "Striker",
                "team": "Manchester City"
            },
            "stats": {
                "goals": 25,
                "assists": 5,
                "shots": 78,
                "shot_accuracy": "67%",
                "minutes_played": 1800
            }
        }
    }

    return mock_data.get(export_id)


async def publish_to_instagram(post_id: int, user_id: str):
    """
    Publica post en Instagram (background task).

    Args:
        post_id: ID del post a publicar
        user_id: ID del usuario
    """
    try:
        # TODO: Implementar publicación real usando Instagram API
        logger.info(f"📤 Publicando post {post_id} en Instagram...")

        supabase = get_supabase_client()

        # Actualizar estado
        supabase.table('posts').update({
            'status': 'published',
            'publication_date': datetime.now().isoformat()
        }).eq('id', post_id).execute()

        logger.info(f"✅ Post {post_id} publicado exitosamente")

    except Exception as e:
        logger.error(f"❌ Error publicando post {post_id}: {str(e)}")

        # Marcar como failed
        supabase = get_supabase_client()
        supabase.table('posts').update({
            'status': 'failed'
        }).eq('id', post_id).execute()
