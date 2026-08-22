"""
Drive Webhook Routes
Endpoint público que recibe las notificaciones push de Google Drive (Push
Notifications) — sin autenticación de usuario, ya que Google no puede
autenticarse como un usuario nuestro. La autenticación es el channel_token
propio, verificado en drive_webhook_service.handle_notification contra la fila
guardada al registrar el canal.
"""

import logging
from fastapi import APIRouter, BackgroundTasks, Header, Response
from typing import Optional

from services import drive_webhook_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/drive", tags=["Google Drive Webhook"])


@router.post("/webhook")
async def drive_webhook(
    background_tasks: BackgroundTasks,
    x_goog_channel_id: Optional[str] = Header(None),
    x_goog_resource_state: Optional[str] = Header(None),
    x_goog_channel_token: Optional[str] = Header(None),
):
    """
    Google no envía cuerpo en sus notificaciones push — todo viaje en cabeceras.
    Siempre respondemos 200 rápido (Google espera un ack, no procesamiento) y
    delegamos el trabajo real a un background task.
    """
    if x_goog_channel_id and x_goog_resource_state:
        background_tasks.add_task(
            drive_webhook_service.handle_notification,
            x_goog_channel_id,
            x_goog_resource_state,
            x_goog_channel_token or "",
        )
    return Response(status_code=200)
