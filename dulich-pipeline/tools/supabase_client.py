"""
supabase_client.py — Supabase client for Python (dulich-pipeline).
Provides functions to interact with Supabase REST API.
"""

import os
import json
import sys
from typing import Optional, Any
from datetime import datetime, timezone

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# Load env
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY", "")

# Fix Windows console encoding
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


class SupabaseClient:
    """Simple Supabase REST API client."""

    def __init__(self, url: str = "", key: str = ""):
        self.url = url or SUPABASE_URL
        self.key = key or SUPABASE_KEY
        self.rest_url = f"{self.url}/rest/v1"
        self.headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    def _request(self, method: str, endpoint: str, data: dict = None, params: dict = None) -> dict:
        """Make a request to Supabase REST API."""
        if not REQUESTS_AVAILABLE:
            print("[Supabase] requests library not installed", file=sys.stderr)
            return {"error": "requests not installed"}

        url = f"{self.rest_url}/{endpoint}"
        try:
            if method == "GET":
                resp = requests.get(url, headers=self.headers, params=params, timeout=30)
            elif method == "POST":
                resp = requests.post(url, headers=self.headers, json=data, timeout=30)
            elif method == "PATCH":
                resp = requests.patch(url, headers=self.headers, json=data, params=params, timeout=30)
            elif method == "DELETE":
                resp = requests.delete(url, headers=self.headers, params=params, timeout=30)
            else:
                return {"error": f"Unknown method: {method}"}

            if resp.status_code >= 400:
                print(f"[Supabase] Error {resp.status_code}: {resp.text[:500]}", file=sys.stderr)
                return {"error": resp.text}

            return resp.json() if resp.text else {}
        except Exception as e:
            print(f"[Supabase] Request error: {e}", file=sys.stderr)
            return {"error": str(e)}

    # ── Users ─────────────────────────────────────────────────────────────────

    def get_user(self, username: str) -> Optional[dict]:
        """Get user by username."""
        result = self._request("GET", "users", params={"username": f"eq.{username}", "select": "*"})
        if isinstance(result, list) and len(result) > 0:
            return result[0]
        return None

    def get_users(self) -> list:
        """Read legacy users for the one-time SQLite migration only."""
        result = self._request("GET", "users", params={"select": "*", "order": "created_at"})
        return result if isinstance(result, list) else []

    # ── Content ───────────────────────────────────────────────────────────────

    def create_content(self, content_data: dict) -> Optional[dict]:
        """Create a new content record."""
        result = self._request("POST", "content", data=content_data)
        if isinstance(result, list) and len(result) > 0:
            return result[0]
        return result

    def get_content(self, content_id: str) -> Optional[dict]:
        """Get content by ID."""
        result = self._request("GET", "content", params={"id": f"eq.{content_id}", "select": "*"})
        if isinstance(result, list) and len(result) > 0:
            return result[0]
        return None

    def get_content_by_job_id(self, job_id: str) -> Optional[dict]:
        """Get content by job_id."""
        result = self._request("GET", "content", params={"job_id": f"eq.{job_id}", "select": "*"})
        if isinstance(result, list) and len(result) > 0:
            return result[0]
        return None

    def get_all_content(self, status: str = None, content_type: str = None) -> list:
        """Get all content with optional filters."""
        params = {"select": "*", "order": "created_at.desc"}
        if status:
            params["status"] = f"eq.{status}"
        if content_type:
            params["content_type"] = f"eq.{content_type}"
        result = self._request("GET", "content", params=params)
        return result if isinstance(result, list) else []

    def get_user_content(self, user_id: str) -> list:
        """Get content for a specific user."""
        result = self._request("GET", "content", params={
            "user_id": f"eq.{user_id}",
            "select": "*",
            "order": "created_at.desc"
        })
        return result if isinstance(result, list) else []

    def update_content(self, content_id: str, update_data: dict) -> Optional[dict]:
        """Update content by ID."""
        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        result = self._request("PATCH", "content", data=update_data, params={"id": f"eq.{content_id}"})
        if isinstance(result, list) and len(result) > 0:
            return result[0]
        return result

    def update_content_status(self, content_id: str, status: str) -> Optional[dict]:
        """Update content status."""
        return self.update_content(content_id, {"status": status})

    # ── Publish Logs ──────────────────────────────────────────────────────────

    def create_publish_log(self, log_data: dict) -> Optional[dict]:
        """Create a publish log entry."""
        result = self._request("POST", "publish_logs", data=log_data)
        if isinstance(result, list) and len(result) > 0:
            return result[0]
        return result

    def get_publish_logs(self, content_id: str) -> list:
        """Get publish logs for content."""
        result = self._request("GET", "publish_logs", params={
            "content_id": f"eq.{content_id}",
            "select": "*",
            "order": "published_at.desc"
        })
        return result if isinstance(result, list) else []


# Singleton instance
_client: Optional[SupabaseClient] = None


def get_supabase() -> SupabaseClient:
    """Get or create Supabase client singleton."""
    global _client
    if _client is None:
        _client = SupabaseClient()
        if not _client.url:
            print("[Supabase] WARNING: SUPABASE_URL not configured", file=sys.stderr)
    return _client
