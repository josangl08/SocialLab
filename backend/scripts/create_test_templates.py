"""
Script para crear templates de prueba.
Genera imágenes PNG simples para testing.
"""

from PIL import Image, ImageDraw, ImageFont
import os

# Crear directorio temporal para templates
os.makedirs('/tmp/test_templates', exist_ok=True)

def create_template(
    filename: str,
    bg_color: tuple,
    text: str,
    size: tuple = (1080, 1080)
):
    """Crea un template de prueba simple."""

    # Crear imagen con color de fondo
    img = Image.new('RGB', size, bg_color)
    draw = ImageDraw.Draw(img)

    # Intentar cargar fuente
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 60)
        title_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 80)
    except:
        font = ImageFont.load_default()
        title_font = ImageFont.load_default()

    # Dibujar título
    title_bbox = draw.textbbox((0, 0), text, font=title_font)
    title_width = title_bbox[2] - title_bbox[0]
    title_height = title_bbox[3] - title_bbox[1]

    draw.text(
        ((size[0] - title_width) // 2, 50),
        text,
        fill=(255, 255, 255),
        font=title_font
    )

    # Dibujar área central (zona para gráfico)
    margin = 150
    rect_coords = [
        margin,
        margin + 150,
        size[0] - margin,
        size[1] - margin - 100
    ]

    # Rectángulo con borde
    draw.rectangle(rect_coords, outline=(255, 255, 255), width=5)

    # Texto indicador
    indicator_text = "ZONA PARA GRÁFICO"
    indicator_bbox = draw.textbbox((0, 0), indicator_text, font=font)
    indicator_width = indicator_bbox[2] - indicator_bbox[0]

    draw.text(
        ((size[0] - indicator_width) // 2, size[1] // 2),
        indicator_text,
        fill=(255, 255, 255, 128),
        font=font
    )

    # Guardar
    path = f'/tmp/test_templates/{filename}'
    img.save(path)
    print(f'✅ Creado: {path}')
    return path


# Crear 5 templates de prueba
templates = [
    {
        'filename': 'player_stats_modern_blue.png',
        'bg_color': (41, 128, 185),  # Azul
        'text': 'PLAYER STATS'
    },
    {
        'filename': 'player_stats_dark_elegant.png',
        'bg_color': (44, 62, 80),  # Gris oscuro
        'text': 'PLAYER STATS'
    },
    {
        'filename': 'match_result_victory_green.png',
        'bg_color': (39, 174, 96),  # Verde
        'text': 'MATCH RESULT'
    },
    {
        'filename': 'team_performance_gradient.png',
        'bg_color': (142, 68, 173),  # Morado
        'text': 'TEAM PERFORMANCE'
    },
    {
        'filename': 'story_player_highlight.png',
        'bg_color': (231, 76, 60),  # Rojo
        'text': 'PLAYER HIGHLIGHT',
        'size': (1080, 1920)  # Story format
    }
]

print("🎨 Creando templates de prueba...\n")

created = []
for template in templates:
    path = create_template(
        template['filename'],
        template['bg_color'],
        template['text'],
        template.get('size', (1080, 1080))
    )
    created.append(path)

print(f"\n✅ {len(created)} templates creados en: /tmp/test_templates/")
print("\n📋 Siguiente paso:")
print("1. Abre Google Drive")
print("2. Ve a la carpeta: TEMPLATES_SOCIALLAB")
print("3. Sube estos archivos:")
for path in created:
    print(f"   - {os.path.basename(path)}")

print("\n💡 O cópialos desde terminal:")
print(f"   open /tmp/test_templates/")
