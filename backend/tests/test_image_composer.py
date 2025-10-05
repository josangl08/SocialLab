"""
Test del Image Composer Service.

Este script:
1. Descarga templates reales de Supabase
2. Genera gráficos de prueba simulando PROJECT 1
3. Compone imágenes finales con diferentes configuraciones
4. Guarda las imágenes generadas para inspección visual
"""

import logging
import os
import requests
from PIL import Image, ImageDraw, ImageFont
import io
from database.supabase_client import get_supabase_admin_client
from services.image_composer import get_image_composer

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_mock_graphic_player_stats():
    """Crea gráfico de prueba simulando stats de jugador de PROJECT 1."""
    # Canvas blanco 800x600
    img = Image.new('RGBA', (800, 600), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)

    # Fondo con gradiente (simulado con rectángulo)
    draw.rectangle([0, 0, 800, 600], fill=(30, 30, 40, 230))

    # Título
    try:
        title_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 60)
        stats_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 40)
    except:
        title_font = ImageFont.load_default()
        stats_font = ImageFont.load_default()

    # Dibujar nombre del jugador
    draw.text((50, 50), "CRISTIANO RONALDO", fill=(255, 255, 255), font=title_font)
    draw.text((50, 120), "Forward", fill=(150, 150, 150), font=stats_font)

    # Estadísticas
    stats = [
        ("Goals", "15"),
        ("Assists", "8"),
        ("Shots", "67"),
        ("Pass Accuracy", "87%")
    ]

    y_offset = 220
    for label, value in stats:
        draw.text((100, y_offset), label, fill=(200, 200, 200), font=stats_font)
        draw.text((500, y_offset), value, fill=(76, 175, 80), font=title_font)
        y_offset += 80

    # Convertir a bytes
    output = io.BytesIO()
    img.save(output, format='PNG')
    output.seek(0)

    return output.getvalue()


def create_mock_graphic_team_performance():
    """Crea gráfico de prueba simulando performance de equipo."""
    img = Image.new('RGBA', (900, 700), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)

    # Fondo
    draw.rectangle([0, 0, 900, 700], fill=(20, 20, 30, 240))

    try:
        title_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 70)
        stats_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 50)
    except:
        title_font = ImageFont.load_default()
        stats_font = ImageFont.load_default()

    # Título
    draw.text((50, 50), "REAL MADRID", fill=(255, 255, 255), font=title_font)
    draw.text((50, 140), "Season Performance", fill=(180, 180, 180), font=stats_font)

    # Stats en barras visuales
    stats = [
        ("Wins", 15, (76, 175, 80)),
        ("Draws", 5, (255, 193, 7)),
        ("Losses", 2, (244, 67, 54))
    ]

    y_offset = 280
    for label, value, color in stats:
        draw.text((80, y_offset), label, fill=(200, 200, 200), font=stats_font)
        # Barra
        bar_width = value * 30
        draw.rectangle([350, y_offset + 10, 350 + bar_width, y_offset + 50], fill=color)
        draw.text((370 + bar_width, y_offset), str(value), fill=color, font=stats_font)
        y_offset += 100

    output = io.BytesIO()
    img.save(output, format='PNG')
    output.seek(0)

    return output.getvalue()


def create_mock_graphic_match_result():
    """Crea gráfico de prueba simulando resultado de partido."""
    img = Image.new('RGBA', (1000, 500), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)

    # Fondo
    draw.rectangle([0, 0, 1000, 500], fill=(15, 76, 45, 250))

    try:
        huge_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 120)
        title_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 60)
        small_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 40)
    except:
        huge_font = ImageFont.load_default()
        title_font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    # Equipos
    draw.text((100, 50), "BARCELONA", fill=(255, 255, 255), font=title_font)
    draw.text((600, 50), "VALENCIA", fill=(200, 200, 200), font=title_font)

    # Marcador
    draw.text((200, 180), "3", fill=(255, 255, 255), font=huge_font)
    draw.text((450, 200), "-", fill=(255, 255, 255), font=title_font)
    draw.text((650, 180), "1", fill=(200, 200, 200), font=huge_font)

    # Footer
    draw.text((350, 380), "FULL TIME", fill=(76, 175, 80), font=small_font)

    output = io.BytesIO()
    img.save(output, format='PNG')
    output.seek(0)

    return output.getvalue()


