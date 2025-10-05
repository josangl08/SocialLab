"""
Google Drive Connector Service
Conecta con Google Drive para:
- Sincronizar exports de PROJECT 1 (datos + imágenes)
- Leer/escribir templates
- Monitorear cambios automáticamente
"""

import os
import json
import pickle
from typing import List, Dict, Optional
from datetime import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io
import logging

logger = logging.getLogger(__name__)

# Scopes necesarios para Google Drive
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']


class GoogleDriveConnector:
    """Servicio para conectar y sincronizar con Google Drive."""

    def __init__(
        self,
        credentials_path: str = "credentials.json",
        token_path: str = "token.pickle",
        oauth_type: str = None
    ):
        """
        Inicializa el conector de Google Drive.

        Args:
            credentials_path: Path al archivo credentials.json
            token_path: Path donde guardar el token de autenticación
            oauth_type: 'desktop' o 'web' (auto-detecta desde env si None)
        """
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.oauth_type = oauth_type or os.getenv('GOOGLE_OAUTH_TYPE', 'desktop')
        self.service = None
        self.creds = None

    def authenticate(self) -> bool:
        """
        Autentica con Google Drive usando OAuth 2.0.

        Returns:
            True si la autenticación fue exitosa
        """
        try:
            # Cargar credenciales guardadas si existen
            if os.path.exists(self.token_path):
                with open(self.token_path, 'rb') as token:
                    self.creds = pickle.load(token)

            # Si no hay credenciales válidas, hacer login
            if not self.creds or not self.creds.valid:
                if self.creds and self.creds.expired and self.creds.refresh_token:
                    self.creds.refresh(Request())
                else:
                    if not os.path.exists(self.credentials_path):
                        logger.error(
                            f"Archivo {self.credentials_path} no encontrado"
                        )
                        logger.info(
                            "Descarga credentials.json desde Google Cloud Console"
                        )
                        return False

                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_path, SCOPES
                    )

                    # Flujo según tipo de OAuth
                    if self.oauth_type == 'web':
                        # Producción: Web App con redirect URI
                        redirect_uri = os.getenv(
                            'GOOGLE_REDIRECT_URI',
                            'http://localhost:8000/callback/google'
                        )
                        flow.redirect_uri = redirect_uri
                        auth_url, _ = flow.authorization_url(prompt='consent')
                        logger.info(f"🔗 Visita esta URL: {auth_url}")
                        # En producción, esto se maneja con endpoint /callback/google
                        return False  # Requiere implementar endpoint
                    else:
                        # Desarrollo: Desktop App (local server)
                        self.creds = flow.run_local_server(port=0)

                # Guardar credenciales para la próxima vez
                with open(self.token_path, 'wb') as token:
                    pickle.dump(self.creds, token)

            # Crear servicio de Drive
            self.service = build('drive', 'v3', credentials=self.creds)
            logger.info("✅ Autenticado con Google Drive exitosamente")
            return True

        except Exception as e:
            logger.error(f"❌ Error en autenticación: {str(e)}")
            return False

    def list_files(
        self,
        folder_id: Optional[str] = None,
        mime_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        Lista archivos en Google Drive.

        Args:
            folder_id: ID de carpeta específica (None = root)
            mime_type: Filtrar por tipo MIME
            limit: Máximo número de archivos a retornar

        Returns:
            Lista de archivos con metadata
        """
        if not self.service:
            if not self.authenticate():
                return []

        try:
            query_parts = []

            if folder_id:
                query_parts.append(f"'{folder_id}' in parents")

            if mime_type:
                query_parts.append(f"mimeType='{mime_type}'")

            query_parts.append("trashed=false")
            query = " and ".join(query_parts)

            results = self.service.files().list(
                q=query,
                pageSize=limit,
                fields="files(id, name, mimeType, size, createdTime, "
                       "modifiedTime, webViewLink, webContentLink)"
            ).execute()

            files = results.get('files', [])
            logger.info(f"📁 Encontrados {len(files)} archivos")
            return files

        except Exception as e:
            logger.error(f"❌ Error listando archivos: {str(e)}")
            return []

    def download_file(
        self,
        file_id: str,
        destination_path: str
    ) -> bool:
        """
        Descarga un archivo de Google Drive.

        Args:
            file_id: ID del archivo en Drive
            destination_path: Path local donde guardar

        Returns:
            True si la descarga fue exitosa
        """
        if not self.service:
            if not self.authenticate():
                return False

        try:
            request = self.service.files().get_media(fileId=file_id)
            fh = io.BytesIO()

            downloader = MediaIoBaseDownload(fh, request)
            done = False

            while not done:
                status, done = downloader.next_chunk()
                logger.info(f"⬇️  Descarga {int(status.progress() * 100)}%")

            # Guardar archivo
            with open(destination_path, 'wb') as f:
                f.write(fh.getvalue())

            logger.info(f"✅ Archivo descargado: {destination_path}")
            return True

        except Exception as e:
            logger.error(f"❌ Error descargando archivo: {str(e)}")
            return False

    def download_metadata_json(
        self,
        folder_id: str,
        filename: str = "metadata.json"
    ) -> Optional[Dict]:
        """
        Descarga y parsea un archivo metadata.json de PROJECT 1.

        Args:
            folder_id: ID de carpeta de PROJECT 1
            filename: Nombre del archivo (default: metadata.json)

        Returns:
            Diccionario con metadata o None
        """
        try:
            # Buscar archivo metadata.json
            query = (
                f"'{folder_id}' in parents and "
                f"name='{filename}' and "
                f"trashed=false"
            )

            results = self.service.files().list(
                q=query,
                pageSize=1,
                fields="files(id, name)"
            ).execute()

            files = results.get('files', [])

            if not files:
                logger.warning(f"⚠️  {filename} no encontrado en carpeta")
                return None

            file_id = files[0]['id']

            # Descargar contenido
            request = self.service.files().get_media(fileId=file_id)
            fh = io.BytesIO()

            downloader = MediaIoBaseDownload(fh, request)
            done = False

            while not done:
                status, done = downloader.next_chunk()

            # Parsear JSON
            content = fh.getvalue().decode('utf-8')
            metadata = json.loads(content)

            logger.info(f"✅ Metadata cargada: {len(metadata)} items")
            return metadata

        except Exception as e:
            logger.error(f"❌ Error descargando metadata: {str(e)}")
            return None

    def list_project1_exports(
        self,
        project1_folder_id: str
    ) -> List[Dict]:
        """
        Lista todos los exports disponibles de PROJECT 1.

        Args:
            project1_folder_id: ID de carpeta raíz de PROJECT 1

        Returns:
            Lista de exports con metadata
        """
        try:
            # Listar subcarpetas (cada export es una carpeta)
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

            folders = results.get('files', [])
            exports = []

            for folder in folders:
                # Buscar metadata.json en cada carpeta
                metadata = self.download_metadata_json(folder['id'])

                export_info = {
                    'folder_id': folder['id'],
                    'folder_name': folder['name'],
                    'created_at': folder['createdTime'],
                    'modified_at': folder['modifiedTime'],
                    'metadata': metadata,
                    'has_metadata': metadata is not None
                }

                exports.append(export_info)

            logger.info(f"📦 Encontrados {len(exports)} exports de PROJECT 1")
            return exports

        except Exception as e:
            logger.error(f"❌ Error listando exports: {str(e)}")
            return []

    def get_file_direct_url(self, file_id: str) -> str:
        """
        Obtiene URL directa de descarga de un archivo.

        Args:
            file_id: ID del archivo en Drive

        Returns:
            URL directa de descarga
        """
        return f"https://drive.google.com/uc?export=download&id={file_id}"

    def watch_folder(
        self,
        folder_id: str,
        webhook_url: str
    ) -> Optional[str]:
        """
        Configura webhook para monitorear cambios en una carpeta.

        Args:
            folder_id: ID de carpeta a monitorear
            webhook_url: URL donde recibir notificaciones

        Returns:
            Channel ID si fue exitoso
        """
        if not self.service:
            if not self.authenticate():
                return None

        try:
            body = {
                'id': f'channel_{datetime.now().timestamp()}',
                'type': 'web_hook',
                'address': webhook_url
            }

            response = self.service.files().watch(
                fileId=folder_id,
                body=body
            ).execute()

            channel_id = response.get('id')
            logger.info(f"✅ Webhook configurado: {channel_id}")
            return channel_id

        except Exception as e:
            logger.error(f"❌ Error configurando webhook: {str(e)}")
            return None


# Instancia global del conector
drive_connector = None


def get_drive_connector() -> GoogleDriveConnector:
    """Obtiene instancia singleton del conector."""
    global drive_connector
    if drive_connector is None:
        drive_connector = GoogleDriveConnector()
        drive_connector.authenticate()
    return drive_connector


# Testing
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    # Test de autenticación
    connector = GoogleDriveConnector()

    if connector.authenticate():
        print("✅ Autenticación exitosa")

        # Listar algunos archivos
        files = connector.list_files(limit=5)
        print(f"\n📁 Primeros 5 archivos:")
        for f in files:
            print(f"  - {f['name']} ({f['mimeType']})")
    else:
        print("❌ Error en autenticación")
        print("Asegúrate de tener credentials.json en el directorio")
