"""
Unit tests for YouTube module integration
"""

import sys
import unittest
from pathlib import Path
from PySide6.QtWidgets import QApplication

# Ensure ROOT_DIR in path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from youtube import YouTubeAuth, YouTubeUploader
from youtube.uploader import YOUTUBE_CATEGORIES
from ui.main_window import MainWindow

app = QApplication.instance() or QApplication(sys.argv)


class TestYouTubeIntegration(unittest.TestCase):

    def test_youtube_categories(self):
        self.assertIn("22", YOUTUBE_CATEGORIES)
        self.assertEqual(YOUTUBE_CATEGORIES["22"], "People & Blogs")

    def test_youtube_auth_init(self):
        yt_auth = YouTubeAuth()
        self.assertFalse(yt_auth.is_logged_in())

    def test_main_window_youtube_components(self):
        window = MainWindow()
        self.assertTrue(hasattr(window, "_yt_login_btn"))
        self.assertTrue(hasattr(window, "_yt_logout_btn"))
        self.assertTrue(hasattr(window, "_yt_auto_upload_check"))
        self.assertTrue(hasattr(window, "_yt_privacy_combo"))
        self.assertTrue(hasattr(window, "_yt_category_combo"))
        self.assertTrue(hasattr(window, "_yt_manual_upload_btn"))

        # Verify default states
        self.assertFalse(window._yt_auto_upload_check.isChecked())
        self.assertEqual(window._yt_privacy_combo.currentText(), "unlisted")


if __name__ == "__main__":
    unittest.main()
