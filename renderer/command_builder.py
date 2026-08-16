"""
FFmpeg Command Builder
Menyusun FFmpeg command dari Timeline.
Dipisah dari Renderer agar mudah ditest dan dikembangkan.

Pendekatan: Multi-input seeking (-ss -to per segmen) menggantikan
split/asplit filter. FFmpeg membaca tiap segmen langsung dari disk
tanpa mendecode seluruh video ke memori → RAM jauh lebih hemat.
"""

import re
from pathlib import Path
from typing import List, Optional, Tuple

from renderer.timeline_builder import Timeline, Segment


class FFmpegCommandBuilder:
    """
    Membangun FFmpeg command dari Timeline.

    Output: list of strings → siap dipakai subprocess.run()
    AI tidak pernah menyentuh class ini.
    """

    def build(
        self,
        timeline: Timeline,
        video_path: str,
        output_path: str,
        intro_path: str | None = None,
    ) -> List[str]:
        """
        Build full FFmpeg command.

        Returns:
            List[str] — argv list untuk subprocess.run()
        """
        if timeline.has_hook:
            return self._build_with_hook(timeline, video_path, output_path, intro_path)
        else:
            return self._build_no_hook(timeline, video_path, output_path, intro_path)

    # ─── With Hook ────────────────────────────────────────────────────────────────

    def _build_with_hook(
        self,
        timeline: Timeline,
        video_path: str,
        output_path: str,
        intro_path: str | None = None,
    ) -> List[str]:
        """
        Gunakan multi-input seeking: tiap segmen jadi input terpisah dengan
        -ss/-t sehingga FFmpeg hanya mendecode bagian yang dibutuhkan.
        Segmen berlabel "intro" pakai intro_path sebagai sumber input.
        """
        segments = timeline.segments
        n = len(segments)
        crop = timeline.crop
        audio = timeline.audio
        out = timeline.output
        ass_path = timeline.subtitle.ass_file

        # ── 0. Susun input flags per segmen ─────────────────────────────────
        # Segmen tanpa audio → inject lavfi anullsrc sebagai input audio dummy.
        # Kita track index input FFmpeg aktual (bukan index segmen) karena
        # lavfi inputs menyisip dan menggeser index.
        cmd = ["ffmpeg", "-y"]
        video_in_idx = {}   # seg_index → FFmpeg input index untuk [N:v]
        audio_in_idx = {}   # seg_index → FFmpeg input index untuk [N:a]
        cur_idx = 0

        for i, seg in enumerate(segments):
            ss  = seg.start_ms / 1000
            dur = seg.duration_ms / 1000
            src = intro_path if (seg.label == "intro" and intro_path) else video_path
            cmd += ["-ss", f"{ss:.3f}", "-t", f"{dur:.3f}", "-i", src]
            video_in_idx[i] = cur_idx
            if seg.has_audio:
                audio_in_idx[i] = cur_idx   # audio dari input video yang sama
            cur_idx += 1

            if not seg.has_audio:
                # Inject input audio silent setelah input video-nya
                cmd += [
                    "-f", "lavfi",
                    "-t", f"{dur:.3f}",
                    "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                ]
                audio_in_idx[i] = cur_idx   # audio dari lavfi
                cur_idx += 1

        # ── 1. Susun filter_complex ───────────────────────────────────────────
        # Intro harus di-scale ke ukuran PRE-CROP karena crop diterapkan
        # SETELAH concat. Segmen lain dari video utama masuk concat dalam
        # ukuran aslinya (pre-crop), jadi intro harus sama.
        src_w = crop.src_width  if crop.src_width  > 0 else crop.width
        src_h = crop.src_height if crop.src_height > 0 else crop.height

        filter_parts = []

        for i, seg in enumerate(segments):
            dur = seg.duration_ms / 1000
            fi  = seg.audio_fade_in_ms  / 1000
            fo  = seg.audio_fade_out_ms / 1000
            vi  = video_in_idx[i]
            ai  = audio_in_idx[i]

            # Scale semua segmen ke ukuran pre-crop video utama + normalisasi fps/SAR
            filter_parts.append(
                f"[{vi}:v]setpts=PTS-STARTPTS,"
                f"scale={src_w}:{src_h}:force_original_aspect_ratio=decrease,"
                f"pad={src_w}:{src_h}:(ow-iw)/2:(oh-ih)/2,"
                f"setsar=1,"
                f"fps=60[v{i}]"
            )

            # Audio
            audio_chain = f"[{ai}:a]asetpts=PTS-STARTPTS"
            fades = []
            if fi > 0:
                fades.append(f"afade=t=in:st=0:d={fi:.3f}")
            if fo > 0:
                fo_start = max(0.0, dur - fo)
                fades.append(f"afade=t=out:st={fo_start:.3f}:d={fo:.3f}")
            if fades:
                audio_chain += "," + ",".join(fades)
            audio_chain += f"[a{i}]"
            filter_parts.append(audio_chain)


        # ── 2. Concat semua segmen ────────────────────────────────────────────
        concat_in = "".join(f"[v{i}][a{i}]" for i in range(n))
        filter_parts.append(
            f"{concat_in}concat=n={n}:v=1:a=1[vcat][acat]"
        )

        # ── 3. Crop ───────────────────────────────────────────────────────────
        filter_parts.append(
            f"[vcat]crop=w={crop.width}:h={crop.height}:x={crop.x}:y={crop.y}[vcrop]"
        )

        # ── 4. Subtitle (ASS) ─────────────────────────────────────────────────
        if ass_path and Path(ass_path).exists():
            escaped = self._escape_ass_path(ass_path)
            filter_parts.append(f"[vcrop]ass='{escaped}'[vout]")
            video_map = "[vout]"
        else:
            video_map = "[vcrop]"

        # ── 5. Susun sisa command ─────────────────────────────────────────────
        filter_complex = ";\n".join(filter_parts)

        cmd += [
            "-filter_complex", filter_complex,
            "-map", video_map,
            "-map", "[acat]",
        ]
        cmd += self._encode_flags(out)
        cmd.append(output_path)
        return cmd

    # ─── No Hook ─────────────────────────────────────────────────────────────────

    def _build_no_hook(
        self,
        timeline: Timeline,
        video_path: str,
        output_path: str,
        intro_path: str | None = None,
    ) -> List[str]:
        """
        Mode tanpa hook: single atau dua input (intro + video).
        Jika ada intro, concat intro + full video.
        Jika tidak ada, crop + subtitle saja (stream copy audio).
        """
        crop = timeline.crop
        out  = timeline.output
        ass_path = timeline.subtitle.ass_file

        has_intro = any(s.label == "intro" for s in timeline.segments)

        if has_intro:
            # ── Ada intro: build mirip with_hook (multi-input concat) ─────────
            segments = timeline.segments
            n = len(segments)

            cmd = ["ffmpeg", "-y"]
            video_in_idx = {}
            audio_in_idx = {}
            cur_idx = 0

            for i, seg in enumerate(segments):
                ss  = seg.start_ms / 1000
                dur = seg.duration_ms / 1000
                src = intro_path if (seg.label == "intro" and intro_path) else video_path
                cmd += ["-ss", f"{ss:.3f}", "-t", f"{dur:.3f}", "-i", src]
                video_in_idx[i] = cur_idx
                if seg.has_audio:
                    audio_in_idx[i] = cur_idx
                cur_idx += 1

                if not seg.has_audio:
                    cmd += [
                        "-f", "lavfi",
                        "-t", f"{dur:.3f}",
                        "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                    ]
                    audio_in_idx[i] = cur_idx
                    cur_idx += 1

            src_w = crop.src_width  if crop.src_width  > 0 else (crop.width if crop.width > 0 else 1920)
            src_h = crop.src_height if crop.src_height > 0 else (crop.height if crop.height > 0 else 1080)

            filter_parts = []
            for i, seg in enumerate(segments):
                vi = video_in_idx[i]
                ai = audio_in_idx[i]
                filter_parts.append(
                    f"[{vi}:v]setpts=PTS-STARTPTS,"
                    f"scale={src_w}:{src_h}:force_original_aspect_ratio=decrease,"
                    f"pad={src_w}:{src_h}:(ow-iw)/2:(oh-ih)/2,"
                    f"setsar=1,"
                    f"fps=60[v{i}]"
                )
                filter_parts.append(f"[{ai}:a]asetpts=PTS-STARTPTS[a{i}]")

            concat_in = "".join(f"[v{i}][a{i}]" for i in range(n))
            filter_parts.append(f"{concat_in}concat=n={n}:v=1:a=1[vcat][acat]")
            filter_parts.append(
                f"[vcat]crop=w={crop.width}:h={crop.height}:x={crop.x}:y={crop.y}[vcrop]"
            )

            if ass_path and Path(ass_path).exists():
                escaped = self._escape_ass_path(ass_path)
                filter_parts.append(f"[vcrop]ass='{escaped}'[vout]")
                video_map = "[vout]"
            else:
                video_map = "[vcrop]"

            cmd += [
                "-filter_complex", ";\n".join(filter_parts),
                "-map", video_map,
                "-map", "[acat]",
            ]
            cmd += self._encode_flags(out)
            cmd.append(output_path)
            return cmd

        else:
            # ── Tidak ada intro: single input, audio copy ────────────────────
            filter_parts = []
            filter_parts.append(
                f"[0:v]crop=w={crop.width}:h={crop.height}:x={crop.x}:y={crop.y}[vcrop]"
            )
            if ass_path and Path(ass_path).exists():
                escaped = self._escape_ass_path(ass_path)
                filter_parts.append(f"[vcrop]ass='{escaped}'[vout]")
                video_map = "[vout]"
            else:
                video_map = "[vcrop]"

            cmd = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-filter_complex", ";\n".join(filter_parts),
                "-map", video_map,
                "-map", "0:a",
                "-c:a", "copy",
            ]
            cmd += self._encode_flags(out)
            cmd.append(output_path)
            return cmd

    # ─── Helpers ─────────────────────────────────────────────────────────────────

    def _encode_flags(self, out) -> List[str]:
        """
        Flag encode video — codec-aware.

        NVENC (h264_nvenc / hevc_nvenc / av1_nvenc):
          - Tidak mendukung -crf → pakai -rc vbr + -cq (setara CRF)
          - Preset berbeda: p1 (fastest) … p7 (slowest). p4 = balanced.
          - Tidak perlu -threads (dikontrol driver GPU)

        libx264 / libx265 (software):
          - Pakai -crf + -preset standar (ultrafast…veryslow)
          - -threads 4 untuk batasi CPU
        """
        nvenc_codecs = ("h264_nvenc", "hevc_nvenc", "av1_nvenc")

        if out.codec in nvenc_codecs:
            # NVENC: quality via -cq (0=auto, 1=best, 51=worst; ~23 = good)
            flags = [
                "-c:v",   out.codec,
                "-rc",    "vbr",         # Variable Bitrate mode (mendukung -cq)
                "-cq",    str(out.crf),  # setara CRF untuk NVENC
                "-preset", "p4",         # p4 = balanced speed/quality untuk NVENC
                "-b:v",   "0",           # bitrate 0 = biarkan -cq yang kontrol
            ]
        else:
            # Software codec (libx264, libx265, dll)
            flags = [
                "-c:v",    out.codec,
                "-crf",    str(out.crf),
                "-preset", out.preset,
                "-threads", "4",
            ]

        return flags

    @staticmethod
    def _escape_ass_path(path: str) -> str:
        """
        Escape path untuk FFmpeg ass filter.
        Windows: drive letter colon harus di-escape -> C\\:/path/to/file
        Spasi dan karakter khusus lainnya di-escape.
        """
        p = path.replace("\\", "/")
        # Escape drive letter colon: "C:" → "C\:"
        p = re.sub(r"^([A-Za-z]):", r"\1\\:", p)
        # Escape spasi dan karakter khusus FFmpeg
        p = p.replace("'", "\\'")
        return p

    def command_to_string(self, cmd: List[str]) -> str:
        """Konversi argv list ke string yang mudah dibaca (untuk logging)."""
        parts = []
        i = 0
        while i < len(cmd):
            arg = cmd[i]
            if arg == "-filter_complex" and i + 1 < len(cmd):
                parts.append("-filter_complex")
                parts.append(f'"\n{cmd[i+1]}\n"')
                i += 2
            else:
                if " " in arg or ";" in arg:
                    parts.append(f'"{arg}"')
                else:
                    parts.append(arg)
                i += 1
        return " \\\n  ".join(parts)
