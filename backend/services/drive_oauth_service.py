import os
import re
import logging
from datetime import datetime, timezone
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

from database.supabase_client import get_supabase_admin_client

logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/drive']
_DEFAULT_REDIRECT_URI = 'http://localhost:8000/api/drive/callback/google'


class DriveOAuthService:
    def __init__(self):
        self._supabase = get_supabase_admin_client()

    def build_flow(self) -> Flow:
        redirect_uri = os.getenv('GOOGLE_REDIRECT_URI', _DEFAULT_REDIRECT_URI)
        client_id = os.getenv('GOOGLE_CLIENT_ID')
        client_secret = os.getenv('GOOGLE_CLIENT_SECRET')

        if client_id and client_secret:
            client_config = {
                "web": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [redirect_uri],
                }
            }
            flow = Flow.from_client_config(client_config, scopes=SCOPES)
        elif os.path.exists('credentials.json'):
            flow = Flow.from_client_secrets_file('credentials.json', scopes=SCOPES)
        else:
            raise ValueError("Client credentials not configured")

        flow.redirect_uri = redirect_uri
        return flow

    def get_credentials(self, user_id: str) -> Optional[Credentials]:
        res = self._supabase.table('drive_tokens').select('*').eq('user_id', user_id).execute()
        if not res.data:
            return None

        row = res.data[0]

        expiry = None
        if row.get('token_expiry'):
            raw = str(row['token_expiry'])
            s = raw.replace('Z', '+00:00')
            s = re.sub(r'\.(\d+)', lambda m: '.' + m.group(1)[:6].ljust(6, '0'), s)
            parsed = datetime.fromisoformat(s)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            # google-auth compares expiry with datetime.utcnow() (naive), so strip tzinfo
            expiry = parsed.astimezone(timezone.utc).replace(tzinfo=None)

        creds = Credentials(
            token=row['access_token'],
            refresh_token=row['refresh_token'],
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.getenv('GOOGLE_CLIENT_ID'),
            client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
            scopes=row.get('scopes') or SCOPES,
            expiry=expiry,
        )

        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                self.save_credentials(user_id, creds)
            except Exception as e:
                logger.error(f"Error refreshing Drive token for user {user_id}: {e}")
                return None

        return creds

    def save_credentials(self, user_id: str, creds: Credentials) -> None:
        expiry_iso = (
            creds.expiry.astimezone(timezone.utc).isoformat()
            if creds.expiry
            else datetime.now(timezone.utc).isoformat()
        )
        self._supabase.table('drive_tokens').upsert({
            'user_id': user_id,
            'access_token': creds.token,
            'refresh_token': creds.refresh_token,
            'token_expiry': expiry_iso,
            'scopes': list(creds.scopes) if creds.scopes else SCOPES,
            'updated_at': datetime.now(timezone.utc).isoformat(),
        }).execute()

    def delete_credentials(self, user_id: str) -> None:
        self._supabase.table('drive_tokens').delete().eq('user_id', user_id).execute()

    def has_credentials(self, user_id: str) -> bool:
        res = self._supabase.table('drive_tokens').select('user_id').eq('user_id', user_id).execute()
        return bool(res.data)
