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
        description="Estilo del caption"
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

        # 1. Obtener export de PROJECT 1 desde Google Drive
        drive = get_drive_connector()
        project1_folder_id = get_project1_folder_id(user_id)

        if not project1_folder_id:
            raise HTTPException(
                status_code=400,
                detail="Google Drive no configurado para PROJECT 1"
            )

        # Buscar export por ID
        exports = drive.list_project1_exports(project1_folder_id)
        export_data = next(
            (e for e in exports if e['folder_name'] == request.export_id),
            None
        )

        if not export_data:
            raise HTTPException(
                status_code=404,
                detail=f"Export {request.export_id} no encontrado"
            )

        metadata = export_data.get('metadata')
        if not metadata:
            raise HTTPException(
                status_code=400,
                detail="Export sin metadata.json válido"
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

        # 3. Descargar imágenes necesarias
        # Template base
        if not template.get('image_url'):
            raise HTTPException(
                status_code=400,
                detail="Template sin imagen base"
            )

        # TODO: Descargar template_image desde Supabase Storage
        # Por ahora simulamos con None
        template_image_bytes = None

        # Gráfico de PROJECT 1
        main_graphic_name = metadata.get('files', {}).get('main_graphic')
        if not main_graphic_name:
            raise HTTPException(
                status_code=400,
                detail="Export sin gráfico principal (main_graphic)"
            )

        # Buscar archivo en Google Drive
        graphic_file = next(
            (
                f for f in drive.list_files(export_data['folder_id'])
                if f['name'] == main_graphic_name
            ),
            None
        )

        if not graphic_file:
            raise HTTPException(
                status_code=404,
                detail=f"Gráfico {main_graphic_name} no encontrado"
            )

        # Descargar gráfico
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name

        drive.download_file(graphic_file['id'], tmp_path)

        with open(tmp_path, 'rb') as f:
            graphic_image_bytes = f.read()

        os.unlink(tmp_path)

        logger.info(f"✅ Gráfico descargado: {main_graphic_name}")

        # 4. Componer imagen final
        # Por ahora solo usamos el gráfico si no hay template
        if template_image_bytes:
            composer = get_image_composer()
            final_image_bytes = composer.compose_post(
                template_image=template_image_bytes,
                graphic_image=graphic_image_bytes,
                template_config=template.get('template_config', {}),
                format_type=request.format_type
            )
        else:
            # Fallback: usar gráfico directo
            final_image_bytes = graphic_image_bytes

        if not final_image_bytes:
            raise HTTPException(
                status_code=500,
                detail="Error componiendo imagen final"
            )

        logger.info("✅ Imagen final compuesta")

        # 5. Generar caption con IA
        caption_prompt = build_caption_prompt(metadata, request.caption_style)
        caption = generate_caption(caption_prompt)

        if not caption:
            caption = generate_fallback_caption(metadata)

        logger.info("✅ Caption generado")

        # 6. Subir imagen a Supabase Storage
        final_image_path = (
            f"generated/{user_id}/"
            f"{request.export_id}_{request.format_type}.png"
        )

        supabase.storage.from_('posts').upload(
            final_image_path,
            final_image_bytes,
            {'content-type': 'image/png'}
        )

        final_image_url = supabase.storage.from_('posts').get_public_url(
            final_image_path
        )

        # 7. Crear post en DB
        post_data = {
            'user_id': user_id,
            'instagram_account_id': request.instagram_account_id,
            'caption': caption,
            'image_url': final_image_url,
            'status': 'draft',
            'metadata': {
                'export_id': request.export_id,
                'export_type': metadata.get('export_type'),
                'template_id': template['id'],
                'template_name': template['name'],
                'format_type': request.format_type,
                'generation_source': 'project1_auto'
            }
        }

        if request.scheduled_time:
            post_data['scheduled_for'] = request.scheduled_time.isoformat()
            post_data['status'] = 'scheduled'

        post_result = supabase.table('posts').insert(post_data).execute()

        if not post_result.data:
            raise HTTPException(
                status_code=500,
                detail="Error guardando post"
            )

        post = post_result.data[0]
        logger.info(f"✅ Post creado: {post['id']}")

        # 8. Incrementar use_count del template
        supabase.table('templates').update({
            'use_count': template['use_count'] + 1
        }).eq('id', template['id']).execute()

        # 9. Registrar en content_generation_history
        supabase.table('content_generation_history').insert({
            'user_id': user_id,
            'post_id': post['id'],
            'export_id': request.export_id,
            'template_id': template['id'],
            'generation_metadata': {
                'export_type': metadata.get('export_type'),
                'format_type': request.format_type,
                'caption_style': request.caption_style
            },
            'status': 'completed'
        }).execute()

        # 10. Auto-publicar si se solicitó
        if request.auto_publish and not request.scheduled_time:
            background_tasks.add_task(
                publish_to_instagram,
                post['id'],
                user_id
            )

        return ContentGenerationResponse(
            success=True,
            message='Contenido generado exitosamente',
            post_id=post['id'],
            preview_url=final_image_url,
            caption=caption,
            template_used={
                'id': template['id'],
                'name': template['name']
            },
            metadata={
                'export_id': request.export_id,
                'export_type': metadata.get('export_type')
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


def build_caption_prompt(metadata: dict, style: str) -> str:
    """
    Construye prompt para generación de caption basado en metadata.

    Args:
        metadata: Metadata del export
        style: Estilo del caption (informative, engaging, viral, etc)

    Returns:
        Prompt para el generador de captions
    """
    export_type = metadata.get('export_type')

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

    # Agregar instrucciones de estilo
    style_instructions = {
        'informative': 'Usa un tono informativo y profesional.',
        'engaging': 'Usa un tono engaging y emocionante.',
        'viral': 'Usa un tono viral y llamativo con emojis.',
        'analytical': 'Usa un tono analítico y detallado.',
    }

    base_prompt += f"\nEstilo: {style_instructions.get(style, style)}\n"
    base_prompt += "Incluye hashtags relevantes.\n"
    base_prompt += "Máximo 2200 caracteres.\n"

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
