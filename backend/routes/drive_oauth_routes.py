import os
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse

from auth.dependencies import get_current_user, get_current_user_from_query_token
from models.schemas import DriveToken, User
from utils.oauth_state import generate_state_token, verify_state_token

from config import FRONTEND_URL

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/drive", tags=["Drive OAuth"])

_FRONTEND_URL = FRONTEND_URL


@router.get("/auth")
async def drive_auth(
    token: str,
    account_id: Optional[int] = None,
    current_user: User = Depends(get_current_user_from_query_token)
):
    """Redirects user to Google OAuth consent screen."""
    from services.drive_oauth_service import DriveOAuthService
    try:
        flow = DriveOAuthService().build_flow()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    auth_url, _ = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        state=generate_state_token(current_user.id),
        prompt='consent',
    )
    return RedirectResponse(url=auth_url)


@router.get("/callback/google")
async def google_callback(code: str, state: str):
    """Exchanges OAuth code for credentials and stores them in DB."""
    from services.drive_oauth_service import DriveOAuthService
    try:
        user_id = verify_state_token(state)
    except ValueError:
        raise HTTPException(status_code=400, detail="Parámetro state inválido o expirado.")
    try:
        svc = DriveOAuthService()
        flow = svc.build_flow()
        flow.fetch_token(code=code)
        svc.save_credentials(user_id, flow.credentials)
    except Exception as e:
        logger.error(f"Drive OAuth callback error for user {user_id}: {e}")
        raise HTTPException(status_code=400, detail=f"Error en autenticación de Google Drive: {str(e)}")

    return RedirectResponse(url=f"{_FRONTEND_URL}/settings?drive_connected=true")


@router.get("/status", response_model=DriveToken)
async def drive_status(current_user: User = Depends(get_current_user)):
    """Returns Google Drive connection status for the current user.

    Actually attempts to refresh the token (via get_credentials) instead of just
    checking that a drive_tokens row exists, so a revoked/expired refresh token
    is reported as disconnected rather than showing a stale 'connected' badge."""
    from services.drive_oauth_service import DriveOAuthService
    svc = DriveOAuthService()
    creds = svc.get_credentials(str(current_user.id))

    if not creds:
        return DriveToken(user_id=current_user.id, connected=False, scopes=None, connected_at=None)

    try:
        res = svc._supabase.table('drive_tokens').select('scopes, created_at').eq('user_id', current_user.id).execute()
        row = res.data[0] if res.data else {}
        return DriveToken(
            user_id=current_user.id,
            connected=True,
            scopes=row.get('scopes'),
            connected_at=row.get('created_at'),
        )
    except Exception:
        return DriveToken(user_id=current_user.id, connected=True, scopes=None, connected_at=None)


@router.delete("/auth", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_drive(current_user: User = Depends(get_current_user)):
    """Deletes the current user's Drive credentials."""
    from services.drive_oauth_service import DriveOAuthService
    DriveOAuthService().delete_credentials(str(current_user.id))
