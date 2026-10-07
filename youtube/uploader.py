"""
YouTube Video Uploader Helper
"""

import os
import logging
from pathlib import Path
from typing import Optional, List, Callable, Dict, Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

# Standard YouTube Categories
YOUTUBE_CATEGORIES = {
    "22": "People & Blogs",
    "24": "Entertainment",
    "27": "Education",
    "20": "Gaming",
    "10": "Music",
    "28": "Science & Technology",
    "1": "Film & Animation",
    "17": "Sports",
    "23": "Comedy",
    "25": "News & Politics",
    "26": "Howto & Style",
}


class YouTubeUploader:
    """Handles uploading videos to YouTube via YouTube Data API v3."""

    @staticmethod
    def upload_video(
        creds: Credentials,
        file_path: str,
        title: str = "",
        description: str = "",
        tags: Optional[List[str]] = None,
        category_id: str = "22",
        privacy_status: str = "unlisted",
        progress_callback: Optional[Callable[[float, str], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> Dict[str, Any]:
        """
        Uploads a video file to YouTube.

        Returns dict:
        {
            "success": bool,
            "video_id": str,
            "url": str,
            "error": str
        }
        """
        p = Path(file_path)
        if not p.exists():
            raise FileNotFoundError(f"File video tidak ditemukan: {file_path}")

        if not title:
            title = p.stem.replace("_", " ").title()

        if not tags:
            tags = []

        if privacy_status not in ["private", "unlisted", "public"]:
            privacy_status = "unlisted"

        body = {
            "snippet": {
                "title": title[:100],  # Max 100 chars
                "description": description[:5000],  # Max 5000 chars
                "tags": tags,
                "categoryId": category_id,
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False,
            },
        }

        try:
            youtube = build("youtube", "v3", credentials=creds)

            # 4MB chunks for upload
            media = MediaFileUpload(
                str(p),
                chunksize=4 * 1024 * 1024,
                resumable=True,
                mimetype="video/*",
            )

            request = youtube.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media,
            )

            if progress_callback:
                progress_callback(0.05, f"Memulai upload video ke YouTube ({privacy_status})...")

            response = None
            while response is None:
                if cancel_check and cancel_check():
                    logger.info("Upload YouTube dibatalkan oleh pengguna.")
                    return {
                        "success": False,
                        "video_id": "",
                        "url": "",
                        "error": "Upload dibatalkan oleh pengguna.",
                    }

                status, response = request.next_chunk()
                if status:
                    pct = status.progress()
                    if progress_callback:
                        progress_callback(pct, f"Mengunggah ke YouTube: {int(pct * 100)}%")

            video_id = response.get("id", "")
            video_url = f"https://youtu.be/{video_id}"

            if progress_callback:
                progress_callback(1.0, f"Upload selesai! URL: {video_url}")

            return {
                "success": True,
                "video_id": video_id,
                "url": video_url,
                "error": "",
            }

        except HttpError as e:
            err_msg = f"HTTP Error {e.resp.status}: {e.content.decode('utf-8')}"
            logger.error(f"YouTube Upload HttpError: {err_msg}")
            return {
                "success": False,
                "video_id": "",
                "url": "",
                "error": err_msg,
            }
        except Exception as e:
            err_msg = str(e)
            logger.error(f"YouTube Upload Error: {err_msg}")
            return {
                "success": False,
                "video_id": "",
                "url": "",
                "error": err_msg,
            }