def test_image_composition():
    """Prueba composición de imágenes con templates reales."""
    supabase = get_supabase_admin_client()
    composer = get_image_composer()

    logger.info("\n" + "="*60)
    logger.info("TEST IMAGE COMPOSER")
    logger.info("="*60 + "\n")

    # Crear directorio para outputs
    output_dir = "/tmp/sociallab_composed"
    os.makedirs(output_dir, exist_ok=True)

    # Obtener templates de Supabase
    logger.info("📥 Obteniendo templates de Supabase...\n")
    templates = supabase.table('templates').select('*').execute()

    if not templates.data:
        logger.error("❌ No hay templates en la base de datos")
        return

    # Test 1: Player stats con template moderno
    logger.info("🎨 Test 1: Player Stats + Modern Blue Template")
    player_template = next(
        (t for t in templates.data if 'modern_blue' in t['name']),
        templates.data[0]
    )

    # Descargar template
    response = requests.get(player_template['image_url'])
    template_bytes = response.content

    # Generar gráfico
    graphic_bytes = create_mock_graphic_player_stats()

    # Componer
    result = composer.compose_post(
        template_image=template_bytes,
        graphic_image=graphic_bytes,
        template_config={
            'graphic_position': 'center',
            'graphic_scale': 0.75,
            'margin': 80
        },
        format_type='square'
    )

    if result:
        output_path = f"{output_dir}/player_stats_composed.png"
        with open(output_path, 'wb') as f:
            f.write(result)
        logger.info(f"✅ Guardado: {output_path}\n")

    # Test 2: Team performance
    logger.info("🎨 Test 2: Team Performance + Gradient Template")
    team_template = next(
        (t for t in templates.data if 'team_performance' in t['name']),
        templates.data[0]
    )

    response = requests.get(team_template['image_url'])
    template_bytes = response.content
    graphic_bytes = create_mock_graphic_team_performance()

    result = composer.compose_post(
        template_image=template_bytes,
        graphic_image=graphic_bytes,
        template_config={
            'graphic_position': 'center',
            'graphic_scale': 0.7,
            'margin': 100
        },
        format_type='square'
    )

    if result:
        output_path = f"{output_dir}/team_performance_composed.png"
        with open(output_path, 'wb') as f:
            f.write(result)
        logger.info(f"✅ Guardado: {output_path}\n")

    # Test 3: Match result
    logger.info("🎨 Test 3: Match Result + Victory Green Template")
    match_template = next(
        (t for t in templates.data if 'match_result' in t['name']),
        templates.data[0]
    )

    response = requests.get(match_template['image_url'])
    template_bytes = response.content
    graphic_bytes = create_mock_graphic_match_result()

    result = composer.compose_post(
        template_image=template_bytes,
        graphic_image=graphic_bytes,
        template_config={
            'graphic_position': 'center',
            'graphic_scale': 0.8,
            'margin': 60
        },
        format_type='square'
    )

    if result:
        output_path = f"{output_dir}/match_result_composed.png"
        with open(output_path, 'wb') as f:
            f.write(result)
        logger.info(f"✅ Guardado: {output_path}\n")

    # Test 4: Story format (9:16)
    logger.info("🎨 Test 4: Player Highlight Story (9:16)")
    story_template = next(
        (t for t in templates.data if 'story' in t['name']),
        templates.data[0]
    )

    response = requests.get(story_template['image_url'])
    template_bytes = response.content
    graphic_bytes = create_mock_graphic_player_stats()

    result = composer.compose_post(
        template_image=template_bytes,
        graphic_image=graphic_bytes,
        template_config={
            'graphic_position': 'center',
            'graphic_scale': 0.6,
            'margin': 100
        },
        format_type='story'
    )

    if result:
        output_path = f"{output_dir}/player_story_composed.png"
        with open(output_path, 'wb') as f:
            f.write(result)
        logger.info(f"✅ Guardado: {output_path}\n")

    logger.info("="*60)
    logger.info("TESTS COMPLETADOS")
    logger.info("="*60)
    logger.info(f"\n📂 Imágenes guardadas en: {output_dir}")
    logger.info(f"   Abre las imágenes para verificar la composición\n")


def main():
    """Ejecutar tests."""
    print("\n" + "🎨 "*30)
    print("TEST IMAGE COMPOSER SERVICE")
    print("🎨 "*30 + "\n")

    test_image_composition()


if __name__ == '__main__':
    main()
