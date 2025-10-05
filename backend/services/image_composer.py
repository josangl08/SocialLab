"""
Image Composer Service
Composición de imágenes finales para Instagram usando Pillow.
Combina templates base con gráficos de PROJECT 1.
"""

import logging
from typing import Dict, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont
import io
import os

logger = logging.getLogger(__name__)


class ImageComposerService:
    """Servicio para composición de imágenes con templates."""

    # Dimensiones Instagram
    INSTAGRAM_SQUARE = (1080, 1080)
    INSTAGRAM_PORTRAIT = (1080, 1350)
    INSTAGRAM_STORY = (1080, 1920)

    def __init__(self):
        """Inicializa el compositor de imágenes."""
        self.default_format = 'square'

    def compose_post(
        self,
        template_image: bytes,
        graphic_image: bytes,
        template_config: Optional[Dict] = None,
        format_type: str = 'square'
    ) -> Optional[bytes]:
        """
        Compone imagen final combinando template + gráfico de PROJECT 1.

        Args:
            template_image: Bytes de imagen template base
            graphic_image: Bytes de gráfico de PROJECT 1
            template_config: Configuración del template (posición, escala, etc)
            format_type: 'square' | 'portrait' | 'story'

        Returns:
            Bytes de imagen compuesta o None si falla
        """
        try:
            # Cargar imágenes
            template = Image.open(io.BytesIO(template_image))
            graphic = Image.open(io.BytesIO(graphic_image))

            # Obtener dimensiones target
            target_size = self._get_target_size(format_type)

            # Redimensionar template al tamaño target
            template = self._resize_to_fit(template, target_size)

            # Aplicar configuración del template
            config = template_config or {}
            composed = self._apply_template_config(
                template,
                graphic,
                config,
                target_size
            )

            # Convertir a bytes
            output = io.BytesIO()
            composed.save(output, format='PNG', quality=95)
            output.seek(0)

            logger.info(
                f"✅ Imagen compuesta: {composed.size[0]}x{composed.size[1]}"
            )
            return output.getvalue()

        except Exception as e:
            logger.error(f"❌ Error componiendo imagen: {str(e)}")
            return None

    def _get_target_size(self, format_type: str) -> Tuple[int, int]:
        """Obtiene dimensiones según tipo de formato."""
        formats = {
            'square': self.INSTAGRAM_SQUARE,
            'portrait': self.INSTAGRAM_PORTRAIT,
            'story': self.INSTAGRAM_STORY
        }
        return formats.get(format_type, self.INSTAGRAM_SQUARE)

    def _resize_to_fit(
        self,
        image: Image.Image,
        target_size: Tuple[int, int]
    ) -> Image.Image:
        """
        Redimensiona imagen manteniendo aspect ratio.

        Args:
            image: Imagen a redimensionar
            target_size: Tamaño objetivo (width, height)

        Returns:
            Imagen redimensionada
        """
        # Si ya es del tamaño correcto, retornar
        if image.size == target_size:
            return image

        # Calcular ratio
        img_ratio = image.width / image.height
        target_ratio = target_size[0] / target_size[1]

        if img_ratio > target_ratio:
            # Imagen más ancha - ajustar por ancho
            new_width = target_size[0]
            new_height = int(new_width / img_ratio)
        else:
            # Imagen más alta - ajustar por alto
            new_height = target_size[1]
            new_width = int(new_height * img_ratio)

        resized = image.resize((new_width, new_height), Image.LANCZOS)

        # Crear canvas del tamaño target y centrar
        canvas = Image.new('RGB', target_size, (255, 255, 255))
        paste_x = (target_size[0] - new_width) // 2
        paste_y = (target_size[1] - new_height) // 2
        canvas.paste(resized, (paste_x, paste_y))

        return canvas

    def _apply_template_config(
        self,
        template: Image.Image,
        graphic: Image.Image,
        config: Dict,
        target_size: Tuple[int, int]
    ) -> Image.Image:
        """
        Aplica configuración del template para overlay del gráfico.

        Args:
            template: Imagen template base
            graphic: Gráfico de PROJECT 1
            config: Configuración (position, scale, opacity, etc)
            target_size: Tamaño final

        Returns:
            Imagen compuesta
        """
        # Configuración por defecto
        position = config.get('graphic_position', 'center')
        scale = config.get('graphic_scale', 0.8)
        opacity = config.get('graphic_opacity', 100)
        margin = config.get('margin', 50)

        # Calcular tamaño del gráfico según scale
        max_width = int(target_size[0] * scale) - (margin * 2)
        max_height = int(target_size[1] * scale) - (margin * 2)

        # Redimensionar gráfico manteniendo aspect ratio
        graphic_resized = self._resize_graphic(
            graphic,
            max_width,
            max_height
        )

        # Calcular posición
        x, y = self._calculate_position(
            position,
            template.size,
            graphic_resized.size,
            margin
        )

        # Crear copia del template para overlay
        result = template.copy()

        # Aplicar opacity al gráfico si es necesario
        if opacity < 100:
            graphic_resized = self._apply_opacity(graphic_resized, opacity)

        # Overlay del gráfico
        if graphic_resized.mode == 'RGBA':
            result.paste(graphic_resized, (x, y), graphic_resized)
        else:
            result.paste(graphic_resized, (x, y))

        return result

    def _resize_graphic(
        self,
        graphic: Image.Image,
        max_width: int,
        max_height: int
    ) -> Image.Image:
        """Redimensiona gráfico manteniendo aspect ratio."""
        ratio = min(max_width / graphic.width, max_height / graphic.height)
        new_width = int(graphic.width * ratio)
        new_height = int(graphic.height * ratio)

        return graphic.resize((new_width, new_height), Image.LANCZOS)

    def _calculate_position(
        self,
        position: str,
        template_size: Tuple[int, int],
        graphic_size: Tuple[int, int],
        margin: int
    ) -> Tuple[int, int]:
        """
        Calcula posición del gráfico según configuración.

        Args:
            position: 'center' | 'top' | 'bottom' | 'top-left' | etc
            template_size: Tamaño del template
            graphic_size: Tamaño del gráfico
            margin: Margen en píxeles

        Returns:
            Tupla (x, y) con coordenadas
        """
        tw, th = template_size
        gw, gh = graphic_size

        positions = {
            'center': ((tw - gw) // 2, (th - gh) // 2),
            'top': ((tw - gw) // 2, margin),
            'bottom': ((tw - gw) // 2, th - gh - margin),
            'top-left': (margin, margin),
            'top-right': (tw - gw - margin, margin),
            'bottom-left': (margin, th - gh - margin),
            'bottom-right': (tw - gw - margin, th - gh - margin),
        }

        return positions.get(position, positions['center'])

    def _apply_opacity(
        self,
        image: Image.Image,
        opacity: int
    ) -> Image.Image:
        """
        Aplica opacidad a una imagen.

        Args:
            image: Imagen original
            opacity: Opacidad 0-100

        Returns:
            Imagen con opacidad aplicada
        """
        if image.mode != 'RGBA':
            image = image.convert('RGBA')

        # Crear capa con opacidad
        alpha = image.split()[3]
        alpha = alpha.point(lambda p: int(p * opacity / 100))
        image.putalpha(alpha)

        return image

    def create_template_preview(
        self,
        template_image: bytes,
        format_type: str = 'square'
    ) -> Optional[bytes]:
        """
        Crea preview de template sin gráfico.

        Args:
            template_image: Bytes de template
            format_type: Formato de salida

        Returns:
            Bytes de preview o None
        """
        try:
            template = Image.open(io.BytesIO(template_image))
            target_size = self._get_target_size(format_type)

            # Redimensionar
            preview = self._resize_to_fit(template, target_size)

            # Agregar marca de agua "PREVIEW"
            draw = ImageDraw.Draw(preview)
            text = "PREVIEW"

            # Intentar cargar fuente
            try:
                font = ImageFont.truetype(
                    "/System/Library/Fonts/Helvetica.ttc",
                    80
                )
            except Exception:
                font = ImageFont.load_default()

            # Calcular posición centrada
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            x = (preview.width - text_width) // 2
            y = (preview.height - text_height) // 2

            # Dibujar texto con fondo semitransparente
            draw.text(
                (x, y),
                text,
                fill=(255, 255, 255, 180),
                font=font
            )

            # Convertir a bytes
            output = io.BytesIO()
            preview.save(output, format='PNG')
            output.seek(0)

            return output.getvalue()

        except Exception as e:
            logger.error(f"❌ Error creando preview: {str(e)}")
            return None

    def validate_image_dimensions(
        self,
        image_bytes: bytes,
        min_width: int = 320,
        min_height: int = 320
    ) -> bool:
        """
        Valida que una imagen cumpla dimensiones mínimas.

        Args:
            image_bytes: Bytes de imagen
            min_width: Ancho mínimo
            min_height: Alto mínimo

        Returns:
            True si cumple requisitos
        """
        try:
            image = Image.open(io.BytesIO(image_bytes))
            width, height = image.size

            if width < min_width or height < min_height:
                logger.warning(
                    f"⚠️  Imagen muy pequeña: {width}x{height} "
                    f"(mínimo: {min_width}x{min_height})"
                )
                return False

            return True

        except Exception as e:
            logger.error(f"❌ Error validando imagen: {str(e)}")
            return False


def get_image_composer() -> ImageComposerService:
    """Factory function para obtener compositor de imágenes."""
    return ImageComposerService()


# Testing
if __name__ == '__main__':
    import sys

    logging.basicConfig(level=logging.INFO)

    composer = get_image_composer()

    # Test básico: crear canvas de prueba
    print("\n🎨 Creando canvas de prueba...")

    # Crear template de prueba (azul)
    template = Image.new('RGB', (1200, 1200), (41, 128, 185))
    template_bytes = io.BytesIO()
    template.save(template_bytes, format='PNG')
    template_bytes = template_bytes.getvalue()

    # Crear gráfico de prueba (rojo)
    graphic = Image.new('RGB', (800, 600), (231, 76, 60))
    graphic_bytes = io.BytesIO()
    graphic.save(graphic_bytes, format='PNG')
    graphic_bytes = graphic_bytes.getvalue()

    # Componer imagen
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
        # Guardar resultado
        output_path = '/tmp/test_composed.png'
        with open(output_path, 'wb') as f:
            f.write(result)
        print(f"✅ Imagen compuesta guardada: {output_path}")
    else:
        print("❌ Error componiendo imagen")

    # Test de preview
    print("\n🖼️  Creando preview...")
    preview = composer.create_template_preview(
        template_bytes,
        format_type='square'
    )

    if preview:
        preview_path = '/tmp/test_preview.png'
        with open(preview_path, 'wb') as f:
            f.write(preview)
        print(f"✅ Preview guardado: {preview_path}")
    else:
        print("❌ Error creando preview")

    print("\n✨ Tests completados")
