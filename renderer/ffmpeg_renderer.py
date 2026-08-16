"""
FFmpeg Renderer
- Menerima Timeline dari TimelineBuilder
- Build subtitle .ass (dengan remapping timing untuk hook)
- Build FFmpeg command
- Eksekusi single encode
- Simpan render_log.txt
"""

import subprocess
import logging
import os
import re
import shutil
from pathlib import Path
from typing import List, Optional, Callable

from renderer.timeline_builder import Timeline, Segment
from renderer.command_builder import FFmpegCommandBuilder
from subtitle.extractor import SubtitleEntry
from subtitle.preset_loader import PresetLoader
from subtitle.time_utils import ms_to_timestamp

logger = logging.getLogger(__name__)


class FFmpegRenderer:
    """
    Bertanggung jawab atas:
    1. Remap timing subtitle sesuai urutan hook
    2. Build file .ass dari preset
    3. Build FFmpeg command via CommandBuilder
    4. Eksekusi FFmpeg (single encode)
    5. Simpan render log
    """

    def __init__(self, config: dict, preset_dir: str):
        self.config        = config
        self.preset_loader = PresetLoader(preset_dir)
        self.cmd_builder   = FFmpegCommandBuilder()

    # ─── Public API ───────────────────────────────────────────────────────────────

    def render(
        self,
        timeline: Timeline,
        video_path: str,
        subtitle_entries: List[SubtitleEntry],
        output_path: str,
        intro_path: Optional[str] = None,
        log_path: Optional[str] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> bool:
        """
        Jalankan full render pipeline.

        Args:
            timeline          : dari TimelineBuilder.build()
            video_path        : path video clip sumber
            subtitle_entries  : dari SubtitleExtractor.shifted_entries()
                                (timing relatif ke clip, bukan video asli)
            output_path       : path output video final
            log_path          : path simpan render log (opsional)
            progress_callback : fn(pct: float, msg: str) → untuk update UI
            cancelled_flag    : callable yang return True jika render dibatalkan

        Returns:
            True jika render berhasil, False jika gagal
        """
        self._report(progress_callback, 0.0, "Menyiapkan subtitle...")

        # ── Step 1: Remap subtitle timing ke urutan final video ───────────────
        remapped = self._remap_subtitles(timeline, subtitle_entries)

        # ── Step 2: Build file .ass ───────────────────────────────────────────
        ass_path = timeline.subtitle.ass_file
        if remapped:
            saved = self.preset_loader.build_and_save(
                preset_name   = timeline.subtitle.preset,
                entries       = remapped,
                output_path   = ass_path,
                output_width  = timeline.output.width,
                output_height = timeline.output.height,
                margin_v      = PresetLoader.calculate_safe_margin(
                    timeline.output.height, bottom_safe_pct=5
                ),
            )
            logger.info(f"Subtitle .ass disimpan: {saved}")
        else:
            logger.info("Tidak ada subtitle — render tanpa subtitle")
            ass_path = None
            # Update timeline subtitle path
            timeline.subtitle.ass_file = ""

        self._report(progress_callback, 0.1, "Menyusun FFmpeg command...")

        # ── Step 3: Build FFmpeg command ────────────────────────────────────
        cmd = self.cmd_builder.build(timeline, video_path, output_path, intro_path)

        # ── Step 4: Coba codec utama, fallback ke libx264 ──────────────────────
        success = self._try_render(
            cmd, timeline, video_path, output_path,
            log_path, progress_callback
        )

        if not success:
            logger.warning(
                f"Codec '{timeline.output.codec}' gagal, "
                f"mencoba fallback '{timeline.output.fallback_codec}'..."
            )
            self._report(progress_callback, 0.1, f"Fallback ke {timeline.output.fallback_codec}...")
            timeline.output.codec = timeline.output.fallback_codec
            cmd = self.cmd_builder.build(timeline, video_path, output_path, intro_path)
            success = self._try_render(
                cmd, timeline, video_path, output_path,
                log_path, progress_callback
            )

        if success:
            self._report(progress_callback, 1.0, "Done.")
            logger.info(f"Render selesai: {output_path}")

        return success

    # ─── Subtitle Remap ───────────────────────────────────────────────────────────

    def _remap_subtitles(
        self,
        timeline: Timeline,
        entries: List[SubtitleEntry],
    ) -> List[SubtitleEntry]:
        """
        Remap timing subtitle dari waktu clip ke waktu final video secara dinamis
        berdasarkan segmen-segmen di timeline.
        """
        # Hitung start time tiap segmen di video final
        segment_mappings = []
        current_final_ms = 0
        for seg in timeline.segments:
            segment_mappings.append((seg, current_final_ms))
            current_final_ms += seg.duration_ms

        remapped = []
        for entry in entries:
            s, e = entry.start_ms, entry.end_ms

            matched_seg = None
            matched_final_start = 0
            for seg, f_start in segment_mappings:
                if seg.label == "intro":
                    continue
                # Cek apakah timing subtitle sepenuhnya berada di dalam segmen sumber asli
                if s >= seg.start_ms and e <= seg.end_ms:
                    matched_seg = seg
                    matched_final_start = f_start
                    break

            if matched_seg is None:
                logger.debug(
                    f"Subtitle overlapping segment boundary atau di luar bounds — dilewati: {ms_to_timestamp(s)}"
                )
                continue

            # Remap: offset relatif terhadap segmen asal + start_time segmen tersebut di final video
            new_s = (s - matched_seg.start_ms) + matched_final_start
            new_e = (e - matched_seg.start_ms) + matched_final_start

            remapped.append(SubtitleEntry(
                index    = entry.index,
                start_ms = new_s,
                end_ms   = new_e,
                text     = entry.text,
            ))

        # Urutkan berdasarkan waktu
        remapped.sort(key=lambda x: x.start_ms)
        return remapped

    # ─── Render Execution ─────────────────────────────────────────────────────────

    def _try_render(
        self,
        cmd: List[str],
        timeline: Timeline,
        video_path: str,
        output_path: str,
        log_path: Optional[str],
        progress_callback: Optional[Callable],
    ) -> bool:
        """Jalankan FFmpeg command, tangkap output, return True jika sukses."""

        cmd_str = self.cmd_builder.command_to_string(cmd)
        logger.info(f"Menjalankan FFmpeg:\n{cmd_str}")

        # Pastikan folder output ada
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        log_lines = [f"Command:\n{cmd_str}\n\nOutput:\n"]

        # Windows: jalankan FFmpeg di priority BELOW_NORMAL agar tidak
        # bersaing dengan UI dan sistem. Di non-Windows, gunakan nice().
        creation_flags = 0
        preexec = None
        if os.name == "nt":
            BELOW_NORMAL_PRIORITY_CLASS = 0x00004000
            creation_flags = BELOW_NORMAL_PRIORITY_CLASS
        else:
            import signal
            preexec = lambda: os.nice(10)  # noqa: E731

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                encoding="utf-8",
                errors="replace",
                creationflags=creation_flags,
            )

            total_duration_ms = sum(s.duration_ms for s in timeline.segments)

            for line in process.stdout:
                line = line.rstrip()
                log_lines.append(line)

                # Parse progress dari FFmpeg output
                pct = self._parse_progress(line, total_duration_ms)
                if pct is not None:
                    self._report(progress_callback, 0.1 + pct * 0.89, f"Rendering... {pct*100:.1f}%")

            process.wait()
            success = (process.returncode == 0)

        except FileNotFoundError:
            logger.error("FFmpeg tidak ditemukan! Pastikan FFmpeg terinstall dan ada di PATH.")
            log_lines.append("ERROR: FFmpeg tidak ditemukan di PATH.")
            success = False

        except Exception as e:
            logger.error(f"Error saat render: {e}")
            log_lines.append(f"ERROR: {e}")
            success = False

        finally:
            if log_path:
                self._save_log(log_path, log_lines, success)

        return success

    # ─── Helpers ─────────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_progress(line: str, total_duration_ms: int) -> Optional[float]:
        """
        Parse baris FFmpeg output untuk mendapatkan progress (0.0 - 1.0).
        FFmpeg menulis: time=HH:MM:SS.cc
        """
        if total_duration_ms <= 0:
            return None

        match = re.search(r"time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})", line)
        if not match:
            return None

        h, m, s, cs = int(match.group(1)), int(match.group(2)), \
                      int(match.group(3)), int(match.group(4))
        elapsed_ms = (h * 3600 + m * 60 + s) * 1000 + cs * 10

        return min(elapsed_ms / total_duration_ms, 1.0)

    @staticmethod
    def _save_log(log_path: str, lines: List[str], success: bool):
        """Simpan render log ke file."""
        status = "SUCCESS" if success else "FAILED"
        content = f"Render Status: {status}\n\n" + "\n".join(lines)
        try:
            Path(log_path).parent.mkdir(parents=True, exist_ok=True)
            Path(log_path).write_text(content, encoding="utf-8")
        except Exception as e:
            logger.error(f"Gagal simpan render log: {e}")

    @staticmethod
    def _report(
        callback: Optional[Callable],
        pct: float,
        msg: str,
    ):
        """Kirim progress update ke callback (jika ada)."""
        logger.debug(f"Progress {pct*100:.1f}%: {msg}")
        if callback:
            callback(pct, msg)

    # ─── Utility ─────────────────────────────────────────────────────────────────

    @staticmethod
    def check_ffmpeg() -> bool:
        """Cek apakah FFmpeg tersedia di PATH."""
        return shutil.which("ffmpeg") is not None

    @staticmethod
    def check_codec(codec: str) -> bool:
        """Cek apakah codec tertentu didukung FFmpeg."""
        try:
            result = subprocess.run(
                ["ffmpeg", "-hide_banner", "-encoders"],
                capture_output=True, text=True, timeout=5
            )
            return codec in result.stdout
        except Exception:
            return False

    @staticmethod
    def probe_video(video_path: str) -> Optional[dict]:
        """
        Ambil info video menggunakan ffprobe.
        Returns: dict dengan width, height, duration_ms, has_audio
        """
        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "quiet",
                    "-print_format", "json",
                    "-show_streams",
                    video_path
                ],
                capture_output=True, text=True, timeout=15
            )
            import json
            data = json.loads(result.stdout)
            streams = data.get("streams", [])

            info = {"has_audio": False, "width": 0, "height": 0, "duration_ms": 0}
            for stream in streams:
                codec_type = stream.get("codec_type")
                if codec_type == "video":
                    info["width"]  = int(stream.get("width",  0))
                    info["height"] = int(stream.get("height", 0))
                    dur = float(stream.get("duration", 0))
                    info["duration_ms"] = int(dur * 1000)
                elif codec_type == "audio":
                    info["has_audio"] = True
            return info

        except Exception as e:
            logger.error(f"ffprobe error: {e}")
            return None
