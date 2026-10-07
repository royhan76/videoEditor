"""
YouTube OAuth Authentication Handler
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]


class YouTubeAuth:
    """Manages YouTube OAuth 2.0 authentication state and tokens."""

    def __init__(self, token_path: Optional[str] = None, client_secret_path: Optional[str] = None):
        self.root_dir = Path(__file__).resolve().parent.parent
        self.token_path = Path(token_path) if token_path else self.root_dir / "config" / "youtube_token.json"
        self.client_secret_path = Path(client_secret_path) if client_secret_path else self.root_dir / "config" / "client_secret.json"

    def get_valid_credentials(self) -> Optional[Credentials]:
        """
        Loads saved credentials if valid or refreshable.
        Returns Credentials object or None.
        """
        if not self.token_path.exists():
            return None

        try:
            creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)
            if creds and creds.valid:
                return creds
            if creds and creds.expired and creds.refresh_token:
                logger.info("Refreshing expired YouTube access token...")
                creds.refresh(Request())
                # Save refreshed token
                self.save_credentials(creds)
                return creds
        except Exception as e:
            logger.error(f"Error loading/refreshing YouTube credentials: {e}")
            return None

        return None

    def is_logged_in(self) -> bool:
        """Returns True if valid credentials exist."""
        return self.get_valid_credentials() is not None

    def save_credentials(self, creds: Credentials):
        """Saves credentials to json file."""
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.token_path, "w", encoding="utf-8") as f:
            f.write(creds.to_json())

    def authenticate_via_browser(self, client_secret_file: Optional[str] = None) -> Credentials:
        """
        Runs browser OAuth flow.
        MUST BE RUN IN BACKGROUND THREAD so main UI thread does not freeze.
        """
        secret_path = Path(client_secret_file) if client_secret_file else self.client_secret_path
        if not secret_path.exists():
            # Check root directory or config/ for client_secret*.json
            candidates = list(self.root_dir.glob("client_secret*.json")) + list((self.root_dir / "config").glob("client_secret*.json"))
            if candidates:
                secret_path = candidates[0]
            else:
                raise FileNotFoundError(
                    f"File OAuth Client Secret ({secret_path.name}) tidak ditemukan!\n"
                    f"Silakan unduh file client_secret.json dari Google Cloud Console dan simpan di folder config/"
                )

        flow = InstalledAppFlow.from_client_secrets_file(str(secret_path), SCOPES)
        # Run local web server on port 0 (free random port)
        creds = flow.run_local_server(
            port=0,
            authorization_prompt_message="Buka tautan ini di browser untuk login YouTube:\n{url}",
            success_message="Login YouTube Berhasil! Anda dapat menutup halaman browser ini."
        )
        self.save_credentials(creds)
        return creds

    def logout(self) -> bool:
        """Deletes token file to logout."""
        try:
            if self.token_path.exists():
                os.remove(self.token_path)
            return True
        except Exception as e:
            logger.error(f"Error logging out YouTube: {e}")
            return False

    def get_channel_info(self, creds: Optional[Credentials] = None) -> Optional[Dict[str, Any]]:
        """
        Fetches channel info (Title, Custom URL, Avatar) for current authenticated user.
        """
        if not creds:
            creds = self.get_valid_credentials()
        if not creds:
            return None

        try:
            youtube = build("youtube", "v3", credentials=creds)
            response = youtube.channels().list(mine=True, part="snippet,contentDetails,statistics").execute()
            items = response.get("items", [])
            if items:
                snippet = items[0].get("snippet", {})
                return {
                    "id": items[0].get("id", ""),
                    "title": snippet.get("title", "Unknown Channel"),
                    "custom_url": snippet.get("customUrl", ""),
                    "thumbnail": snippet.get("thumbnails", {}).get("default", {}).get("url", ""),
                    "subscriber_count": items[0].get("statistics", {}).get("subscriberCount", "0"),
                    "video_count": items[0].get("statistics", {}).get("videoCount", "0"),
                }
        except Exception as e:
            logger.error(f"Failed to fetch YouTube channel info: {e}")

        return None
