#!/usr/bin/env python3
"""Bukti visual treatment beneran ngubah pixel.

Gunakan sinyal MSE/PSNR antar frame (konten identik dgn tanpa filter).
Kalau visual_filter_on != visual_filter_off, ada perubahan.
"""
import sys, subprocess, tempfile, shutil
from pathlib import Path

APP = Path(r"E:\PROJECT\desktop\videoEditor")
SRC = APP / "output" / "render_klip_GUS_IQDAM_KESIKSO_NGAKAK_PARAH_PEMUDA_GARANGAN_MASUK_PLOSO_BARENG_GUS_AZMI.mp4"
sys.path.insert(0, str(APP))
from renderer.timeline_builder import TimelineBuilder, AudioInfo, VisualInfo
from renderer.command_builder import FFmpegCommandBuilder

def psnr(a, b):
    r = subprocess.run(
        ["ffmpeg","-y","-i",a,"-i",b,"-lavfi","psnr","-f","null","-"],
        capture_output=True, text=True)
    for line in r.stderr.splitlines():
        if "psnr_avg" in line:
            for tok in line.split():
                if tok.startswith("average:"):
                    try: return float(tok.split(":")[1])
                    except: pass
    return None

tmp = Path(tempfile.mkdtemp(prefix="vs-"))
subprocess.run(["ffmpeg","-y","-i",str(SRC),"-t","10","-c","copy",str(tmp/"src.mp4")], capture_output=True, check=True)
tb = TimelineBuilder({})
ai = AudioInfo(fade_in_ms=0, fade_out_ms=0, crossfade_ms=0, masking_enabled=False, masking_intensity=0.5)

for tag, vis in [("off", VisualInfo(enabled=False, level=5)), ("lvl5", VisualInfo(enabled=True, level=5)), ("lvl10", VisualInfo(enabled=True, level=10))]:
    tl = tb.build_no_hook(None, 10000, 538, 268, "")
    tl.audio = ai; tl.visual = vis
    tl.output.codec = "libx264"; tl.output.crf = 23; tl.output.preset = "ultrafast"
    out = tmp / f"{tag}.mp4"
    cmd = FFmpegCommandBuilder().build(tl, str(tmp/"src.mp4"), str(out))
    subprocess.run(cmd, capture_output=True, text=True, check=True)
    p = psnr(str(tmp/"src.mp4"), str(out))
    sz = out.stat().st_size
    print(f"{tag:>5}: psnr={p} dB  size={sz} bytes")

shutil.rmtree(tmp, ignore_errors=True)