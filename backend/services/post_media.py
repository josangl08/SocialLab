"""
Media de los posts: abrir imágenes en cualquier formato (incluido HEIC) y subir a
Storage el original de Drive de un post aprobado para que el publisher tenga media_url.
"""

import io
import logging
import math
from typing import Any, Dict, Optional, Tuple

from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

from database.supabase_client import get_supabase_admin_client

logger = logging.getLogger(__name__)

register_heif_opener()

# Graph API: las imágenes deben ser JPEG de 8 MB como máximo
INSTAGRAM_IMAGE_MAX_BYTES = 8 * 1024 * 1024
# Graph API: proporción de las imágenes del feed entre 4:5 y 1.91:1
FEED_MIN_RATIO, FEED_MAX_RATIO = 4 / 5, 1.91
FEED_FORMATS = {"post", "carousel", "feed", "image"}
STORAGE_BUCKET = "posts"
# Orientaciones EXIF que giran la imagen 90°
_EXIF_ROTATED = {5, 6, 7, 8}


def open_image(data: bytes) -> Image.Image:
    """Abre cualquier formato soportado por Pillow o pillow-heif, orientado según EXIF y en RGB."""
    with Image.open(io.BytesIO(data)) as img:
        return ImageOps.exif_transpose(img).convert("RGB")


def image_size(data: bytes) -> Tuple[int, int]:
    """(ancho, alto) tal como se ve la imagen (orientación EXIF aplicada), sin decodificarla."""
    with Image.open(io.BytesIO(data)) as img:
        width, height = img.size
        if img.getexif().get(0x0112) in _EXIF_ROTATED:
            width, height = height, width
    return width, height


def image_extension(data: bytes) -> str:
    """Extensión real de la imagen (para enviar el original con su formato)."""
    with Image.open(io.BytesIO(data)) as img:
        fmt = (img.format or "JPEG").upper()
    return {"JPEG": "jpg", "HEIF": "heic"}.get(fmt, fmt.lower())


def is_feed_post(post: Dict[str, Any]) -> bool:
    fmt = (post.get("content_format") or post.get("post_type") or "post").lower()
    return fmt in FEED_FORMATS


def feed_crop_target(width: int, height: int) -> Optional[Tuple[str, int, int]]:
    """Recorte necesario para el feed, a la máxima resolución posible: (proporción, ancho, alto).
    None si la imagen ya está entre 4:5 y 1.91:1."""
    ratio = width / height
    if ratio < FEED_MIN_RATIO:
        return "4:5", width, math.floor(width * 5 / 4)
    if ratio > FEED_MAX_RATIO:
        return "1.91:1", math.floor(height * FEED_MAX_RATIO), height
    return None


def to_jpeg(img: Image.Image, max_bytes: int, quality: int = 95) -> bytes:
    """JPEG que quepa en max_bytes conservando la resolución original: baja la calidad hasta 50
    y solo si no basta reduce las dimensiones."""
    while True:
        for q in range(quality, 49, -5):
            out = io.BytesIO()
            img.save(out, format="JPEG", quality=q)
            if out.tell() <= max_bytes:
                return out.getvalue()
        img = img.resize((int(img.width * 0.85), int(img.height * 0.85)), Image.LANCZOS)


def prepare_image_for_instagram(data: bytes, mime_type: str) -> bytes:
    """El original si Instagram lo acepta tal cual (JPEG ≤ 8 MB); si no, la conversión mínima."""
    if mime_type == "image/jpeg" and len(data) <= INSTAGRAM_IMAGE_MAX_BYTES:
        return data
    return to_jpeg(open_image(data), INSTAGRAM_IMAGE_MAX_BYTES)


def materialize_drive_media(post: Dict[str, Any]) -> str:
    """Descarga el original de Drive del post, lo sube a Storage y guarda posts.media_url.

    Idempotente: la ruta en Storage es fija por post y archivo y se sobrescribe."""
    from services.google_drive_connector import get_drive_connector

    post_id, file_id, user_id = post["id"], post.get("drive_file_id"), post.get("user_id")
    if not file_id or not user_id:
        raise ValueError(f"Post {post_id} has no Drive image to publish")

    drive = get_drive_connector(str(user_id))
    meta = drive.service.files().get(fileId=file_id, fields="name, mimeType").execute()
    data = drive.download_file_bytes(file_id)
    if not data:
        raise ValueError(f"Could not download Drive file {file_id} for post {post_id}")

    mime_type = meta.get("mimeType", "")
    if mime_type.startswith("image/") and is_feed_post(post):
        target = feed_crop_target(*image_size(data))
        if target:
            raise ValueError(
                f"Post {post_id}: la imagen debe recortarse a {target[0]} ({target[1]}x{target[2]} px) para el feed"
            )
    if mime_type.startswith("image/"):
        data, content_type, ext = prepare_image_for_instagram(data, mime_type), "image/jpeg", "jpg"
    else:
        name = meta.get("name", "")
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else "mp4"
        content_type = mime_type or "video/mp4"

    path = f"drive/{post_id}_{file_id}.{ext}"
    storage = get_supabase_admin_client().storage.from_(STORAGE_BUCKET)
    storage.upload(path, data, {"content-type": content_type, "upsert": "true"})
    media_url = storage.get_public_url(path)

    get_supabase_admin_client().table("posts").update({"media_url": media_url}).eq("id", post_id).execute()
    logger.info(f"Post {post_id}: original de Drive {file_id} subido a Storage ({len(data)} bytes)")
    return media_url

