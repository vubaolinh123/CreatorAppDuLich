"""
Google Drive Uploader — Uploads rendered videos and images to Google Drive.
Uses resumable upload for large files.
"""

import os
import json
from pathlib import Path
from typing import Optional
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
BASE_FOLDER_NAME = "DuLichApp"


class DriveUploader:
    def __init__(self, token_path: str = "token.json"):
        self.token_path = token_path
        self.service = None
        self.base_folder_id: Optional[str] = None

    def _get_service(self):
        if not self.service:
            creds = self._get_credentials()
            if creds:
                self.service = build("drive", "v3", credentials=creds)
        return self.service

    def _get_credentials(self) -> Optional[Credentials]:
        try:
            creds = None
            if os.path.exists(self.token_path):
                creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    return None
            return creds
        except Exception:
            return None

    def _get_or_create_base_folder(self) -> str:
        service = self._get_service()
        if not service:
            return ""

        if self.base_folder_id:
            return self.base_folder_id

        query = f"name='{BASE_FOLDER_NAME}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        results = service.files().list(q=query, fields="files(id)").execute()
        folders = results.get("files", [])

        if folders:
            self.base_folder_id = folders[0]["id"]
        else:
            folder_metadata = {
                "name": BASE_FOLDER_NAME,
                "mimeType": "application/vnd.google-apps.folder",
            }
            folder = service.files().create(body=folder_metadata, fields="id").execute()
            self.base_folder_id = folder.get("id")

        return self.base_folder_id or ""

    def create_subfolder(self, name: str) -> str:
        service = self._get_service()
        if not service:
            return ""
        base_id = self._get_or_create_base_folder()

        folder_metadata = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [base_id],
        }
        folder = service.files().create(body=folder_metadata, fields="id").execute()
        return folder.get("id", "")

    def upload_file(self, local_path: str, folder_id: str, file_name: Optional[str] = None) -> dict:
        service = self._get_service()
        if not service:
            return {}

        file_name = file_name or Path(local_path).name
        file_metadata = {"name": file_name, "parents": [folder_id]}

        media = MediaFileUpload(local_path, resumable=True)
        file = (
            service.files()
            .create(body=file_metadata, media_body=media, fields="id, name, webViewLink")
            .execute()
        )

        return {
            "id": file.get("id"),
            "name": file.get("name"),
            "webViewLink": file.get("webViewLink"),
        }
