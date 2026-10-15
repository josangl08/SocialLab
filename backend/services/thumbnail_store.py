"""
Miniaturas de los posts guardadas en el bucket público `thumbnails` (persistent-thumbnails).

Ruta: `{user_id}/{post_id}/{key}_{size}.webp`, con `key` aleatorio por versión de imagen, así que
un objeto nunca cambia y puede cachearse un año. `posts.thumbnail_url_base` guarda la URL pública
sin sufijo; un trigger la anula al cambiar `media_url` o `drive_file_id`.
Escribe siempre con el cliente service role.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Optional

from database.supabase_client import get_supabase_admin_client
from services.media_thumbnails import THUMBNAIL_MEDIA_TYPE

logger = logging.getLogger(__name__)

THUMBNAIL_BUCKET = "thumbnails"
# storage3 solo admite segundos: Storage sirve `max-age=31536000`
STORAGE_CACHE_SECONDS = "31536000"
# Objetos más recientes que esto no se borran: pueden ser de una generación en curso en otra
# instancia que aún no ha guardado su `thumbnail_url_base`
DELETE_GRACE = timedelta(minutes=10)
_LIST_PAGE = 100

# post_id → [lock, peticiones que lo usan]; se quita al quedar libre
_locks: dict[int, list] = {}


def _storage() -> Any:
    return get_supabase_admin_client().storage.from_(THUMBNAIL_BUCKET)


def _folder(user_id: str, post_id: int) -> str:
    return f"{user_id}/{post_id}"


def current_key(base: Optional[str], user_id: str, post_id: int) -> Optional[str]:
    """`key` de la versión a la que apunta `thumbnail_url_base` (None si no es de este post)."""
    marker = f"/{THUMBNAIL_BUCKET}/{_folder(user_id, post_id)}/"
    if not base or marker not in base:
        return None
    return base.split(marker, 1)[1] or None


def _list_all(path: str) -> list[dict]:
    items: list[dict] = []
    offset = 0
    while True:
        page = _storage().list(path, {"limit": _LIST_PAGE, "offset": offset})
        items.extend(page)
        if len(page) < _LIST_PAGE:
            return items
        offset += _LIST_PAGE


def _is_old(item: dict, now: datetime) -> bool:
    created = item.get("created_at")
    if not created:
        return True
    return now - datetime.fromisoformat(created.replace("Z", "+00:00")) >= DELETE_GRACE


def _remove_except(user_id: str, post_id: int, keep_key: Optional[str]) -> int:
    folder = _folder(user_id, post_id)
    now = datetime.now(timezone.utc)
    stale = [
        f"{folder}/{item['name']}"
        for item in _list_all(folder)
        if item.get("id")  # las carpetas no tienen id
        and not (keep_key and item["name"].startswith(f"{keep_key}_"))
        and _is_old(item, now)
    ]
    if stale:
        _storage().remove(stale)
    return len(stale)


def _read_base(post_id: int) -> Optional[str]:
    result = (
        get_supabase_admin_client().table("posts").select("thumbnail_url_base")
        .eq("id", post_id).limit(1).execute()
    )
    return result.data[0].get("thumbnail_url_base") if result.data else None


def remove_stale_versions(user_id: str, post_id: int) -> int:
    """Borra las versiones que no son la vigente (relee la columna antes de borrar)."""
    return _remove_except(user_id, post_id, current_key(_read_base(post_id), user_id, post_id))


def _save(user_id: str, post_id: int, sizes: dict[int, bytes], expected_source: dict) -> Optional[str]:
    key = uuid.uuid4().hex
    storage = _storage()
    prefix = f"{_folder(user_id, post_id)}/{key}"
    for size, data in sizes.items():
        storage.upload(
            f"{prefix}_{size}.webp", data,
            {"content-type": THUMBNAIL_MEDIA_TYPE, "cache-control": STORAGE_CACHE_SECONDS},
        )
    base = storage.get_public_url(prefix)

    # Solo si la imagen sigue siendo la que se usó para generar (AD-4)
    query = get_supabase_admin_client().table("posts").update({"thumbnail_url_base": base}).eq("id", post_id)
    for column in ("media_url", "drive_file_id"):
        value = expected_source.get(column)
        query = query.eq(column, value) if value else query.is_(column, "null")
    saved = bool(query.execute().data)
    if not saved:
        logger.info(f"Post {post_id}: la imagen cambió mientras se generaba la miniatura; no se guarda")

    remove_stale_versions(user_id, post_id)
    return base if saved else None


async def save_thumbnails(
    user_id: str, post_id: int, sizes: dict[int, bytes], expected_source: dict
) -> Optional[str]:
    """Sube los tamaños, guarda `thumbnail_url_base` si la imagen no cambió entretanto y borra
    las versiones anteriores. Devuelve la base guardada o None. Lanza si falla Storage."""
    return await asyncio.to_thread(_save, user_id, post_id, sizes, expected_source)


async def generate_once(
    post_id: int, render: Callable[[], Awaitable[Optional[dict[int, bytes]]]]
) -> tuple[Optional[str], Optional[dict[int, bytes]]]:
    """Ejecuta `render` con un lock por post. Si había otra generación en curso en este proceso,
    al entrar comprueba si ya guardó la miniatura: devuelve (base, None) sin volver a generar.
    Si no, devuelve (None, lo que devuelva `render`)."""
    entry = _locks.setdefault(post_id, [asyncio.Lock(), 0])
    entry[1] += 1
    waited = entry[0].locked()
    try:
        async with entry[0]:
            if waited:
                base = await asyncio.to_thread(_read_base, post_id)
                if base:
                    return base, None
            return None, await render()
    finally:
        entry[1] -= 1
        if entry[1] == 0:
            _locks.pop(post_id, None)


def _cleanup() -> int:
    removed = 0
    for user_folder in _list_all(""):
        if user_folder.get("id"):
            continue
        user_id = user_folder["name"]
        post_folders = [item["name"] for item in _list_all(user_id) if not item.get("id")]
        post_ids = [int(name) for name in post_folders if name.isdigit()]
        bases: dict[int, Optional[str]] = {}
        if post_ids:
            rows = (
                get_supabase_admin_client().table("posts").select("id, user_id, thumbnail_url_base")
                .in_("id", post_ids).execute().data or []
            )
            bases = {row["id"]: row.get("thumbnail_url_base") for row in rows if str(row.get("user_id")) == user_id}
        for post_id in post_ids:
            removed += _remove_except(user_id, post_id, current_key(bases.get(post_id), user_id, post_id))
    return removed


def cleanup_orphan_thumbnails() -> int:
    """Job diario (BackgroundScheduler, en su propio hilo): borra miniaturas de posts que ya no
    existen, sin miniatura vigente o de versiones viejas. Idempotente: lo vigente nunca se
    borra. Devuelve los objetos borrados."""
    try:
        removed = _cleanup()
    except Exception as e:
        logger.error(f"Limpieza de miniaturas huérfanas fallida: {e}", exc_info=True)
        return 0
    logger.info(f"Limpieza de miniaturas: {removed} objetos borrados")
    return removed
