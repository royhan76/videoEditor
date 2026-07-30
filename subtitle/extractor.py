"""
Subtitle Extractor
- Membaca file .srt
- Extract subtitle berdasarkan time range (start - end)
- Output 1: plain text untuk AI
- Output 2: list entry dengan timing (untuk renderer subtitle)
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List

from subtitle.time_utils import timestamp_to_ms, ms_to_timestamp


@dataclass
class SubtitleEntry:
    """Satu baris/blok subtitle dengan timing-nya."""
    index: int
    start_ms: int           # waktu mulai di video asli (ms)
    end_ms: int             # waktu selesai di video asli (ms)
    text: str               # teks bersih (tanpa tag HTML)

    @property
    def start_ts(self) -> str:
        return ms_to_timestamp(self.start_ms)

    @property
    def end_ts(self) -> str:
        return ms_to_timestamp(self.end_ms)

    def to_plain(self) -> str:
        """Teks saja, tanpa timing (untuk dikirim ke AI)."""
        return self.text.strip()


class SubtitleExtractor:
    """
    Membaca file .srt dan menyediakan dua output:
    1. plain_text()  → string untuk AI
    2. entries()     → list SubtitleEntry untuk renderer
    """

    def __init__(self, srt_path: str):
        self.srt_path = Path(srt_path)
        if not self.srt_path.exists():
            raise FileNotFoundError(f"File subtitle tidak ditemukan: {srt_path}")

        self._raw_entries: List[SubtitleEntry] = []
        self._parse()

    # ─── Parsing ─────────────────────────────────────────────────────────────────

    def _parse(self):
        """Parse file .srt menjadi list SubtitleEntry."""
        content = self.srt_path.read_text(encoding="utf-8-sig")  # utf-8-sig handles BOM

        # Pisahkan tiap blok subtitle (dipisahkan baris kosong)
        blocks = re.split(r"\n\s*\n", content.strip())

        entries = []
        for block in blocks:
            lines = block.strip().splitlines()
            if len(lines) < 3:
                continue

            # Baris 1: index
            try:
                index = int(lines[0].strip())
            except ValueError:
                continue

            # Baris 2: timing  "00:00:01,000 --> 00:00:04,000"
            timing_match = re.match(
                r"(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,\.]\d{3})",
                lines[1].strip()
            )
            if not timing_match:
                continue

            start_ms = timestamp_to_ms(timing_match.group(1))
            end_ms   = timestamp_to_ms(timing_match.group(2))

            # Baris 3+: teks (bersihkan tag HTML seperti <i>, <b>)
            raw_text = "\n".join(lines[2:])
            clean_text = re.sub(r"<[^>]+>", "", raw_text).strip()

            if clean_text:
                entries.append(SubtitleEntry(
                    index=index,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    text=clean_text
                ))

        self._raw_entries = entries

    # ─── Public API ───────────────────────────────────────────────────────────────

    def extract(
        self,
        start_time: str,
        end_time: str
    ) -> List[SubtitleEntry]:
        """
        Kembalikan subtitle entries dalam rentang waktu.

        Args:
            start_time : timestamp awal (HH:MM:SS.mmm) di video asli
            end_time   : timestamp akhir (HH:MM:SS.mmm) di video asli

        Returns:
            List SubtitleEntry yang berada dalam rentang tersebut
        """
        start_ms = timestamp_to_ms(start_time)
        end_ms   = timestamp_to_ms(end_time)

        return [
            e for e in self._raw_entries
            if e.start_ms >= start_ms and e.end_ms <= end_ms
        ]

    def plain_text(self, start_time: str, end_time: str) -> str:
        """
        Kembalikan subtitle sebagai plain text (untuk dikirim ke AI).
        Format: "[HH:MM:SS] teks"

        Args:
            start_time : timestamp awal di video asli
            end_time   : timestamp akhir di video asli
        """
        entries = self.extract(start_time, end_time)
        if not entries:
            return ""

        lines = []
        for e in entries:
            lines.append(f"[{e.start_ts}] {e.to_plain()}")

        return "\n".join(lines)

    def shifted_entries(
        self,
        start_time: str,
        end_time: str,
        offset_ms: int = 0
    ) -> List[SubtitleEntry]:
        """
        Extract entries dan geser timing-nya relatif terhadap clip.
        Berguna untuk subtitle renderer — timing harus relatif ke video clip,
        bukan ke video asli.

        Args:
            start_time  : timestamp awal di video asli
            end_time    : timestamp akhir di video asli
            offset_ms   : tambahan offset (ms) jika diperlukan
        """
        start_ms = timestamp_to_ms(start_time)
        entries  = self.extract(start_time, end_time)

        shifted = []
        for e in entries:
            shifted.append(SubtitleEntry(
                index=e.index,
                start_ms=e.start_ms - start_ms + offset_ms,
                end_ms=e.end_ms   - start_ms + offset_ms,
                text=e.text
            ))
        return shifted

    def total_entries(self) -> int:
        """Jumlah total entry di file .srt."""
        return len(self._raw_entries)

    def duration_range(self) -> tuple:
        """
        Kembalikan (start_ms, end_ms) dari seluruh file .srt.
        """
        if not self._raw_entries:
            return (0, 0)
        return (self._raw_entries[0].start_ms, self._raw_entries[-1].end_ms)
