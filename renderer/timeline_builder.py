"""
Timeline Builder
- Membaca EditPlan + config
- Mengonversi hook timestamps dari waktu video asli ke waktu relatif clip
- Menyusun timeline dict yang siap dikirim ke FFmpeg Renderer
- TIDAK pernah membuat FFmpeg command langsung
"""

import logging
from dataclasses import dataclass, field, asdict
from typing import List, Optional

from ai.edit_plan import EditPlan
from subtitle.time_utils import timestamp_to_ms, ms_to_timestamp
from subtitle.preset_loader import PresetLoader

logger = logging.getLogger(__name__)


# ─── Timeline Data Models ────────────────────────────────────────────────────────

@dataclass
class Segment:
    """Satu potongan video dalam timeline."""
    label: str              # "hook" | "intro" | "body_start" | "body_end" | "full"
    start_ms: int           # start dalam clip (relative)
    end_ms: int             # end dalam clip (relative)
    audio_fade_in_ms: int = 0
    audio_fade_out_ms: int = 0
    has_audio: bool = True  # False jika sumber video tidak punya stream audio

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms

    @property
    def start_ts(self) -> str:
        return ms_to_timestamp(self.start_ms)

    @property
    def end_ts(self) -> str:
        return ms_to_timestamp(self.end_ms)


@dataclass
class CropInfo:
    """Informasi crop video."""
    x: int
    y: int
    width: int
    height: int
    src_width: int = 0   # lebar video sumber sebelum crop
    src_height: int = 0  # tinggi video sumber sebelum crop


@dataclass
class SubtitleInfo:
    """Informasi subtitle untuk renderer."""
    preset: str
    ass_file: str           # path file .ass yang akan digenerate renderer
    font_size: int = 0      # 0 = pakai default dari preset


