"""
Test del Flujo Completo End-to-End.

Simula el proceso completo de generación de contenido:
1. Metadata de PROJECT 1 (simulado)
2. Selección de template apropiado
3. Descarga de template y generación de gráfico
4. Composición de imagen final
5. Generación de caption con IA
6. Guardado en Supabase (posts + storage)
"""

import logging
import os
import requests
from datetime import datetime, timezone
from PIL import Image, ImageDraw, ImageFont
import io

from database.supabase_client import get_supabase_admin_client
from services.template_selector import get_template_selector
from services.image_composer import get_image_composer
from services.caption_generator import get_caption_generator

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_mock_player_graphic(metadata: dict) -> bytes:
    """Crea gráfico de jugador basado en metadata."""
    player = metadata.get('player', {})
    stats = metadata.get('stats', {})

    img = Image.new('RGBA', (800, 600), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)

    # Fondo
    draw.rectangle([0, 0, 800, 600], fill=(30, 30, 40, 230))

    try:
        title_font = ImageFont.truetype(
            "/System/Library/Fonts/Helvetica.ttc", 60
        )
        stats_font = ImageFont.truetype(
            "/System/Library/Fonts/Helvetica.ttc", 40
        )
    except:
        title_font = ImageFont.load_default()
        stats_font = ImageFont.load_default()

    # Nombre del jugador
    draw.text(
        (50, 50),
        player.get('name', 'Player').upper(),
        fill=(255, 255, 255),
        font=title_font
    )
    draw.text(
        (50, 120),
        player.get('position', 'Position'),
        fill=(150, 150, 150),
        font=stats_font
    )

    # Estadísticas
    y_offset = 220
    for key, value in stats.items():
        label = key.replace('_', ' ').title()
        draw.text(
            (100, y_offset),
            label,
            fill=(200, 200, 200),
            font=stats_font
        )
        draw.text(
            (500, y_offset),
            str(value),
            fill=(76, 175, 80),
            font=title_font
        )
        y_offset += 80

    output = io.BytesIO()
    img.save(output, format='PNG')
    output.seek(0)

    return output.getvalue()


def create_mock_match_graphic(metadata: dict) -> bytes:
    """Crea gráfico de partido basado en metadata."""
    match = metadata.get('match', {})
    home = match.get('home_team', {})
    away = match.get('away_team', {})

    img = Image.new('RGBA', (1000, 500), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)

    # Fondo verde victoria
    draw.rectangle([0, 0, 1000, 500], fill=(15, 76, 45, 250))

    try:
        huge_font = ImageFont.truetype(
            "/System/Library/Fonts/Helvetica.ttc", 120
        )
        title_font = ImageFont.truetype(
            "/System/Library/Fonts/Helvetica.ttc", 60
        )
        small_font = ImageFont.truetype(
            "/System/Library/Fonts/Helvetica.ttc", 40
        )
    except:
        huge_font = ImageFont.load_default()
        title_font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    # Equipos
    draw.text(
        (100, 50),
        home.get('name', 'HOME').upper(),
        fill=(255, 255, 255),
        font=title_font
    )
    draw.text(
        (600, 50),
        away.get('name', 'AWAY').upper(),
        fill=(200, 200, 200),
        font=title_font
    )

    # Marcador
    score = match.get('score', '0-0').split('-')
    draw.text((200, 180), score[0], fill=(255, 255, 255), font=huge_font)
    draw.text((450, 200), "-", fill=(255, 255, 255), font=title_font)
    draw.text((650, 180), score[1], fill=(200, 200, 200), font=huge_font)

    # Footer
    status_text = match.get('status', 'FINISHED').upper()
    draw.text((350, 380), status_text, fill=(76, 175, 80), font=small_font)

    output = io.BytesIO()
    img.save(output, format='PNG')
    output.seek(0)

    return output.getvalue()


