"""
Servicio de backfill perezoso para enriquecer registros antiguos de visual_analyses
con aesthetic_score y campos visuales estructurados sin sobreescribir datos existentes.
"""

import logging
from typing import Dict, Any
from database.supabase_client import get_supabase_admin_client
from services.google_drive_connector import get_drive_connector
from services.gemini_service import analyze_image_vision

logger = logging.getLogger(__name__)


async def backfill_visual_scores(account_id: int, batch_size: int = 10) -> Dict[str, int]:
    supabase = get_supabase_admin_client()

    ac_res = supabase.table("instagram_accounts").select("user_id").eq("id", account_id).execute()
    user_id = ac_res.data[0].get("user_id") if ac_res.data else None

    res = supabase.table("visual_analyses").select("*").eq("account_id", account_id).execute()
    all_rows = res.data or []

    rows_without_score = [
        r for r in all_rows
        if not (isinstance(r.get("gemini_description"), dict) and "aesthetic_score" in r["gemini_description"])
    ]

    batch = rows_without_score[:batch_size]
    processed = len(batch)
    updated = 0

    if not batch:
        return {
            "processed": 0,
            "updated": 0,
            "remaining_without_score": 0,
        }

    try:
        drive = get_drive_connector(str(user_id)) if user_id else get_drive_connector()
    except Exception as e:
        logger.error(f"No se pudo conectar a Google Drive para cuenta {account_id}: {e}")
        return {
            "processed": processed,
            "updated": 0,
            "remaining_without_score": len(rows_without_score),
        }

    for row in batch:
        drive_file_id = row.get("drive_file_id")
        if not drive_file_id:
            continue
        try:
            image_bytes = drive.download_file_bytes(drive_file_id)
            if not image_bytes:
                logger.warning(f"No se pudieron descargar bytes para {drive_file_id}")
                continue

            new_analysis = await analyze_image_vision(image_bytes, "image/jpeg")
            existing_desc = row.get("gemini_description") or {}

            merged_desc = dict(existing_desc)
            for key in ("aesthetic_score", "composition_type", "content_type_fit", "suggested_hook"):
                if key in new_analysis:
                    merged_desc[key] = new_analysis[key]

            supabase.table("visual_analyses").update({"gemini_description": merged_desc}).eq("drive_file_id", drive_file_id).execute()
            updated += 1
        except Exception as e:
            logger.warning(f"Error procesando fila {drive_file_id} en backfill: {e}")
            continue

    remaining = len(rows_without_score) - updated
    return {
        "processed": processed,
        "updated": updated,
        "remaining_without_score": max(0, remaining),
    }
