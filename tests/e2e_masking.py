#!/usr/bin/env python3
"""Verifikasi end-to-end: render pipeline dengan masking aktif.

Membuat clip pendek dari sumber, render lewat FFmpegRenderer/TimelineBuilder
dengan masking_enabled, lalu ukur fingerprint source vs hasil render.
"""
import sys, tempfile, subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from renderer.timeline_builder import TimelineBuilder, AudioInfo
from renderer.command_builder import FFmpegCommandBuilder
from renderer.ffmpeg_renderer import FFmpegRenderer

FP = Path(__file__).resolve().parent.parent / "resources" / "bin" / "fpcalc.exe"

def fp(path):
    import json
    out = subprocess.check_output([str(FP), "-json", str(path)], text=True)
    return json.loads(out)

def bits(s):
    import base64
    s += "=" * (-len(s) % 4)
    return "".join(f"{c:08b}" for c in base64.urlsafe_b64decode(s))

def dist(a, b):
    ba, bb = bits(a), bits(b)
    n = min(len(ba), len(bb))
    if n == 0: return 1.0
    return sum(1 for i in range(n) if ba[i] != bb[i]) / n

def main():
    src = sys.argv[1]
    tmp = Path(tempfile.mkdtemp(prefix="e2e-mask-"))
    clip = tmp / "clip.mp4"

    # Potong 20 detik pertama (dengan audio) biar cepat
    subprocess.run(["ffmpeg", "-y", "-i", src, "-t", "20",
                    "-c", "copy", str(clip)], check=True, capture_output=True)

    # Build timeline tanpa hook — full segment, masking aktif
    builder = TimelineBuilder({})
    ai = AudioInfo(fade_in_ms=0, fade_out_ms=0, crossfade_ms=0,
                   masking_enabled=True, masking_intensity=0.5)
    timeline = builder.build_no_hook(
        edit_plan=None, video_duration_ms=20_000,
        video_src_width=538, video_src_height=268,
        subtitle_ass_path="", )
    timeline.audio = ai

    cmd_builder = FFmpegCommandBuilder()
    outp = tmp / "render-masked.mp4"
    cmd = cmd_builder.build(timeline, str(clip), str(outp))
    subprocess.run(cmd, check=True, capture_output=True, text=True)

    d = dist(fp(str(clip))["fingerprint"], fp(str(outp))["fingerprint"])
    print(f"source={clip.name} ({fp(str(clip))['duration']}s)")
    print(f"render-masked={outp.name} ({fp(str(outp))['duration']}s)")
    print(f"distance = {d:.4f}  {'OK (>=0.01)' if d >= 0.01 else 'WEAK (<0.01)'}")

if __name__ == "__main__":
    main()