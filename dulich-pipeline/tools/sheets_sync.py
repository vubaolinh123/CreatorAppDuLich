"""
Google Sheets Sync — Reads/writes content data to central Google Sheet.
Used as the sync hub between desktop apps and dashboard.
"""

import os
import os
import json
from typing import List, Optional
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class SheetsSync:
    def __init__(self, sheet_id: str, token_path: str = "token.json"):
        self.sheet_id = sheet_id
        self.token_path = token_path
        self.service = None

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

    def _get_service(self):
        if not self.service:
            creds = self._get_credentials()
            if creds:
                self.service = build("sheets", "v4", credentials=creds)
        return self.service

    def read_sheet(self, sheet_name: str, range: str = "A:Z") -> List[List[str]]:
        service = self._get_service()
        if not service:
            return []
        result = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=self.sheet_id, range=f"{sheet_name}!{range}")
            .execute()
        )
        return result.get("values", [])

    def append_row(self, sheet_name: str, row: List[str]) -> bool:
        service = self._get_service()
        if not service:
            return False
        service.spreadsheets().values().append(
            spreadsheetId=self.sheet_id,
            range=f"{sheet_name}!A:Z",
            valueInputOption="USER_ENTERED",
            body={"values": [row]},
        ).execute()
        return True

    def update_cell(self, sheet_name: str, cell: str, value: str) -> bool:
        service = self._get_service()
        if not service:
            return False
        service.spreadsheets().values().update(
            spreadsheetId=self.sheet_id,
            range=f"{sheet_name}!{cell}",
            valueInputOption="USER_ENTERED",
            body={"values": [[value]]},
        ).execute()
        return True

    def add_video(self, row: List[str]) -> bool:
        return self.append_row("Videos", row)

    def add_album(self, row: List[str]) -> bool:
        return self.append_row("Albums", row)

    def get_queue(self) -> List[dict]:
        rows = self.read_sheet("Queue")
        if not rows:
            return []
        headers = rows[0]
        return [dict(zip(headers, row)) for row in rows[1:]]
