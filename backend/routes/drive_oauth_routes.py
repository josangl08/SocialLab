import os
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse

from auth.dependencies import get_current_user, get_current_user_from_query_token
from models.schemas import DriveToken, User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/drive", tags=["Drive OAuth"])

_FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:5173')


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
        state=current_user.id,
        prompt='consent',
    )
    return RedirectResponse(url=auth_url)


@router.get("/callback/google")
async def google_callback(code: str, state: str):
    """Exchanges OAuth code for credentials and stores them in DB."""
    from services.drive_oauth_service import DriveOAuthService
    user_id = state
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
    """Returns Google Drive connection status for the current user."""
    from services.drive_oauth_service import DriveOAuthService
    svc = DriveOAuthService()
    connected = svc.has_credentials(str(current_user.id))

    if not connected:
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
