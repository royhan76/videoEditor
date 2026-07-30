"""
Subtitle Preset Loader
- Membaca file .ass preset dari folder preset/
- Build file .ass lengkap dengan events (untuk dikirim ke FFmpeg)
- Menghitung safe margin berdasarkan area crop
"""

import re
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional

from subtitle.extractor import SubtitleEntry
from subtitle.time_utils import ms_to_ass_timestamp


@dataclass
class StyleInfo:
    """Info style yang diekstrak dari file .ass preset."""
    name: str
    raw_line: str       # baris Style: ... aslinya


class PresetLoader:
    """
    Memuat preset .ass dan membangun file .ass lengkap dengan events.

    Alur:
        preset .ass (template) + SubtitleEntry list
            → file .ass lengkap siap pakai FFmpeg
    """

    def __init__(self, preset_dir: str):
        self.preset_dir = Path(preset_dir)
        if not self.preset_dir.exists():
            raise FileNotFoundError(f"Folder preset tidak ditemukan: {preset_dir}")

    # ─── Public API ───────────────────────────────────────────────────────────────

    def available_presets(self) -> List[str]:
        """Kembalikan list nama preset yang tersedia (tanpa ekstensi)."""
        return [f.stem for f in sorted(self.preset_dir.glob("*.ass"))]

    def load_header(self, preset_name: str) -> str:
        """
        Baca bagian header preset (.ass tanpa section [Events]).
        Returns: string header (Script Info + V4+ Styles)
        """
        path = self._resolve(preset_name)
        content = path.read_text(encoding="utf-8-sig")

        # Ambil sampai sebelum [Events]
        events_idx = content.find("[Events]")
        if events_idx == -1:
            return content.strip()
        return content[:events_idx].strip()

    def build_ass(
        self,
        preset_name: str,
        entries: List[SubtitleEntry],
        output_width: int,
        output_height: int,
        margin_v: Optional[int] = None,
        margin_h: Optional[int] = None,
    ) -> str:
        """
        Build file .ass lengkap siap untuk FFmpeg.

        Args:
            preset_name   : nama preset (misal "Modern01")
            entries       : list SubtitleEntry dengan timing RELATIF ke clip
            output_width  : lebar video output setelah crop (px)
            output_height : tinggi video output setelah crop (px)
            margin_v      : override margin vertikal bawah (px) — opsional
            margin_h      : override margin horizontal (px) — opsional

        Returns:
            String konten file .ass lengkap
        """
        header = self.load_header(preset_name)

        # Override PlayRes agar sesuai output video setelah crop
        header = self._override_playres(header, output_width, output_height)

        # Override margin jika diberikan
        if margin_v is not None or margin_h is not None:
            header = self._override_margin(header, margin_v, margin_h)

        # Build events section
        events_lines = [
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ]

        for entry in entries:
            start = ms_to_ass_timestamp(entry.start_ms)
            end   = ms_to_ass_timestamp(entry.end_ms)
            # Escape special ASS characters di teks
            text  = self._escape_ass(entry.text)
            events_lines.append(
                f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}"
            )

        return header + "\n" + "\n".join(events_lines) + "\n"

    def build_and_save(
        self,
        preset_name: str,
        entries: List[SubtitleEntry],
        output_path: str,
        output_width: int,
        output_height: int,
        margin_v: Optional[int] = None,
        margin_h: Optional[int] = None,
    ) -> str:
        """
        Build .ass dan simpan ke file.
        Returns: path file yang disimpan
        """
        content = self.build_ass(
            preset_name, entries,
            output_width, output_height,
            margin_v, margin_h
        )
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")
        return str(out)

    # ─── Safe Margin Calculator ───────────────────────────────────────────────────

    @staticmethod
    def calculate_safe_margin(
        output_height: int,
        bottom_safe_pct: float = 5.0
    ) -> int:
        """
        Hitung margin vertikal aman di bawah video output.

        Args:
            output_height   : tinggi video setelah crop (px)
            bottom_safe_pct : persentase safe area dari bawah (default 5%)

        Returns:
            Margin dalam pixel
        """
        return int(output_height * bottom_safe_pct / 100)

    @staticmethod
    def calculate_output_dimensions(
        src_width: int,
        src_height: int,
        left_pct: float,
        right_pct: float,
        top_pct: float,
        bottom_pct: float,
    ) -> tuple:
        """
        Hitung dimensi video setelah crop berdasarkan persentase margin.

        Returns:
            (output_width, output_height, crop_x, crop_y)
        """
        crop_left   = int(src_width  * left_pct   / 100)
        crop_right  = int(src_width  * right_pct  / 100)
        crop_top    = int(src_height * top_pct    / 100)
        crop_bottom = int(src_height * bottom_pct / 100)

        out_w = src_width  - crop_left - crop_right
        out_h = src_height - crop_top  - crop_bottom

        # Pastikan divisible by 2 (required FFmpeg)
        out_w = out_w - (out_w % 2)
        out_h = out_h - (out_h % 2)

        return (out_w, out_h, crop_left, crop_top)

    # ─── Internal helpers ─────────────────────────────────────────────────────────

    def _resolve(self, preset_name: str) -> Path:
        """Resolve nama preset ke path file .ass."""
        # Coba dengan nama persis dulu, lalu case-insensitive
        direct = self.preset_dir / f"{preset_name}.ass"
        if direct.exists():
            return direct

        for f in self.preset_dir.glob("*.ass"):
            if f.stem.lower() == preset_name.lower():
                return f

        available = self.available_presets()
        raise FileNotFoundError(
            f"Preset '{preset_name}' tidak ditemukan. "
            f"Tersedia: {available}"
        )

    def _override_playres(self, header: str, width: int, height: int) -> str:
        """Override PlayResX dan PlayResY di header."""
        header = re.sub(r"PlayResX:\s*\d+", f"PlayResX: {width}", header)
        header = re.sub(r"PlayResY:\s*\d+", f"PlayResY: {height}", header)
        return header

    def _override_margin(
        self,
        header: str,
        margin_v: Optional[int],
        margin_h: Optional[int]
    ) -> str:
        """
        Override MarginL, MarginR, MarginV pada baris Style: di header.
        Format baris Style: Name,Font,...,MarginL,MarginR,MarginV,Encoding
        Index field (0-based): 19=MarginL, 20=MarginR, 21=MarginV
        """
        lines = header.splitlines()
        result = []
        for line in lines:
            if line.startswith("Style:"):
                parts = line.split(",")
                if len(parts) >= 23:
                    if margin_h is not None:
                        parts[19] = str(margin_h)   # MarginL
                        parts[20] = str(margin_h)   # MarginR
                    if margin_v is not None:
                        parts[21] = str(margin_v)   # MarginV
                    line = ",".join(parts)
            result.append(line)
        return "\n".join(result)

    @staticmethod
    def _escape_ass(text: str) -> str:
        """Escape karakter khusus ASS dan handle multi-line."""
        text = text.replace("\\", "\\\\")
        text = text.replace("{", "\\{")
        text = text.replace("}", "\\}")
        text = text.replace("\n", "\\N")   # newline dalam 1 dialogue
        return text
