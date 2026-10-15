"""
Miniaturas de las imágenes de los posts para el calendario y el planner.

Drive: miniatura que genera Google (sirve también para vídeos); si no hay, el original
redimensionado. Storage: la URL pública redimensionada. Salida siempre WebP (~30 % menos
que JPEG con la misma calidad visual), con caché LRU en memoria. Para los posts se generan
los 4 tamaños de una descarga (`render_all_sizes`) y se guardan en Storage (thumbnail_store). Las descargas van en hilos para no bloquear el event loop.
"""

import asyncio
import io
import logging
import re
from collections import OrderedDict
from enum import IntEnum
from typing import Literal, Optional, Tuple

import requests
from PIL import Image

from services.google_drive_connector import get_drive_connector
from services.post_media import open_image

logger = logging.getLogger(__name__)

ThumbnailSource = Literal["drive", "storage"]



class ThumbnailSize(IntEnum):
    """Tamaños permitidos (lado mayor en px); cualquier otro valor en la query da 422."""
    S160 = 160
    S320 = 320
    S480 = 480
    S640 = 640


DEFAULT_THUMBNAIL_SIZE = ThumbnailSize.S320
IMAGE_CACHE_HEADERS = {"Cache-Control": "private, max-age=86400"}
THUMBNAIL_QUALITY = 82
THUMBNAIL_MEDIA_TYPE = "image/webp"
CACHE_MAX_ENTRIES = 300
_VIDEO_URL = re.compile(r"\.(mp4|mov|webm|ogg|m4v)(\?.*)?$", re.IGNORECASE)

_cache: "OrderedDict[Tuple[str, str, int, Optional[str]], bytes]" = OrderedDict()


def is_storage_video(media_url: str) -> bool:
    return bool(_VIDEO_URL.search(media_url))


def to_thumbnail(data: bytes, size: int) -> bytes:
    """WebP con el lado mayor = size (nunca amplía). Admite HEIC."""
    img = open_image(data)
    img.thumbnail((size, size), Image.LANCZOS)
    out = io.BytesIO()
    img.save(out, format="WEBP", quality=THUMBNAIL_QUALITY, method=6)
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
    """Miniatura WebP del origen (drive_file_id o media_url). None si no hay imagen
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


ALL_SIZES = sorted((int(size) for size in ThumbnailSize), reverse=True)  # 640 → 160


def _render_all(data: bytes) -> dict[int, bytes]:
    """Los 4 tamaños reduciendo desde la misma imagen abierta (de mayor a menor)."""
    img = open_image(data)
    sizes: dict[int, bytes] = {}
    for size in ALL_SIZES:
        img.thumbnail((size, size), Image.LANCZOS)
        out = io.BytesIO()
        img.save(out, format="WEBP", quality=THUMBNAIL_QUALITY, method=6)
        sizes[size] = out.getvalue()
    return sizes


def _drive_all_sizes(user_id: str, file_id: str) -> Optional[dict[int, bytes]]:
    drive = get_drive_connector(user_id)
    data = drive.get_thumbnail_bytes(file_id, max(ALL_SIZES))
    if data is None:
        original, mime_type = drive.get_image_bytes(file_id)
        if not mime_type.startswith("image/"):
            return None
        data = original
    return _render_all(data)


def _storage_all_sizes(media_url: str) -> Optional[dict[int, bytes]]:
    if is_storage_video(media_url):
        return None
    response = requests.get(media_url, timeout=30)
    response.raise_for_status()
    return _render_all(response.content)


async def render_all_sizes(
    source: ThumbnailSource, source_id: str, user_id: Optional[str] = None
) -> Optional[dict[int, bytes]]:
    """Los 4 tamaños WebP con una sola descarga del origen (Drive a 640, Storage original).
    Quedan en la LRU: si no se pueden guardar en Storage, no se vuelve a descargar.
    None si no hay imagen previsualizable; lanza excepción si Drive o Storage fallan."""
    if source == "drive" and not user_id:
        raise ValueError("user_id es obligatorio para miniaturas de Drive")
    owner = user_id if source == "drive" else None
    cached = {size: _cache.get((source, source_id, size, owner)) for size in ALL_SIZES}
    if all(data is not None for data in cached.values()):
        return cached  # type: ignore[return-value]

    if source == "drive":
        sizes = await asyncio.to_thread(_drive_all_sizes, user_id, source_id)
    else:
        sizes = await asyncio.to_thread(_storage_all_sizes, source_id)

    if sizes is not None:
        for size, data in sizes.items():
            _cache[(source, source_id, size, owner)] = data
            _cache.move_to_end((source, source_id, size, owner))
        while len(_cache) > CACHE_MAX_ENTRIES:
            _cache.popitem(last=False)
    return sizes


def clear_cache() -> None:
    _cache.clear()
