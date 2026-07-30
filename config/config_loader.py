"""
Config Loader
Membaca dan menyediakan akses ke config/config.json
"""

import json
import os
from pathlib import Path


# Root project = folder tempat config_loader.py berada (naik 1 level dari config/)
ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT_DIR / "config" / "config.json"


class ConfigLoader:
    """
    Singleton config loader.
    Memuat config.json sekali, kemudian bisa diakses dari mana saja.
    """

    _instance = None
    _config: dict = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load()
        return cls._instance

    def _load(self):
        if not CONFIG_PATH.exists():
            raise FileNotFoundError(f"Config tidak ditemukan: {CONFIG_PATH}")

        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            self._config = json.load(f)

    def get(self, *keys, default=None):
        """
        Ambil nilai config dengan dot-path.
        Contoh: config.get("audio", "fade_in") → 300
        """
        value = self._config
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return default
            if value is None:
                return default
        return value

    def all(self) -> dict:
        """Kembalikan seluruh config sebagai dict."""
        return self._config

    def reload(self):
        """Reload config dari disk (berguna saat user mengubah config)."""
        self._load()


# ─── Helper shortcut ────────────────────────────────────────────────────────────

def load_config() -> dict:
    """Shortcut: kembalikan seluruh config sebagai dict."""
    return ConfigLoader().all()


def get_config(*keys, default=None):
    """Shortcut: ambil nilai config by key path."""
    return ConfigLoader().get(*keys, default=default)


# ─── Resolve path relatif ke root ───────────────────────────────────────────────

def resolve_path(*relative_parts) -> Path:
    """
    Gabungkan path relatif ke ROOT_DIR.
    Contoh: resolve_path("output") → E:/PROJECT/desktop/videoEditor/output
    """
    return ROOT_DIR.joinpath(*relative_parts)


# ─── Quick-access helpers ────────────────────────────────────────────────────────

def get_output_dir() -> Path:
    return resolve_path(get_config("paths", "output_dir", default="output"))


def get_temp_dir() -> Path:
    return resolve_path(get_config("paths", "temp_dir", default="temp"))


def get_preset_dir() -> Path:
    return resolve_path(get_config("paths", "preset_dir", default="preset"))


def get_edit_plan_dir() -> Path:
    return resolve_path(get_config("paths", "edit_plan_dir", default="edit_plan"))
