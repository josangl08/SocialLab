import os
import uuid
import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel

from database.supabase_client import get_supabase_client, get_supabase_admin_client
from models.schemas import User, TelegramUpdate, TelegramLinkTokenResponse
from auth.dependencies import get_current_user
from services.telegram_service import TelegramService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/telegram", tags=["Telegram Integration"])
supabase = get_supabase_client()
admin_supabase = get_supabase_admin_client()

class LinkAccountRequest(BaseModel):
    link_token: str
    telegram_chat_id: str

@router.post("/webhook/{token}")
async def telegram_webhook(token: str, update: TelegramUpdate):
    """
    Webhook endpoint for Telegram bot updates.
    """
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token or token != bot_token:
        logger.warning("Unauthorized webhook request: token mismatch")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized"
        )

    try:
        telegram_service = TelegramService()
        if update.callback_query:
            await telegram_service.handle_callback_query(update.callback_query)
        elif update.message:
            await telegram_service.handle_message(update.message)
    except Exception as e:
        logger.error(f"Error handling Telegram update: {str(e)}", exc_info=True)
        # Always return 200 to Telegram unless authorization failed
        return {"ok": True}

    return {"ok": True}

@router.post("/generate-link-token", response_model=TelegramLinkTokenResponse)
async def generate_link_token(current_user: User = Depends(get_current_user)):
    """
    Generates a temporary UUID link token for the user's active Instagram account.
    """
    try:
        # Find user's active Instagram account
        response = admin_supabase.table('instagram_accounts')\
            .select('id')\
            .eq('user_id', current_user.id)\
            .eq('is_active', True)\
            .limit(1)\
            .execute()
        
        account_data = response.data
        if not account_data:
            # Fallback to the first account if none is marked active
            response = admin_supabase.table('instagram_accounts')\
                .select('id')\
                .eq('user_id', current_user.id)\
                .limit(1)\
                .execute()
            account_data = response.data

        if not account_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No se encontró ninguna cuenta de Instagram vinculada para este usuario."
            )

        account_id = account_data[0]['id']
        token = str(uuid.uuid4())
        # Token is valid for 10 minutes
        expires_at = datetime.utcnow() + timedelta(minutes=10)

        admin_supabase.table('instagram_accounts')\
            .update({
                'telegram_link_token': token,
                'telegram_link_token_expires_at': expires_at.isoformat()
            })\
            .eq('id', account_id)\
            .execute()

        return TelegramLinkTokenResponse(token=token, expires_at=expires_at)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating link token: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al generar el token de vinculación: {str(e)}"
        )

@router.post("/link-account")
async def link_account(payload: LinkAccountRequest):
    """
    Links a telegram chat ID to an Instagram account using a valid link token.
    Internal endpoint used by the Telegram bot handler.
    """
    try:
        # Find account by link token
        response = admin_supabase.table('instagram_accounts')\
            .select('id, telegram_link_token_expires_at')\
            .eq('telegram_link_token', payload.link_token)\
            .execute()

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Token de vinculación no encontrado o no válido."
            )

        account = response.data[0]
        expires_at_str = account.get('telegram_link_token_expires_at')
        if expires_at_str:
            expires_at = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
            if expires_at < datetime.now(expires_at.tzinfo):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El token de vinculación ha expirado."
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token no válido o sin fecha de expiración."
            )

        # Update the account with the telegram chat ID and clear the token fields
        admin_supabase.table('instagram_accounts')\
            .update({
                'telegram_chat_id': payload.telegram_chat_id,
                'telegram_link_token': None,
                'telegram_link_token_expires_at': None
            })\
            .eq('id', account['id'])\
            .execute()

        return {"success": True, "message": "Cuenta vinculada correctamente."}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error linking account: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al vincular la cuenta: {str(e)}"
        )