@dataclass
class VisualInfo:
    """
    Visual treatment (anti-Copyright visual) — terapkan SETELAH crop.

    Kalibrasi riil di mesin user (video ceramah 380x234):
      level 5: crop 10% + contrast 6% + sat 6% + noise 5
        → claim PT DRM "Audio visual" LEPAS total.

    Nilai:
      enabled : aktif/tidak
      level   : 0-10
        - level 0      : tidak ada filter
        - 1-4          : crop 2-8% + contrast/sat 2-4% (ringan)
        - 5-7          : crop 10% + contrast/sat 6-8% + noise 5-7 (default 5 = terbukti)
        - 8-10         : crop 12-15% + contrast/sat 10-12% + noise 8-10 (agresif)
    """
    enabled: bool = False
    level: int = 5
    mirror_enabled: bool = False

    def vf_suffix(self, src_w: int, src_h: int) -> str:
        """Return filter string yang ditambahkan SETELAH crop filter.

        Memakai ukuran POST-crop (crop.width/height) sebagai basis, karena
        filter ini dipasang setelah [vcrop] di chain.
        """
        if not self.enabled or self.level <= 0:
            return ""

        initial_filters = []
        if self.mirror_enabled:
            initial_filters.append("hflip")

        lvl = self.level
        # Crop ASIMETRIS: lebar ringan, tinggi dalam → ubah aspect ratio
        # (racikan manual yang lolos YT: crop 1440:694 dari 1920x1080 = aspek 2.07)
        # pct_w: 2% → 16% ; pct_h: 8% → 41% (lvl 1-10)
        pct_w = 0.02 + (lvl - 1) * 0.015
        pct_h = 0.08 + (lvl - 1) * 0.037
        # Force even dimensions — libx264 (dan H.264) reject ganjil, error
        # "Invalid too big or non positive size". cx/cy juga genap biar crop valid.
        def _even(v): return v - (v % 2)
        cw = _even(max(2, min(src_w - 2, int(src_w * (1 - pct_w)))))
        ch = _even(max(2, min(src_h - 2, int(src_h * (1 - pct_h)))))
        cx = _even(max(0, (src_w - cw) // 2))
        cy = _even(max(0, (src_h - ch) // 2))

        # Contrast/Saturation diperkuat biar fingerprint warna berubah drastis
        contrast = 1.0 + lvl * 0.015      # 1.015 → 1.15
        sat      = 1.0 + lvl * 0.015      # 1.015 → 1.15
        noise    = max(1, int(3 + lvl * 1.0))  # 4 → 13

        parts = [
            f"crop={cw}:{ch}:{cx}:{cy}",
            f"scale={src_w}:{src_h}",
            f"eq=contrast={contrast:.2f}:saturation={sat:.2f}",
            f"noise=alls={noise}:allf=t+u",
        ]
        return ",".join(initial_filters + parts)


@dataclass
class AudioInfo:
    """Konfigurasi audio fade/crossfade."""
    fade_in_ms: int
    fade_out_ms: int
    crossfade_ms: int
    masking_enabled: bool = False
    masking_intensity: float = 0.5  # 0.0 to 1.0


@dataclass
class OutputInfo:
    """Konfigurasi output video."""
    width: int
    height: int
    codec: str
    fallback_codec: str
    crf: int
    preset: str
    format: str


@dataclass
class Timeline:
    """
    Representasi lengkap rencana editing yang siap dikirim ke FFmpeg Renderer.
    """
    segments: List[Segment]
    crop: CropInfo
    subtitle: SubtitleInfo
    audio: AudioInfo
    output: OutputInfo
    visual: VisualInfo = field(default_factory=VisualInfo)
    has_hook: bool = True

    def to_dict(self) -> dict:
        return {
            "has_hook": self.has_hook,
            "segments": [asdict(s) for s in self.segments],
            "crop": asdict(self.crop),
            "subtitle": asdict(self.subtitle),
            "audio": asdict(self.audio),
            "visual": asdict(self.visual),
            "output": asdict(self.output),
        }


# ─── Timeline Builder ─────────────────────────────────────────────────────────────

class TimelineBuilder:
    """
    Membaca EditPlan dan config, menghasilkan Timeline siap render.

    Alur hook processing (sesuai spec):
        CUT hook → MOVE ke awal → DELETE original → JOIN
        → [Hook] + [0 → hook_start] + [hook_end → video_end]

    Audio fade:
        Hook     : fade_in di awal, fade_out di akhir
        Body join: crossfade di titik sambungan Hook → Body
    """

    def __init__(self, config: dict):
        self.config = config

    def build(
        self,
        edit_plan: EditPlan,
        subtitle_start_time: str,
        video_duration_ms: int,
        video_src_width: int,
        video_src_height: int,
        subtitle_ass_path: str,
        preset_dir: str,
        intro_duration_ms: int = 0,
        intro_has_audio: bool = True,
    ) -> Timeline:
        """
        Build Timeline dari EditPlan.

        Args:
            edit_plan           : hasil dari AIDirector.analyze()
            subtitle_start_time : timestamp awal subtitle di video asli (HH:MM:SS)
                                  → dipakai untuk konversi hook ke waktu clip
            video_duration_ms   : durasi video clip dalam ms
            video_src_width     : lebar video sumber (sebelum crop)
            video_src_height    : tinggi video sumber (sebelum crop)
            subtitle_ass_path   : path output file .ass (akan dibuat renderer)
            preset_dir          : folder preset .ass
            intro_duration_ms   : durasi video intro dalam ms (0 = tidak ada intro)

        Returns:
            Timeline siap kirim ke FFmpeg Renderer
        """
        logger.info("Building timeline...")

        crop    = self._build_crop(video_src_width, video_src_height)
        audio   = self._build_audio()
        visual  = self._build_visual()
        output  = self._build_output(crop)
        subtitle = SubtitleInfo(
            preset=edit_plan.subtitle.preset,
            ass_file=subtitle_ass_path
        )

        # Konversi hook timestamps ke clip-relative
        clip_offset_ms  = timestamp_to_ms(subtitle_start_time)
        hook_start_ms   = edit_plan.hook.start_ms - clip_offset_ms
        hook_end_ms     = edit_plan.hook.end_ms   - clip_offset_ms

        # Validasi hook masih dalam range clip
        hook_start_ms, hook_end_ms, valid = self._validate_hook_range(
            hook_start_ms, hook_end_ms, video_duration_ms
        )

        if not valid:
            logger.warning("Hook di luar range clip — render tanpa hook")
            segments = self._build_segments_no_hook(video_duration_ms, audio, intro_duration_ms, intro_has_audio)
            return Timeline(
                segments=segments, crop=crop, subtitle=subtitle,
                audio=audio, visual=visual, output=output, has_hook=False
            )

        segments = self._build_segments_with_hook(
            hook_start_ms, hook_end_ms, video_duration_ms, audio, intro_duration_ms, intro_has_audio
        )

        logger.info(
            f"Timeline ready — {len(segments)} segment(s), "
            f"hook: {ms_to_timestamp(hook_start_ms)} → {ms_to_timestamp(hook_end_ms)}, "
            f"output: {output.width}x{output.height}"
        )

        return Timeline(
            segments=segments, crop=crop, subtitle=subtitle,
            audio=audio, visual=visual, output=output, has_hook=True
        )

    def build_no_hook(
        self,
        edit_plan: EditPlan,
        video_duration_ms: int,
        video_src_width: int,
        video_src_height: int,
        subtitle_ass_path: str,
        intro_duration_ms: int = 0,
        intro_has_audio: bool = True,
    ) -> Timeline:
        """
        Build Timeline TANPA hook (fallback jika AI gagal).
        """
        logger.info("Building timeline tanpa hook (fallback)...")

        crop    = self._build_crop(video_src_width, video_src_height)
        audio   = self._build_audio()
        visual  = self._build_visual()
        output  = self._build_output(crop)
        subtitle = SubtitleInfo(
            preset=edit_plan.subtitle.preset if edit_plan else "Modern01",
            ass_file=subtitle_ass_path
        )
        segments = self._build_segments_no_hook(video_duration_ms, audio, intro_duration_ms, intro_has_audio)

        return Timeline(
            segments=segments, crop=crop, subtitle=subtitle,
            audio=audio, visual=visual, output=output, has_hook=False
        )

    # ─── Segment builders ─────────────────────────────────────────────────────────

    def _build_segments_with_hook(
        self,
        hook_start_ms: int,
        hook_end_ms: int,
        video_duration_ms: int,
        audio: AudioInfo,
        intro_duration_ms: int = 0,
        intro_has_audio: bool = True,
    ) -> List[Segment]:
        """
        Susun segmen: [Hook] + [Intro*] + [Body Start] + [Body End]

        Hook           : hook_start → hook_end (fade in + fade out)
        Intro (opsional): full intro video (input terpisah, index ditandai label)
        Body Start     : 0 → hook_start
        Body End       : hook_end → video_end

        Label "intro" memberi tahu CommandBuilder untuk pakai intro_path,
        bukan video_path, sebagai sumber input segmen ini.
        """
        segments = []

        # Segmen 1: Hook (dipindah ke depan)
        segments.append(Segment(
            label="hook",
            start_ms=hook_start_ms,
            end_ms=hook_end_ms,
            audio_fade_in_ms=audio.fade_in_ms,
            audio_fade_out_ms=audio.fade_out_ms,
        ))

        # Segmen 2: Intro (opsional, disisipkan setelah hook)
        if intro_duration_ms > 0:
            segments.append(Segment(
                label="intro",
                start_ms=0,
                end_ms=intro_duration_ms,
                audio_fade_in_ms=0,
                audio_fade_out_ms=0,
                has_audio=intro_has_audio,
            ))

        # Segmen 3: Body Start (bagian SEBELUM hook di video asli)
        if hook_start_ms > 0:
            segments.append(Segment(
                label="body_start",
                start_ms=0,
                end_ms=hook_start_ms,
                audio_fade_in_ms=audio.fade_in_ms,
                audio_fade_out_ms=0,
            ))

        # Segmen 4: Body End (bagian SETELAH hook di video asli)
        if hook_end_ms < video_duration_ms:
            segments.append(Segment(
                label="body_end",
                start_ms=hook_end_ms,
                end_ms=video_duration_ms,
                audio_fade_in_ms=0,
                audio_fade_out_ms=0,
            ))

        return segments

    def _build_segments_no_hook(
        self,
        video_duration_ms: int,
        audio: AudioInfo,
        intro_duration_ms: int = 0,
        intro_has_audio: bool = True,
    ) -> List[Segment]:
        """Satu atau dua segmen: [Intro*] + [Full video] tanpa perubahan urutan."""
        segments = []
        if intro_duration_ms > 0:
            segments.append(Segment(
                label="intro",
                start_ms=0,
                end_ms=intro_duration_ms,
                audio_fade_in_ms=0,
                audio_fade_out_ms=0,
                has_audio=intro_has_audio,
            ))
        segments.append(Segment(
            label="full",
            start_ms=0,
            end_ms=video_duration_ms,
            audio_fade_in_ms=0,
            audio_fade_out_ms=0,
        ))
        return segments

    # ─── Info builders ────────────────────────────────────────────────────────────

    def _build_crop(self, src_w: int, src_h: int) -> CropInfo:
        crop_cfg = self.config.get("crop", {})
        if not crop_cfg.get("enabled", True):
            return CropInfo(x=0, y=0, width=src_w, height=src_h,
                            src_width=src_w, src_height=src_h)

        out_w, out_h, cx, cy = PresetLoader.calculate_output_dimensions(
            src_w, src_h,
            left_pct   = crop_cfg.get("left_pct",   8),
            right_pct  = crop_cfg.get("right_pct",  8),
            top_pct    = crop_cfg.get("top_pct",    4),
            bottom_pct = crop_cfg.get("bottom_pct", 10),
        )
        return CropInfo(x=cx, y=cy, width=out_w, height=out_h,
                        src_width=src_w, src_height=src_h)

    def _build_visual(self) -> VisualInfo:
        v = self.config.get("visual", {})
        return VisualInfo(
            enabled = v.get("enabled", False),
            level   = v.get("level", 5),
            mirror_enabled = v.get("mirror_enabled", False),
        )

    def _build_audio(self) -> AudioInfo:
        a = self.config.get("audio", {})
        return AudioInfo(
            fade_in_ms      = a.get("fade_in",      300),
            fade_out_ms     = a.get("fade_out",     300),
            crossfade_ms    = a.get("crossfade",    400),
            masking_enabled = a.get("masking_enabled",  False),
            masking_intensity = a.get("masking_intensity", 0.5),
        )

    def _build_output(self, crop: CropInfo) -> OutputInfo:
        r = self.config.get("render", {})
        return OutputInfo(
            width         = crop.width,
            height        = crop.height,
            codec         = r.get("codec",          "h264_nvenc"),
            fallback_codec= r.get("fallback_codec", "libx264"),
            crf           = r.get("crf",            18),
            preset        = r.get("preset",         "fast"),
            format        = r.get("output_format",  "mp4"),
        )

    # ─── Validators ──────────────────────────────────────────────────────────────

    def _validate_hook_range(
        self,
        hook_start_ms: int,
        hook_end_ms: int,
        video_duration_ms: int,
    ) -> tuple:
        """
        Validasi hook masih dalam range clip.

        Toleransi: jika hook_start sedikit negatif (< 2 detik), clamp ke 0.
        Ini terjadi karena AI sering return timestamp tanpa ms (misal "00:35:27")
        sementara subtitle_start_time punya ms (misal "00:35:27.400").

        Returns: (start_ms, end_ms, is_valid)
        """
        TOLERANCE_MS = 2000   # toleransi 2 detik

        # Clamp hook_start jika sedikit negatif (dalam toleransi)
        if -TOLERANCE_MS <= hook_start_ms < 0:
            logger.info(
                f"Hook start {hook_start_ms}ms di-clamp ke 0 "
                f"(selisih kecil antara AI timestamp dan subtitle_start)"
            )
            hook_start_ms = 0

        # Clamp hook_end jika sedikit melebihi durasi (dalam toleransi)
        if video_duration_ms < hook_end_ms <= video_duration_ms + TOLERANCE_MS:
            logger.info(
                f"Hook end {hook_end_ms}ms di-clamp ke {video_duration_ms}ms"
            )
            hook_end_ms = video_duration_ms

        if hook_start_ms < 0 or hook_end_ms > video_duration_ms:
            logger.warning(
                f"Hook out of range: {hook_start_ms}ms - {hook_end_ms}ms "
                f"(clip duration: {video_duration_ms}ms)"
            )
            return (hook_start_ms, hook_end_ms, False)

        if hook_start_ms >= hook_end_ms:
            logger.warning("Hook start >= end — invalid hook")
            return (hook_start_ms, hook_end_ms, False)

        # Pastikan hook minimal 5 detik setelah clamping
        if (hook_end_ms - hook_start_ms) < 5000:
            logger.warning(
                f"Hook terlalu pendek setelah clamping: "
                f"{(hook_end_ms - hook_start_ms)/1000:.1f}s"
            )
            return (hook_start_ms, hook_end_ms, False)

        return (hook_start_ms, hook_end_ms, True)
