"""
Miniaturas de las imágenes de los posts para el calendario y el planner.

Drive: miniatura que genera Google (sirve también para vídeos); si no hay, el original
redimensionado. Storage: la URL pública redimensionada. Salida siempre JPEG pequeño, con
caché LRU en memoria. Las descargas van en hilos para no bloquear el event loop.
"""

import asyncio
import io
import logging
import re
from collections import OrderedDict
from enum import IntEnum
from typing import Literal, Optional, Tuple

import requests

from services.google_drive_connector import get_drive_connector
from services.post_media import open_image

logger = logging.getLogger(__name__)

ThumbnailSource = Literal["drive", "storage"]



class ThumbnailSize(IntEnum):
    """Tamaños permitidos (lado mayor en px); cualquier otro valor en la query da 422."""
    S160 = 160
    S320 = 320
    S640 = 640


DEFAULT_THUMBNAIL_SIZE = ThumbnailSize.S320
IMAGE_CACHE_HEADERS = {"Cache-Control": "private, max-age=86400"}
JPEG_QUALITY = 80
CACHE_MAX_ENTRIES = 300
_VIDEO_URL = re.compile(r"\.(mp4|mov|webm|ogg|m4v)(\?.*)?$", re.IGNORECASE)

_cache: "OrderedDict[Tuple[str, str, int, Optional[str]], bytes]" = OrderedDict()


def is_storage_video(media_url: str) -> bool:
    return bool(_VIDEO_URL.search(media_url))


def to_thumbnail(data: bytes, size: int) -> bytes:
    """JPEG con el lado mayor = size (nunca amplía). Admite HEIC."""
    img = open_image(data)
    img.thumbnail((size, size))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return out.getvalue()


def _drive_thumbnail(user_id: str, file_id: str, size: int) -> Optional[bytes]:
    drive = get_drive_connector(user_id)
    data = drive.get_thumbnail_bytes(file_id, size)
    if data is None:
        original, mime_type = drive.get_image_bytes(file_id)
        if not mime_type.startswith("image/"):
            return None
        data = original
    return to_thumbnail(data, size)


def _storage_thumbnail(media_url: str, size: int) -> Optional[bytes]:
    if is_storage_video(media_url):
        return None
    response = requests.get(media_url, timeout=30)
    response.raise_for_status()
    return to_thumbnail(response.content, size)


async def get_thumbnail(
    source: ThumbnailSource, source_id: str, size: int, user_id: Optional[str] = None
) -> Optional[bytes]:
    """Miniatura JPEG del origen (drive_file_id o media_url). None si no hay imagen
    previsualizable (vídeo de Storage, archivo de Drive sin miniatura que no es imagen).
    Lanza excepción si Drive o Storage fallan."""
    # En Drive el acceso depende de las credenciales del usuario: la clave lo incluye para
    # no servir a otro usuario una miniatura que no podría descargar
    key = (source, source_id, size, user_id if source == "drive" else None)
    cached = _cache.get(key)
    if cached is not None:
        _cache.move_to_end(key)
        return cached

    if source == "drive":
        if not user_id:
            raise ValueError("user_id es obligatorio para miniaturas de Drive")
        data = await asyncio.to_thread(_drive_thumbnail, user_id, source_id, size)
    else:
        data = await asyncio.to_thread(_storage_thumbnail, source_id, size)

    if data is not None:
        _cache[key] = data
        _cache.move_to_end(key)
        while len(_cache) > CACHE_MAX_ENTRIES:
            _cache.popitem(last=False)
    return data


def clear_cache() -> None:
    _cache.clear()