def generate_content_flow(metadata: dict, user_id: str) -> dict:
    """
    Ejecuta el flujo completo de generación de contenido.

    Args:
        metadata: Metadata simulando export de PROJECT 1
        user_id: UUID del usuario

    Returns:
        Diccionario con resultado del flujo
    """
    supabase = get_supabase_admin_client()
    result = {
        'success': False,
        'steps': {},
        'post_id': None,
        'errors': []
    }

    export_type = metadata.get('export_type')
    logger.info(f"\n{'='*60}")
    logger.info(f"INICIANDO FLUJO: {export_type.upper()}")
    logger.info(f"{'='*60}\n")

    try:
        # PASO 1: Seleccionar template
        logger.info("📋 PASO 1: Selección de Template")
        selector = get_template_selector(supabase)
        template = selector.select_template(metadata, user_id)

        if not template:
            result['errors'].append("No se encontró template apropiado")
            return result

        logger.info(f"   ✅ Template seleccionado: {template['name']}\n")
        result['steps']['template_selection'] = {
            'template_id': template['id'],
            'template_name': template['name']
        }

        # PASO 2: Generar gráfico (simular PROJECT 1)
        logger.info("🎨 PASO 2: Generación de Gráfico")

        if export_type == 'player':
            graphic_bytes = create_mock_player_graphic(metadata)
        elif export_type == 'match':
            graphic_bytes = create_mock_match_graphic(metadata)
        else:
            # Gráfico genérico
            img = Image.new('RGB', (800, 600), (100, 100, 120))
            output = io.BytesIO()
            img.save(output, format='PNG')
            graphic_bytes = output.getvalue()

        logger.info(f"   ✅ Gráfico generado: {len(graphic_bytes)} bytes\n")
        result['steps']['graphic_generation'] = {
            'size_bytes': len(graphic_bytes)
        }

        # PASO 3: Descargar template y componer imagen
        logger.info("🖼️  PASO 3: Composición de Imagen")

        # Descargar template de Supabase
        response = requests.get(template['image_url'])
        template_bytes = response.content

        # Componer imagen
        composer = get_image_composer()
        composed_image = composer.compose_post(
            template_image=template_bytes,
            graphic_image=graphic_bytes,
            template_config=template.get('template_config', {}),
            format_type='square'
        )

        if not composed_image:
            result['errors'].append("Error componiendo imagen")
            return result

        logger.info(
            f"   ✅ Imagen compuesta: {len(composed_image)} bytes\n"
        )
        result['steps']['image_composition'] = {
            'size_bytes': len(composed_image)
        }

        # PASO 4: Generar caption con IA
        logger.info("🤖 PASO 4: Generación de Caption")

        caption_generator = get_caption_generator()
        caption = caption_generator.generate_caption(
            metadata=metadata,
            tone='energetic',
            language='es',
            max_hashtags=7
        )

        if not caption:
            logger.warning("   ⚠️  Error con IA, usando fallback")
            caption = caption_generator.generate_caption_fallback(metadata)

        logger.info(f"   ✅ Caption generado ({len(caption)} chars)")
        logger.info(f"   Caption: {caption[:100]}...\n")
        result['steps']['caption_generation'] = {
            'caption': caption,
            'length': len(caption)
        }

        # PASO 5: Subir imagen a Supabase Storage
        logger.info("☁️  PASO 5: Subida a Supabase Storage")

        # Generar nombre único
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        filename = f"{user_id}/composed_{export_type}_{timestamp}.png"

        # Subir a bucket 'posts'
        supabase.storage.from_('posts').upload(
            filename,
            composed_image,
            {'content-type': 'image/png', 'upsert': 'true'}
        )

        # Obtener URL pública
        image_url = supabase.storage.from_('posts').get_public_url(filename)

        logger.info(f"   ✅ Imagen subida: {filename}\n")
        result['steps']['storage_upload'] = {
            'filename': filename,
            'url': image_url
        }

        # PASO 6: Guardar post en base de datos
        logger.info("💾 PASO 6: Guardado en Base de Datos")

        post_data = {
            'user_id': user_id,
            'content': caption,  # La tabla usa 'content' no 'caption'
            'media_url': image_url,
            'post_type': 'IMAGE',  # La tabla usa 'post_type' no 'media_type'
            'status': 'draft',
            'template_id': template['id'],
            'ai_caption_raw': caption,  # Guardar también en ai_caption_raw
            'ai_metadata': {
                'export_type': export_type,
                'metadata': metadata,
                'generated_at': datetime.now(timezone.utc).isoformat()
            },
            'is_ai_generated': True
        }

        post_result = supabase.table('posts').insert(post_data).execute()

        if not post_result.data:
            result['errors'].append("Error guardando post en DB")
            return result

        post_id = post_result.data[0]['id']
        logger.info(f"   ✅ Post guardado con ID: {post_id}\n")
        result['steps']['database_save'] = {
            'post_id': post_id
        }

        # Success!
        result['success'] = True
        result['post_id'] = post_id

        logger.info(f"{'='*60}")
        logger.info("✅ FLUJO COMPLETADO EXITOSAMENTE")
        logger.info(f"{'='*60}\n")

        return result

    except Exception as e:
        logger.error(f"❌ Error en flujo: {str(e)}")
        result['errors'].append(str(e))
        return result


