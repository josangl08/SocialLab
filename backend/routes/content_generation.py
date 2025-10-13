"""
Content Generation API Routes
Endpoint principal para generación automática de contenido.
Integra: PROJECT 1 exports + Template Selector + Image Composer + Caption Generator.
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import logging

from auth.jwt_handler import get_current_user
from database.supabase_client import get_supabase_client
from services.google_drive_connector import get_drive_connector
from services.template_selector import get_template_selector
from services.image_composer import get_image_composer
from services.caption_generator import generate_caption

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/content", tags=["Content Generation"])


# Schemas
class ContentGenerationRequest(BaseModel):
    """Schema para solicitud de generación."""
    export_id: str = Field(..., description="ID del export de PROJECT 1")
    instagram_account_id: int = Field(
        ...,
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
    current_user: dict = Depends(get_current_user)
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
        supabase = get_supabase_client()
        user_id = current_user['id']

        logger.info(f"🎬 Iniciando generación para export: {request.export_id}")

        # Intentar primero obtener de Google Drive
        metadata = None
        is_mock_export = False
        export_data = None

        try:
            # 1. Obtener export de PROJECT 1 desde Google Drive
            drive = get_drive_connector()
            project1_folder_id = get_project1_folder_id(user_id)

            if project1_folder_id and drive.service:
                logger.info("📂 Buscando export en Google Drive...")
                # Buscar export por ID
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

        # Si no se encontró en Drive, intentar con datos mock
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

        logger.info(
            f"✅ Metadata cargado: {metadata.get('export_type')}"
        )

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
        final_image_bytes = None
        final_image_url = None

        if not is_mock_export:
            # Descargar imágenes desde Google Drive
            main_graphic_name = metadata.get('files', {}).get('main_graphic')
            logger.info(f"🔍 Buscando gráfico: {main_graphic_name}")

            if not main_graphic_name:
                raise HTTPException(
                    status_code=400,
                    detail="Export sin gráfico principal (main_graphic) en metadata.json"
                )

            # Buscar archivo en Google Drive
            logger.info(f"📁 Listando archivos en folder {export_data['folder_id']}...")
            files_in_folder = drive.list_files(export_data['folder_id'])
            logger.info(f"📁 Archivos encontrados:")
            for f in files_in_folder:
                logger.info(f"   - {f['name']}")

            graphic_file = next(
                (
                    f for f in files_in_folder
                    if f['name'] == main_graphic_name
                ),
                None
            )

            if not graphic_file:
                logger.error(f"❌ Gráfico '{main_graphic_name}' NO encontrado entre los archivos")
                raise HTTPException(
                    status_code=404,
                    detail=f"Gráfico '{main_graphic_name}' no encontrado en la carpeta. Archivos disponibles: {[f['name'] for f in files_in_folder]}"
                )

            logger.info(f"✅ Gráfico '{main_graphic_name}' encontrado con ID: {graphic_file['id']}")

            # Descargar gráfico
            import tempfile
            import os as os_temp

            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp_path = tmp.name

            drive.download_file(graphic_file['id'], tmp_path)

            with open(tmp_path, 'rb') as f:
                graphic_image_bytes = f.read()

            os_temp.unlink(tmp_path)

            logger.info(f"✅ Gráfico descargado: {main_graphic_name}")

            # Descargar template desde Supabase Storage
            template_path = template.get('file_path') or template.get('image_url')

            if not template_path:
                raise HTTPException(
                    status_code=400,
                    detail="Template sin imagen configurada"
                )

            logger.info(f"🔍 Template path original: {template_path}")

            # Si es URL completa, extraer solo la ruta relativa
            if template_path.startswith('http'):
                # Extraer la parte después de '/templates/'
                if '/templates/' in template_path:
                    template_path = template_path.split('/templates/')[-1]
                    logger.info(f"✅ Ruta relativa extraída: {template_path}")
                else:
                    raise HTTPException(
                        status_code=400,
                        detail=f"URL de template inválida: {template_path}"
                    )

            # Descargar template desde Supabase Storage
            logger.info(f"⬇️ Descargando template desde Supabase Storage...")
            template_response = supabase.storage.from_('templates').download(
                template_path
            )
            template_image_bytes = template_response

            logger.info(f"✅ Template descargado: {template.get('name')}")

            # Componer imagen final usando ImageComposer
            image_composer = get_image_composer()

            # Obtener configuración del template
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

            # NO guardar todavía - solo convertir a base64 para preview
            import base64
            final_image_base64 = base64.b64encode(final_image_bytes).decode('utf-8')
            final_image_url = f"data:image/png;base64,{final_image_base64}"

            logger.info("✅ Imagen convertida a base64 para preview (no guardada aún)")
        else:
            # Para exports mock, usar la imagen del template
            logger.info("🎭 Export mock: usando imagen del template")

            # Obtener URL pública del template desde Supabase Storage
            # El template puede tener 'file_path' o 'image_url'
            template_path = template.get('file_path') or template.get('image_url')

            if template_path:
                # Si el path no incluye el bucket, asumimos que está en 'templates'
                if not template_path.startswith('http'):
                    final_image_url = supabase.storage.from_('templates').get_public_url(
                        template_path
                    )
                else:
                    final_image_url = template_path

                logger.info(f"✅ Usando imagen del template: {template.get('name')}")
            else:
                logger.warning("⚠️ Template sin ruta de archivo, usando None")
                final_image_url = None

        # 4. Generar caption con IA
        language = request.language if request.language else 'es'
        caption_style = request.caption_style if request.caption_style else 'informative'

        logger.info(f"🎨 Generando caption - Estilo: {caption_style}, Idioma: {language}")

        caption_prompt = build_caption_prompt(metadata, caption_style, language)
        caption = generate_caption(caption_prompt)

        if not caption:
            caption = generate_fallback_caption(metadata)

        logger.info("✅ Caption generado")

        # 5. NO crear post todavía - solo devolver datos para preview
        logger.info("📦 Preparando respuesta con preview (sin guardar en DB)")

        # Devolver preview SIN guardar en DB (el frontend guardará después)
        return ContentGenerationResponse(
            success=True,
            message='Preview generado - usa "Guardar" para almacenar' + (' (modo prueba)' if is_mock_export else ''),
            post_id=None,  # No hay post_id porque no se guardó todavía
            preview_url=final_image_url,  # Base64 data URL para preview
            caption=caption,
            template_used={
                'id': template.get('id') if template else 0,
                'name': template.get('name') if template else 'mock_template'
            } if template else None,
            metadata={
                'export_id': request.export_id,
                'export_type': metadata.get('export_type'),
                'instagram_account_id': request.instagram_account_id,
                'format_type': request.format_type,
                'caption_style': request.caption_style,
                'template_id': template.get('id') if template else None,
                'is_mock': is_mock_export,
                'user_id': user_id  # Para cuando se guarde después
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error generando contenido: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/queue/status", response_model=QueueStatusResponse)
async def get_queue_status(
    current_user: dict = Depends(get_current_user)
):
    """Obtiene estado de la cola de generación."""
    try:
        supabase = get_supabase_client()
        user_id = current_user['id']

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
    current_user: dict = Depends(get_current_user)
):
    """Obtiene historial de generaciones."""
    try:
        supabase = get_supabase_client()
        user_id = current_user['id']

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
            'published_at': datetime.now().isoformat()
        }).eq('id', post_id).execute()

        logger.info(f"✅ Post {post_id} publicado exitosamente")

    except Exception as e:
        logger.error(f"❌ Error publicando post {post_id}: {str(e)}")

        # Marcar como failed
        supabase = get_supabase_client()
        supabase.table('posts').update({
            'status': 'failed'
        }).eq('id', post_id).execute()
