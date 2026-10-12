"""
Google Drive Connector Service
Conecta con Google Drive para:
- Sincronizar exports de PROJECT 1 (datos + imágenes)
- Leer/escribir templates
- Monitorear cambios automáticamente
"""

import io
import json
import logging
import re
import threading
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from google.auth.transport.requests import AuthorizedSession
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

logger = logging.getLogger(__name__)

_DRIVE_FILES_URL = "https://www.googleapis.com/drive/v3/files"


class GoogleDriveConnector:
    """Servicio para conectar y sincronizar con Google Drive."""

    def __init__(self):
        self.service = None
        self.credentials = None

    def list_files(
        self,
        folder_id: Optional[str] = None,
        mime_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        query_parts = []
        if folder_id:
            query_parts.append(f"'{folder_id}' in parents")
        if mime_type:
            query_parts.append(f"mimeType='{mime_type}'")
        query_parts.append("trashed=false")
        query = " and ".join(query_parts)

        try:
            results = self.service.files().list(
                q=query,
                pageSize=limit,
                fields="files(id, name, mimeType, size, createdTime, "
                       "modifiedTime, webViewLink, webContentLink)"
            ).execute()
            return results.get('files', [])
        except Exception as e:
            logger.error(f"Error listando archivos: {str(e)}")
            return []

    def download_file(self, file_id: str, destination_path: str) -> bool:
        try:
            request = self.service.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            with open(destination_path, 'wb') as f:
                f.write(fh.getvalue())
            return True
        except Exception as e:
            logger.error(f"Error descargando archivo: {str(e)}")
            return False

    def download_file_bytes(self, file_id: str) -> Optional[bytes]:
        try:
            request = self.service.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            return fh.getvalue()
        except Exception as e:
            logger.error(f"Error descargando archivo en memoria: {str(e)}")
            return None


    def download_metadata_json(
        self,
        folder_id: str,
        filename: str = "metadata.json"
    ) -> Optional[Dict]:
        try:
            query = (
                f"'{folder_id}' in parents and "
                f"name='{filename}' and "
                f"trashed=false"
            )
            results = self.service.files().list(
                q=query, pageSize=1, fields="files(id, name)"
            ).execute()
            files = results.get('files', [])
            if not files:
                logger.warning(f"{filename} no encontrado en carpeta")
                return None

            request = self.service.files().get_media(fileId=files[0]['id'])
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            return json.loads(fh.getvalue().decode('utf-8'))
        except Exception as e:
            logger.error(f"Error descargando metadata: {str(e)}")
            return None

    def list_project1_exports(self, project1_folder_id: str) -> List[Dict]:
        try:
            query = (
                f"'{project1_folder_id}' in parents and "
                f"mimeType='application/vnd.google-apps.folder' and "
                f"trashed=false"
            )
            results = self.service.files().list(
                q=query,
                pageSize=100,
                orderBy="modifiedTime desc",
                fields="files(id, name, createdTime, modifiedTime)"
            ).execute()

            exports = []
            for folder in results.get('files', []):
                metadata = self.download_metadata_json(folder['id'])
                exports.append({
                    'folder_id': folder['id'],
                    'folder_name': folder['name'],
                    'created_at': folder['createdTime'],
                    'modified_at': folder['modifiedTime'],
                    'metadata': metadata,
                    'has_metadata': metadata is not None
                })
            return exports
        except Exception as e:
            logger.error(f"Error listando exports: {str(e)}")
            return []

    def list_generic_resources(self, folder_id: str, already_processed_ids: set) -> list:
        """Returns image/video files from a Drive folder, excluding already-processed IDs."""
        try:
            query = (
                f"'{folder_id}' in parents and "
                f"(mimeType contains 'image/' or mimeType contains 'video/') and "
                f"trashed=false"
            )
            results = self.service.files().list(
                q=query,
                pageSize=100,
                fields="files(id, name, mimeType, webContentLink)"
            ).execute()
            files = results.get('files', [])
            return [f for f in files if f['id'] not in already_processed_ids]
        except Exception as e:
            logger.error(f"Error listing generic resources: {str(e)}")
            return []

    def archive_to_published(self, drive_file_id: str, parent_folder_id: str) -> bool:
        """Moves a file to a 'published' subfolder inside parent_folder_id."""
        try:
            query = (
                f"'{parent_folder_id}' in parents and "
                f"name='published' and "
                f"mimeType='application/vnd.google-apps.folder' and "
                f"trashed=false"
            )
            result = self.service.files().list(q=query, pageSize=1, fields="files(id)").execute()
            folders = result.get('files', [])
            if folders:
                published_id = folders[0]['id']
            else:
                created = self.service.files().create(body={
                    'name': 'published',
                    'mimeType': 'application/vnd.google-apps.folder',
                    'parents': [parent_folder_id]
                }, fields='id').execute()
                published_id = created['id']

            self.service.files().update(
                fileId=drive_file_id,
                addParents=published_id,
                removeParents=parent_folder_id,
                fields='id, parents'
            ).execute()
            logger.info(f"Archived Drive file {drive_file_id} to /published/")
            return True
        except Exception as e:
            logger.error(f"Error archiving Drive file {drive_file_id}: {str(e)}")
            return False

    def _session(self) -> AuthorizedSession:
        # Una sesión por llamada: httplib2 (self.service) no es seguro entre hilos y estas
        # descargas se ejecutan en asyncio.to_thread
        return AuthorizedSession(self.credentials)

    def get_image_bytes(self, file_id: str) -> Tuple[bytes, str]:
        """Original del archivo y su mimeType. Lanza excepción si Drive falla."""
        session = self._session()
        meta = session.get(f"{_DRIVE_FILES_URL}/{file_id}", params={"fields": "mimeType"}, timeout=30)
        meta.raise_for_status()
        media = session.get(f"{_DRIVE_FILES_URL}/{file_id}", params={"alt": "media"}, timeout=60)
        media.raise_for_status()
        return media.content, meta.json().get("mimeType", "image/jpeg")

    def get_thumbnail_bytes(self, file_id: str, size: int) -> Optional[bytes]:
        """Miniatura de Google (lado mayor = size). None si Drive no genera miniatura."""
        session = self._session()
        meta = session.get(f"{_DRIVE_FILES_URL}/{file_id}", params={"fields": "thumbnailLink"}, timeout=30)
        meta.raise_for_status()
        link = meta.json().get("thumbnailLink")
        if not link:
            return None
        link = re.sub(r"=s\d+$", f"=s{size}", link) if re.search(r"=s\d+$", link) else f"{link}=s{size}"
        thumb = session.get(link, timeout=30)
        thumb.raise_for_status()
        return thumb.content

    def get_file_direct_url(self, file_id: str) -> str:
        return f"https://drive.google.com/uc?export=download&id={file_id}"

    def watch_folder(self, folder_id: str, webhook_url: str, channel_id: str, token: str) -> Optional[Dict]:
        """Registers a Drive Push Notification channel for a folder. Returns the
        full channel dict (id, resourceId, expiration) needed to later renew or
        stop the channel — a bare channel id isn't enough for either operation."""
        try:
            body = {
                'id': channel_id,
                'type': 'web_hook',
                'address': webhook_url,
                'token': token,
            }
            response = self.service.files().watch(fileId=folder_id, body=body).execute()
            return {
                'channel_id': response.get('id'),
                'resource_id': response.get('resourceId'),
                'expiration': response.get('expiration'),
            }
        except Exception as e:
            logger.error(f"Error configurando webhook: {str(e)}")
            return None

    def stop_channel(self, channel_id: str, resource_id: str) -> bool:
        try:
            self.service.channels().stop(body={'id': channel_id, 'resourceId': resource_id}).execute()
            return True
        except Exception as e:
            logger.error(f"Error deteniendo canal de Drive {channel_id}: {str(e)}")
            return False


# Credenciales por usuario reutilizadas hasta que caducan: evita leer y descifrar el token
# en cada llamada. Se cachean las credenciales y no el conector porque el cliente httplib2
# de self.service no es seguro entre hilos.
_credentials: Dict[str, Credentials] = {}
_credentials_lock = threading.Lock()


def get_drive_connector(user_id: str) -> GoogleDriveConnector:
    """Creates a per-user Drive connector. Raises RuntimeError if no credentials found."""
    with _credentials_lock:
        creds = _credentials.get(user_id)
    if not creds or not creds.valid:
        from services.drive_oauth_service import DriveOAuthService
        creds = DriveOAuthService().get_credentials(user_id)
        if not creds:
            raise RuntimeError(f"No Drive credentials for user {user_id}")
        with _credentials_lock:
            _credentials[user_id] = creds
    connector = GoogleDriveConnector()
    connector.credentials = creds
    connector.service = build('drive', 'v3', credentials=creds)
    return connector


def forget_drive_credentials(user_id: str) -> None:
    """Descarta las credenciales cacheadas (al desconectar o reconectar Drive)."""
    with _credentials_lock:
        _credentials.pop(user_id, None)