def main():
    """Ejecutar tests del flujo completo."""
    print("\n" + "🚀 "*30)
    print("TEST FLUJO COMPLETO END-TO-END")
    print("🚀 "*30 + "\n")

    supabase = get_supabase_admin_client()

    # Obtener user_id
    result = supabase.table('posts').select('user_id').limit(1).execute()
    user_id = result.data[0]['user_id'] if result.data else None

    if not user_id:
        logger.error("No se encontró user_id")
        return

    # Test 1: Player Stats
    logger.info("="*60)
    logger.info("TEST 1: PLAYER STATS")
    logger.info("="*60)

    metadata_player = {
        'export_type': 'player',
        'player': {
            'name': 'Lionel Messi',
            'position': 'Forward',
            'team': 'Inter Miami'
        },
        'stats': {
            'goals': 12,
            'assists': 9,
            'shots': 54,
            'pass_accuracy': '89%'
        }
    }

    result1 = generate_content_flow(metadata_player, user_id)

    if result1['success']:
        logger.info(f"✅ Test 1 completado - Post ID: {result1['post_id']}\n")
    else:
        logger.error(f"❌ Test 1 falló: {result1['errors']}\n")

    # Test 2: Match Result
    logger.info("="*60)
    logger.info("TEST 2: MATCH RESULT")
    logger.info("="*60)

    metadata_match = {
        'export_type': 'match',
        'match': {
            'home_team': {'name': 'Barcelona', 'id': 'barcelona'},
            'away_team': {'name': 'Real Madrid', 'id': 'real_madrid'},
            'score': '3-1',
            'status': 'finished',
            'winner': 'home'
        }
    }

    result2 = generate_content_flow(metadata_match, user_id)

    if result2['success']:
        logger.info(f"✅ Test 2 completado - Post ID: {result2['post_id']}\n")
    else:
        logger.error(f"❌ Test 2 falló: {result2['errors']}\n")

    # Resumen
    print("\n" + "="*60)
    print("RESUMEN DE TESTS")
    print("="*60)
    print(f"\nTest 1 (Player Stats): {'✅ ÉXITO' if result1['success'] else '❌ FALLO'}")
    if result1['success']:
        print(f"  Post ID: {result1['post_id']}")
        print(f"  Caption: {result1['steps']['caption_generation']['caption'][:80]}...")

    print(f"\nTest 2 (Match Result): {'✅ ÉXITO' if result2['success'] else '❌ FALLO'}")
    if result2['success']:
        print(f"  Post ID: {result2['post_id']}")
        print(f"  Caption: {result2['steps']['caption_generation']['caption'][:80]}...")

    print("\n" + "="*60)
    print("VERIFICAR POSTS EN SUPABASE")
    print("="*60)
    print("\n1. Ve a: https://supabase.com/dashboard")
    print("2. Table Editor → posts")
    print("3. Busca los posts con is_ai_generated = true")
    print("4. Verifica las imágenes en Storage → posts bucket\n")


if __name__ == '__main__':
    main()
