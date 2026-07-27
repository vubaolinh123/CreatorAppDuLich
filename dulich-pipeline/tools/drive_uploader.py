"""
Google Drive Uploader — Uploads rendered videos and images to Google Drive.
Supports both Service Account and OAuth2 authentication.
"""

import os
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent

try:
    from google.oauth2 import service_account
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False
    print("[DriveUploader] google-api-python-client not installed. Run: pip install google-api-python-client google-auth", file=sys.stderr)

# Load env
try:
    from dotenv import load_dotenv

    env_file = Path(
        os.getenv("PIPELINE_ENV_PATH") or (ROOT / ".env")
    ).resolve()
    if env_file.exists():
        load_dotenv(env_file)
except Exception:
    pass

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
BASE_FOLDER_NAME = "DuLichApp"


class DriveUploader:
    def __init__(self, service_account_path: str = "", token_path: str = "token.json"):
        self.service_account_path = service_account_path or os.getenv("GOOGLE_SERVICE_ACCOUNT_PATH", "credentials.json")
        self.token_path = token_path
        self.service = None
        self.auth_mode = ""
        self.requested_auth_mode = (
            os.getenv("GOOGLE_DRIVE_AUTH_MODE", "auto").strip().lower() or "auto"
        )
        self.base_folder_id: Optional[str] = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")
        self.shared_drive_id: str = os.getenv("GOOGLE_DRIVE_SHARED_DRIVE_ID", "").strip()
        self.make_public = (
            os.getenv("GOOGLE_DRIVE_MAKE_PUBLIC", "0").strip().lower()
            in {"1", "true", "yes"}
        )

    def _get_service(self):
        """Get Google Drive service with authentication."""
        if not GOOGLE_AVAILABLE:
            print("[DriveUploader] Google libraries not available", file=sys.stderr)
            return None
            
        if self.service:
            return self.service

        if self.requested_auth_mode not in {"auto", "oauth", "service_account"}:
            print(
                f"[DriveUploader] Invalid GOOGLE_DRIVE_AUTH_MODE="
                f"{self.requested_auth_mode!r}",
                file=sys.stderr,
            )
            return None

        def oauth_service():
            if not self.token_path or not os.path.exists(self.token_path):
                return None
            try:
                creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                    Path(self.token_path).write_text(creds.to_json(), encoding="utf-8")
                if creds and creds.valid:
                    service = build("drive", "v3", credentials=creds)
                    self.auth_mode = "oauth"
                    print(f"[DriveUploader] ✓ Connected via OAuth2: {self.token_path}", file=sys.stderr)
                    return service
            except Exception as e:
                print(f"[DriveUploader] OAuth2 error: {e}", file=sys.stderr)
            return None

        def service_account_service():
            if not self.service_account_path or not os.path.exists(self.service_account_path):
                return None
            try:
                creds = service_account.Credentials.from_service_account_file(
                    self.service_account_path, scopes=SCOPES
                )
                service = build("drive", "v3", credentials=creds)
                self.auth_mode = "service_account"
                print(f"[DriveUploader] ✓ Connected via Service Account: {self.service_account_path}", file=sys.stderr)
                return service
            except Exception as e:
                print(f"[DriveUploader] Service Account error: {e}", file=sys.stderr)
            return None

        if self.requested_auth_mode == "oauth":
            self.service = oauth_service()
        elif self.requested_auth_mode == "service_account":
            self.service = service_account_service()
        else:
            # A specifically configured service-account path takes precedence;
            # otherwise preserve the existing OAuth-first behavior.
            configured_sa = bool(os.getenv("GOOGLE_SERVICE_ACCOUNT_PATH", "").strip())
            candidates = (
                (service_account_service, oauth_service)
                if configured_sa
                else (oauth_service, service_account_service)
            )
            for candidate in candidates:
                self.service = candidate()
                if self.service:
                    break

        if not self.service:
            print("[DriveUploader] ⚠ No valid credentials found. Upload will fail.", file=sys.stderr)
        return self.service

    def _get_or_create_base_folder(self) -> str:
        """Get or create the base DuLichApp folder."""
        # Use configured folder ID if provided
        if self.base_folder_id:
            return self.base_folder_id

        service = self._get_service()
        if not service:
            return ""
        if self.auth_mode == "service_account":
            print(
                "[DriveUploader] Service Account cần GOOGLE_DRIVE_FOLDER_ID "
                "trong Shared Drive hoặc folder đã chia sẻ.",
                file=sys.stderr,
            )
            return ""

        # Search for existing folder
        query = f"name='{BASE_FOLDER_NAME}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        params = {"q": query, "fields": "files(id)", "supportsAllDrives": True}
        if self.shared_drive_id:
            params.update(
                {
                    "corpora": "drive",
                    "driveId": self.shared_drive_id,
                    "includeItemsFromAllDrives": True,
                }
            )
        results = service.files().list(**params).execute()
        folders = results.get("files", [])

        if folders:
            self.base_folder_id = folders[0]["id"]
        else:
            # Create new folder
            folder_metadata = {
                "name": BASE_FOLDER_NAME,
                "mimeType": "application/vnd.google-apps.folder",
            }
            folder = service.files().create(
                body=folder_metadata,
                fields="id",
                supportsAllDrives=True,
            ).execute()
            self.base_folder_id = folder.get("id")
            print(f"[DriveUploader] ✓ Created base folder: {BASE_FOLDER_NAME}", file=sys.stderr)

        return self.base_folder_id or ""

    def create_subfolder(self, name: str) -> str:
        """Create a subfolder inside the base folder."""
        service = self._get_service()
        if not service:
            return ""
        
        base_id = self._get_or_create_base_folder()
        if not base_id:
            return ""

        folder_metadata = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [base_id],
        }
        folder = service.files().create(
            body=folder_metadata,
            fields="id",
            supportsAllDrives=True,
        ).execute()
        folder_id = folder.get("id", "")
        print(f"[DriveUploader] ✓ Created subfolder: {name}", file=sys.stderr)
        return folder_id

    def upload_file(
        self,
        local_path: str,
        folder_id: str,
        file_name: Optional[str] = None,
        *,
        make_public: Optional[bool] = None,
    ) -> dict:
        """Upload a file to Google Drive."""
        service = self._get_service()
        if not service:
            return {"error": "Google Drive service not available"}

        if not os.path.exists(local_path):
            return {"error": f"File not found: {local_path}"}

        file_name = file_name or Path(local_path).name
        file_size = os.path.getsize(local_path)
        
        file_metadata = {"name": file_name, "parents": [folder_id]}
        media = MediaFileUpload(local_path, resumable=True)

        try:
            file = (
                service.files()
                .create(
                    body=file_metadata,
                    media_body=media,
                    fields="id, name, webViewLink, webContentLink, driveId",
                    supportsAllDrives=True,
                )
                .execute()
            )
            
            file_id = file.get("id")
            should_publish = self.make_public if make_public is None else bool(make_public)
            if should_publish:
                self._make_public(file_id)
            
            result = {
                "id": file_id,
                "name": file.get("name"),
                "webViewLink": file.get("webViewLink"),
                "webContentLink": file.get("webContentLink"),
                "driveId": file.get("driveId"),
                "public": should_publish,
            }
            print(f"[DriveUploader] ✓ Uploaded: {file_name} ({file_size/1024/1024:.1f}MB)", file=sys.stderr)
            return result
            
        except Exception as e:
            print(f"[DriveUploader] Upload error: {e}", file=sys.stderr)
            return {"error": str(e)}

    def _make_public(self, file_id: str):
        """Make a file publicly readable (optional)."""
        try:
            service = self._get_service()
            if service:
                permission = {"type": "anyone", "role": "reader"}
                service.permissions().create(
                    fileId=file_id,
                    body=permission,
                    supportsAllDrives=True,
                ).execute()
        except Exception as e:
            print(f"[DriveUploader] Warning: Could not make public: {e}", file=sys.stderr)

    def upload_video(self, local_path: str, job_id: str = "") -> dict:
        """Upload a video file to Google Drive with proper folder structure."""
        service = self._get_service()
        if not service:
            return {"error": "Google Drive not configured"}

        # Create or get video folder
        folder_name = "Videos"
        if job_id:
            folder_name = f"Videos/{job_id}"
        
        folder_id = self.create_subfolder(folder_name)
        if not folder_id:
            # Fallback to base folder
            folder_id = self._get_or_create_base_folder()
        
        if not folder_id:
            return {"error": "Could not create folder"}

        return self.upload_file(local_path, folder_id)

    def get_file_url(self, file_id: str) -> str:
        """Get a shareable URL for a file."""
        return f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"

    def destination_info(self) -> dict:
        """Verify credentials and configured parent without exposing key material."""
        service = self._get_service()
        if not service:
            return {"ok": False, "error": "Google Drive authentication failed"}
        folder_id = self._get_or_create_base_folder()
        if not folder_id:
            return {
                "ok": False,
                "auth_mode": self.auth_mode,
                "error": "GOOGLE_DRIVE_FOLDER_ID is required or inaccessible",
            }
        try:
            folder = service.files().get(
                fileId=folder_id,
                fields="id,name,mimeType,driveId,capabilities(canAddChildren)",
                supportsAllDrives=True,
            ).execute()
        except Exception as exc:
            return {
                "ok": False,
                "auth_mode": self.auth_mode,
                "error": str(exc),
            }
        can_add = bool((folder.get("capabilities") or {}).get("canAddChildren"))
        return {
            "ok": (
                folder.get("mimeType")
                == "application/vnd.google-apps.folder"
                and can_add
            ),
            "auth_mode": self.auth_mode,
            "folder_id": folder.get("id", ""),
            "folder_name": folder.get("name", ""),
            "shared_drive_id": folder.get("driveId", ""),
            "can_add_children": can_add,
            "make_public": self.make_public,
        }


# Singleton instance
_uploader: Optional[DriveUploader] = None


def get_drive_uploader() -> DriveUploader:
    """Get or create DriveUploader singleton."""
    global _uploader
    if _uploader is None:
        _uploader = DriveUploader()
    return _uploader
