"""
PySide6 Thread Workers for YouTube Authentication and Upload
"""

import logging
from typing import Optional, List, Dict, Any

from PySide6.QtCore import QThread, Signal
from google.oauth2.credentials import Credentials

from .auth import YouTubeAuth
from .uploader import YouTubeUploader

logger = logging.getLogger(__name__)


class YouTubeAuthThread(QThread):
    """Worker thread for authenticating YouTube via browser OAuth."""

    auth_started = Signal(str)
    finished = Signal(bool, dict, str)

    def __init__(self, client_secret_file: Optional[str] = None, token_path: Optional[str] = None):
        super().__init__()
        self.client_secret_file = client_secret_file
        self.token_path = token_path
        self.yt_auth = YouTubeAuth(token_path=token_path, client_secret_path=client_secret_file)

    def run(self):
        try:
            self.auth_started.emit("Membuka browser untuk otorisasi Google YouTube...")
            creds = self.yt_auth.authenticate_via_browser(self.client_secret_file)
            if creds:
                info = self.yt_auth.get_channel_info(creds) or {}
                self.finished.emit(True, info, "Login YouTube berhasil!")
            else:
                self.finished.emit(False, {}, "Otorisasi dibatalkan atau gagal.")
        except Exception as e:
            logger.error(f"YouTubeAuthThread error: {e}")
            self.finished.emit(False, {}, str(e))


class YouTubeCheckThread(QThread):
    """Worker thread to check saved credentials and load channel info on startup."""

    finished = Signal(bool, dict)

    def __init__(self, token_path: Optional[str] = None):
        super().__init__()
        self.yt_auth = YouTubeAuth(token_path=token_path)

    def run(self):
        try:
            creds = self.yt_auth.get_valid_credentials()
            if creds:
                info = self.yt_auth.get_channel_info(creds) or {}
                self.finished.emit(True, info)
            else:
                self.finished.emit(False, {})
        except Exception as e:
            logger.error(f"YouTubeCheckThread error: {e}")
            self.finished.emit(False, {})


class YouTubeUploadThread(QThread):
    """Worker thread for uploading video to YouTube in background."""

    progress = Signal(float, str)
    log_message = Signal(str)
    finished = Signal(bool, dict, str)

    def __init__(
        self,
        creds: Credentials,
        file_path: str,
        title: str = "",
        description: str = "",
        tags: Optional[List[str]] = None,
        category_id: str = "22",
        privacy_status: str = "unlisted",
    ):
        super().__init__()
        self.creds = creds
        self.file_path = file_path
        self.title = title
        self.description = description
        self.tags = tags or []
        self.category_id = category_id
        self.privacy_status = privacy_status
        self._is_canceled = False

    def cancel(self):
        self._is_canceled = True

    def run(self):
        try:
            self.log_message.emit(f"[YOUTUBE] Memulai pengunggahan: {self.file_path}")
            result = YouTubeUploader.upload_video(
                creds=self.creds,
                file_path=self.file_path,
                title=self.title,
                description=self.description,
                tags=self.tags,
                category_id=self.category_id,
                privacy_status=self.privacy_status,
                progress_callback=self._on_progress,
                cancel_check=lambda: self._is_canceled,
            )

            if result.get("success"):
                url = result.get("url", "")
                self.log_message.emit(f"[YOUTUBE] ✓ Video berhasil diunggah! Link: {url}")
                self.finished.emit(True, result, "")
            else:
                err = result.get("error", "Gagal mengunggah video.")
                self.log_message.emit(f"[YOUTUBE ERROR] ✗ Upload gagal: {err}")
                self.finished.emit(False, result, err)

        except Exception as e:
            err_msg = str(e)
            logger.error(f"YouTubeUploadThread error: {e}")
            self.log_message.emit(f"[YOUTUBE ERROR] Exception: {err_msg}")
            self.finished.emit(False, {}, err_msg)

    def _on_progress(self, pct: float, msg: str):
        self.progress.emit(pct, msg)
        self.log_message.emit(f"[YOUTUBE] {msg}")
