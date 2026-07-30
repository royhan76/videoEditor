"""
Worker Thread
Menjalankan full pipeline (AI → Timeline → Render) di background thread.
Berkomunikasi ke UI via Qt signals.
"""

import logging
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from config import load_config, get_preset_dir, get_output_dir, get_temp_dir
from subtitle import SubtitleExtractor, PresetLoader
from ai.director import AIDirector
from ai.edit_plan import EditPlan, HookPlan, SubtitlePlan
from renderer.timeline_builder import TimelineBuilder
from renderer.ffmpeg_renderer import FFmpegRenderer

logger = logging.getLogger(__name__)


class WorkerSignals:
    pass


class RenderWorker(QThread):
    """
    Background thread yang menjalankan full pipeline:
    1. ffprobe → video info
    2. Subtitle extract
    3. AI Director → edit_plan
    4. Timeline Builder
    5. FFmpeg Renderer
    """

    # Signals
    progress    = Signal(float, str)    # (pct 0.0-1.0, message)
    log_message = Signal(str)           # log line
    finished    = Signal(bool, str)     # (success, output_path or error_msg)

    def __init__(
        self,
        video_path: str,
        intro_path: str | None,
        subtitle_path: str,
        subtitle_start: str,
        subtitle_preset: str,
        auto_hook: bool,
        crop_settings: dict,
    ):
        super().__init__()
        self.video_path       = video_path
        self.intro_path       = intro_path      # None jika tidak ada intro
        self.subtitle_path    = subtitle_path
        self.subtitle_start   = subtitle_start
        self.subtitle_preset  = subtitle_preset
        self.auto_hook        = auto_hook
        self.crop_settings    = crop_settings
        self._cancelled       = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            self._pipeline()
        except Exception as e:
            logger.exception("Pipeline error")
            self.finished.emit(False, str(e))

    def _pipeline(self):
        # Reload config setiap kali worker jalan (ambil nilai terbaru dari disk)
        from config.config_loader import ConfigLoader
        ConfigLoader._instance = None
        config = load_config()

        # Override crop settings dari UI
        config["crop"].update(self.crop_settings)

        output_dir  = get_output_dir()
        temp_dir    = get_temp_dir()
        preset_dir  = get_preset_dir()
        output_dir.mkdir(parents=True, exist_ok=True)
        temp_dir.mkdir(parents=True, exist_ok=True)

        # Auto-detect codec yang tersedia (hindari encode 2x)
        if config.get("render", {}).get("codec") == "h264_nvenc":
            if not FFmpegRenderer.check_codec("h264_nvenc"):
                self._log("[INFO] h264_nvenc tidak tersedia \u2014 menggunakan libx264")
                config["render"]["codec"] = "libx264"
            else:
                self._log("[INFO] Codec: h264_nvenc (GPU)")

        # Nama output: render_<nama_video_input>.mp4
        input_stem  = Path(self.video_path).stem
        output_name = f"render_{input_stem}.mp4"
        output_path = str(output_dir / output_name)
        ass_path    = str(temp_dir   / "subtitle_output.ass")
        log_path    = str(output_dir / "render_log.txt")
        plan_path   = str(output_dir / "edit_plan.json")

        # ── Step 1: Probe video ────────────────────────────────────────────
        self._emit_progress(0.02, "Membaca info video...")
        self._log("Membaca info video...")

        info = FFmpegRenderer.probe_video(self.video_path)
        if not info:
            self.finished.emit(False, "Gagal membaca video. Pastikan FFmpeg terinstall.")
            return

        src_w, src_h     = info["width"], info["height"]
        video_duration_ms = info["duration_ms"]

        if video_duration_ms == 0:
            self.finished.emit(False, "Durasi video tidak terdeteksi.")
            return

        self._log(f"Video: {src_w}x{src_h}, durasi: {video_duration_ms/1000:.1f}s")

        # ── Step 1b: Probe intro (opsional) ───────────────────────────────
        intro_duration_ms = 0
        intro_has_audio   = True
        if self.intro_path:
            intro_info = FFmpegRenderer.probe_video(self.intro_path)
            if intro_info:
                intro_duration_ms = intro_info["duration_ms"]
                intro_has_audio   = intro_info["has_audio"]
                self._log(
                    f"Intro: {intro_info['width']}x{intro_info['height']}, "
                    f"durasi: {intro_duration_ms/1000:.1f}s, "
                    f"audio: {'ya' if intro_has_audio else 'tidak ada'}"
                )
                if not intro_has_audio:
                    self._log("[INFO] Intro tidak punya audio — akan diganti silent audio.")
            else:
                self._log("[WARNING] Gagal probe intro video — intro akan diabaikan.")
                self.intro_path = None

        if self._cancelled:
            return

        # ── Step 2: Extract subtitle ───────────────────────────────────────
        self._emit_progress(0.06, "Membaca subtitle...")
        self._log("Mengekstrak subtitle...")

        try:
            extractor = SubtitleExtractor(self.subtitle_path)
        except FileNotFoundError as e:
            self.finished.emit(False, str(e))
            return

        from subtitle.time_utils import timestamp_to_ms, ms_to_timestamp
        start_ms  = timestamp_to_ms(self.subtitle_start)
        end_ms    = start_ms + video_duration_ms
        end_time  = ms_to_timestamp(end_ms)

        self._log(f"Subtitle range: {self.subtitle_start} --> {end_time}")

        plain_text = extractor.plain_text(self.subtitle_start, end_time)
        if not plain_text.strip():
            self.finished.emit(False, "Subtitle kosong dalam rentang waktu yang dipilih.")
            return

        shifted_entries = extractor.shifted_entries(self.subtitle_start, end_time)
        self._log(f"Ditemukan {len(shifted_entries)} subtitle entries.")

        if self._cancelled:
            return

        # ── Step 3: AI Director ────────────────────────────────────────────
        edit_plan = None

        if self.auto_hook:
            self._emit_progress(0.10, "Mengirim ke AI Director...")
            self._log("Mengirim subtitle ke AI...")

            api_key = config.get("api", {}).get("api_key", "")
            if not api_key or api_key == "YOUR_API_KEY_HERE":
                self._log("[WARNING] API key belum dikonfigurasi di config/config.json")
                self._log("          Render akan berjalan TANPA hook.")
            else:
                try:
                    director = AIDirector(config)
                    available = PresetLoader(str(preset_dir)).available_presets()
                    edit_plan = director.analyze(
                        subtitle_text      = plain_text,
                        available_presets  = available,
                        save_path          = plan_path,
                    )
                    if edit_plan:
                        self._log(
                            f"[AI] Hook ditemukan: {edit_plan.hook.start} --> "
                            f"{edit_plan.hook.end} (score: {edit_plan.hook.score})"
                        )
                        self._log(f"[AI] Alasan : {edit_plan.hook.reason}")
                        self._log(f"[AI] Preset : {edit_plan.subtitle.preset}")
                    else:
                        self._log("[WARNING] AI tidak menemukan hook — render tanpa hook.")
                except Exception as e:
                    self._log(f"[WARNING] AI error: {e}")
                    self._log("          Render akan berjalan TANPA hook.")

        # Fallback edit_plan tanpa hook
        if edit_plan is None:
            preset = self.subtitle_preset or config.get("subtitle", {}).get("default_preset", "Modern01")
            edit_plan = EditPlan(
                hook=HookPlan(start="00:00:00", end="00:00:01", score=0, reason="No hook"),
                subtitle=SubtitlePlan(preset=preset)
            )

        if self._cancelled:
            return

        # ── Step 4: Timeline Builder ───────────────────────────────────────
        self._emit_progress(0.20, "Menyusun timeline...")
        self._log("Menyusun timeline...")

        tl_builder = TimelineBuilder(config)

        # Hook aktif jika: auto_hook aktif, edit_plan ada, dan durasi hook valid (> 0ms)
        hook_active = (
            self.auto_hook
            and edit_plan is not None
            and edit_plan.hook.duration_ms > 0
        )
        hook_score_str    = str(edit_plan.hook.score) if edit_plan else "N/A"
        hook_duration_str = f"{edit_plan.hook.duration_ms/1000:.1f}s" if edit_plan else "N/A"
        self._log(
            f"[HOOK] auto_hook={self.auto_hook}, "
            f"plan={'ada' if edit_plan else 'None'}, "
            f"score={hook_score_str}, "
            f"duration={hook_duration_str}, "
            f"hook_active={hook_active}"
        )

        if hook_active:
            timeline = tl_builder.build(
                edit_plan           = edit_plan,
                subtitle_start_time = self.subtitle_start,
                video_duration_ms   = video_duration_ms,
                video_src_width     = src_w,
                video_src_height    = src_h,
                subtitle_ass_path   = ass_path,
                preset_dir          = str(preset_dir),
                intro_duration_ms   = intro_duration_ms,
                intro_has_audio     = intro_has_audio,
            )
        else:
            timeline = tl_builder.build_no_hook(
                edit_plan         = edit_plan,
                video_duration_ms = video_duration_ms,
                video_src_width   = src_w,
                video_src_height  = src_h,
                subtitle_ass_path = ass_path,
                intro_duration_ms = intro_duration_ms,
                intro_has_audio   = intro_has_audio,
            )

        # Override preset dari UI jika user memilih manual
        if self.subtitle_preset:
            timeline.subtitle.preset = self.subtitle_preset

        self._log(
            f"[TIMELINE] Segmen: {len(timeline.segments)} | "
            f"Hook aktif: {timeline.has_hook} | "
            f"Output: {timeline.output.width}x{timeline.output.height} | "
            f"Codec: {timeline.output.codec}"
        )
        if timeline.has_hook:
            hook_seg = next((s for s in timeline.segments if s.label == 'hook'), None)
            if hook_seg:
                self._log(
                    f"[HOOK] Dipindahkan: "
                    f"{hook_seg.start_ts} --> {hook_seg.end_ts} "
                    f"({hook_seg.duration_ms/1000:.1f}s) ke posisi awal video"
                )
        else:
            self._log("[TIMELINE] has_hook=False — video dirender tanpa perubahan urutan.")

        if self._cancelled:
            return

        # ── Step 5: FFmpeg Render ──────────────────────────────────────────
        self._emit_progress(0.25, "Memulai render...")
        self._log("Memulai render FFmpeg...")
        self._log(f"Output: {output_path}")

        renderer = FFmpegRenderer(config, preset_dir=str(preset_dir))

        # Log FFmpeg command sebelum dijalankan
        from renderer.command_builder import FFmpegCommandBuilder
        _cmd_preview = FFmpegCommandBuilder().build(timeline, self.video_path, output_path, self.intro_path)
        self._log("[FFmpeg CMD] " + " ".join(_cmd_preview[:6]) + " ... (lihat render_log.txt untuk detail)")

        success = renderer.render(
            timeline          = timeline,
            video_path        = self.video_path,
            intro_path        = self.intro_path,
            subtitle_entries  = shifted_entries,
            output_path       = output_path,
            log_path          = log_path,
            progress_callback = self._on_render_progress,
        )

        if success:
            self._log(f"[DONE] Render selesai! Output: {output_path}")
            self.finished.emit(True, output_path)
        else:
            self._log("[ERROR] Render gagal. Cek render_log.txt untuk detail.")
            self.finished.emit(False, f"Render gagal. Log: {log_path}")

    # ─── Helpers ─────────────────────────────────────────────────────────────────

    def _on_render_progress(self, pct: float, msg: str):
        render_pct = 0.25 + pct * 0.75   # Render = 25% - 100% dari total
        self._emit_progress(render_pct, msg)

    def _emit_progress(self, pct: float, msg: str):
        self.progress.emit(pct, msg)

    def _log(self, msg: str):
        logger.info(msg)
        self.log_message.emit(msg)
