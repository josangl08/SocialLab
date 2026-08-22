"""
Drive Webhook Service
Registro/renovación de canales de notificación push de Google Drive y análisis
reactivo de imágenes nuevas — evita esperar a la sesión semanal de Hermes para
analizar fotos recién subidas.
"""

import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import config
from database.supabase_client import get_supabase_admin_client
from services.google_drive_connector import get_drive_connector
from services.gemini_service import analyze_image_vision

logger = logging.getLogger(__name__)


def register_channel(account_id: int, folder_id: str) -> Optional[dict]:
    """Registers a Drive Push Notification channel for this account's folder,
    replacing any previous channel row for it. Returns the raw watch_folder
    result, or None if Drive isn't connected for this account."""
    supabase = get_supabase_admin_client()
    acc_res = supabase.table("instagram_accounts").select("user_id").eq("id", account_id).execute()
    if not acc_res.data:
        return None
    user_id = acc_res.data[0]["user_id"]

    try:
        connector = get_drive_connector(user_id)
    except Exception as e:
        logger.warning(f"No se pudo obtener conector de Drive para la cuenta {account_id}, saltando registro de webhook: {e}")
        return None

    channel_id = str(uuid.uuid4())
    token = secrets.token_urlsafe(32)
    webhook_url = f"{config.APP_BASE_URL}/api/drive/webhook"

    result = connector.watch_folder(folder_id, webhook_url, channel_id, token)
    if not result:
        return None

    expiration = datetime.fromtimestamp(int(result["expiration"]) / 1000, tz=timezone.utc)

    supabase.table("drive_watch_channels").delete().eq("account_id", account_id).execute()
    supabase.table("drive_watch_channels").insert({
        "account_id": account_id,
        "channel_id": result["channel_id"],
        "resource_id": result["resource_id"],
        "folder_id": folder_id,
        "channel_token": token,
        "expiration": expiration.isoformat(),
    }).execute()

    logger.info(f"Drive watch channel registered for account {account_id}, expires {expiration.isoformat()}")
    return result


def renew_expiring_channels(within_minutes: int = 20) -> int:
    """Re-registers any channel expiring within the given window. Drive channels
    can't be renewed in place — this registers a fresh one (replacing the row)
    and lets the old one lapse naturally at its original expiration.

    Default window is short (20 min) because a live registration against this
    account's real folder came back with a ~1 hour expiration — Drive's actual
    TTL for this resource type, confirmed empirically rather than assumed."""
    supabase = get_supabase_admin_client()
    cutoff = (datetime.now(timezone.utc) + timedelta(minutes=within_minutes)).isoformat()
    expiring = supabase.table("drive_watch_channels").select("account_id, folder_id").lte("expiration", cutoff).execute()

    renewed = 0
    for row in expiring.data or []:
        if register_channel(row["account_id"], row["folder_id"]):
            renewed += 1
    return renewed


def handle_notification(channel_id: str, resource_state: str, channel_token: str) -> None:
    """Validates the incoming Drive push notification against the stored channel
    token (Google's push notifications carry no other credential) and, on a real
    file change, triggers the fast-path analysis for that account's folder."""
    supabase = get_supabase_admin_client()
    channel_res = supabase.table("drive_watch_channels").select("*").eq("channel_id", channel_id).execute()
    if not channel_res.data:
        logger.warning(f"Drive webhook: unknown channel_id {channel_id}, ignoring")
        return

    channel = channel_res.data[0]
    if channel["channel_token"] != channel_token:
        logger.warning(f"Drive webhook: token mismatch for channel {channel_id}, ignoring")
        return

    if resource_state not in ("add", "update"):
        return

    analyze_new_files_fast_path(channel["account_id"], channel["folder_id"])


def analyze_new_files_fast_path(account_id: int, folder_id: str) -> int:
    """Analyzes any image in the folder not yet in visual_analyses, directly
    (no Hermes/MCP tool-calling loop needed — we already know exactly what to
    do). Returns the number of images analyzed."""
    supabase = get_supabase_admin_client()
    acc_res = supabase.table("instagram_accounts").select("user_id").eq("id", account_id).execute()
    if not acc_res.data:
        return 0
    user_id = acc_res.data[0]["user_id"]

    try:
        connector = get_drive_connector(user_id)
    except RuntimeError:
        return 0

    files = connector.list_files(folder_id=folder_id)
    image_files = [f for f in files if f.get("mimeType", "").startswith("image/")]

    existing = supabase.table("visual_analyses").select("drive_file_id").eq("account_id", account_id).execute()
    already_analyzed = {row["drive_file_id"] for row in (existing.data or [])}

    analyzed_count = 0
    for f in image_files:
        file_id = f["id"]
        if file_id in already_analyzed:
            continue
        image_bytes = connector.download_file_bytes(file_id)
        if not image_bytes:
            continue
        import asyncio
        analysis = asyncio.run(analyze_image_vision(image_bytes, f.get("mimeType", "image/jpeg")))
        supabase.table("visual_analyses").insert({
            "account_id": account_id,
            "drive_file_id": file_id,
            "file_name": f.get("name"),
            "gemini_description": analysis,
            "suggested_caption": analysis.get("suggested_caption"),
        }).execute()
        analyzed_count += 1

    if analyzed_count:
        logger.info(f"Drive webhook fast-path: analyzed {analyzed_count} new image(s) for account {account_id}")
    return analyzed_count
