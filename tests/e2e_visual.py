#!/usr/bin/env python3
"""Verifikasi visual masking — ukur pixel/ssim distance vs source.

Bukan fingerprint audio — visual match Content ID pakai pixel hash.
Ukur pakai perceptual diff (psnr/ssim) buat pastikan video beneran berubah.
"""
import sys, subprocess, tempfile, shutil
from pathlib import Path

APP = Path(r"E:\PROJECT\desktop\videoEditor")
SRC = APP / "output" / "render_klip_GUS_IQDAM_KESIKSO_NGAKAK_PARAH_PEMUDA_GARANGAN_MASUK_PLOSO_BARENG_GUS_AZMI.mp4"
sys.path.insert(0, str(APP))
from renderer.timeline_builder import TimelineBuilder, AudioInfo, VisualInfo
from renderer.command_builder import FFmpegCommandBuilder

def ffmpeg_diff(a, b):
    """PSNR/SSIM via ffmpeg -i ref -i src -lavfi psnr/ssim -f null -"""
    r = subprocess.run(
        ["ffmpeg", "-y", "-i", a, "-i", b,
         "-lavfi", "psnr=stats_file=-", "-f", "null", "-"],
        capture_output=True, text=True)
    psnr = "n/a"
    for line in r.stderr.splitlines():
        if "psnr_avg:" in line:
            for tok in line.split():
                if tok.startswith("psnr_avg:"):
                    try: psnr = tok.split(":")[1].rstrip(","); break
                    except: pass
    return psnr

fail = []

# Test 1: Visual OFF → output identik → PSNR tinggi (no change)
print("[1/4] Build cmd visual=OFF (kontrol)")
tmp = Path(tempfile.mkdtemp(prefix="vis-off-"))
subprocess.run(["ffmpeg","-y","-i",str(SRC),"-t","10","-c","copy",str(tmp/"clip.mp4")], capture_output=True, check=True)
tb = TimelineBuilder({})
ai = AudioInfo(fade_in_ms=0, fade_out_ms=0, crossfade_ms=0, masking_enabled=False, masking_intensity=0.5)
tl = tb.build_no_hook(None, 10000, 538, 268, "")
tl.audio = ai; tl.visual = VisualInfo(enabled=False, level=5)
tl.output.codec = "libx264"; tl.output.crf = 23; tl.output.preset = "ultrafast"
out = tmp / "off.mp4"
cmd = FFmpegCommandBuilder().build(tl, str(tmp/"clip.mp4"), str(out))
r = subprocess.run(cmd, capture_output=True, text=True)
ok = r.returncode == 0
print(f"  rc={r.returncode} {'PASS' if ok else 'FAIL'}")
if ok:
    psnr = ffmpeg_diff(str(tmp/"clip.mp4"), str(out))
    print(f"  PSNR(visual=off): {psnr} dB (harusnya tinggi = hampir sama)")
shutil.rmtree(tmp, ignore_errors=True)

# Test 2: Visual ON level 5 → output beda → PSNR lebih rendah
print("[2/4] Build cmd visual=ON level 5")
tmp = Path(tempfile.mkdtemp(prefix="vis-on-"))
subprocess.run(["ffmpeg","-y","-i",str(SRC),"-t","10","-c","copy",str(tmp/"clip.mp4")], capture_output=True, check=True)
tl2 = tb.build_no_hook(None, 10000, 538, 268, "")
tl2.audio = ai; tl2.visual = VisualInfo(enabled=True, level=5)
tl2.output.codec = "libx264"; tl2.output.crf = 23; tl2.output.preset = "ultrafast"
out2 = tmp / "on.mp4"
cmd2 = FFmpegCommandBuilder().build(tl2, str(tmp/"clip.mp4"), str(out2))
r = subprocess.run(cmd2, capture_output=True, text=True)
ok = r.returncode == 0
print(f"  rc={r.returncode} {'PASS' if ok else 'FAIL'}")
if ok:
    psnr = ffmpeg_diff(str(tmp/"clip.mp4"), str(out2))
    print(f"  PSNR(visual=on lvl5): {psnr} dB (harusnya lebih rendah dari OFF = video berubah)")
    if not fail:
        try:
            v = float(psnr)
            if v > 35: fail.append("visual-on level5: PSNR tinggi, kemungkinan filter gak kepake")
        except: pass
shutil.rmtree(tmp, ignore_errors=True)

# Test 3: Visual ON level 10 → lebih beda lagi
print("[3/4] Build cmd visual=ON level 10")
tmp = Path(tempfile.mkdtemp(prefix="vis-max-"))
subprocess.run(["ffmpeg","-y","-i",str(SRC),"-t","10","-c","copy",str(tmp/"clip.mp4")], capture_output=True, check=True)
tl3 = tb.build_no_hook(None, 10000, 538, 268, "")
tl3.audio = ai; tl3.visual = VisualInfo(enabled=True, level=10)
tl3.output.codec = "libx264"; tl3.output.crf = 23; tl3.output.preset = "ultrafast"
out3 = tmp / "max.mp4"
cmd3 = FFmpegCommandBuilder().build(tl3, str(tmp/"clip.mp4"), str(out3))
r = subprocess.run(cmd3, capture_output=True, text=True)
ok = r.returncode == 0
print(f"  rc={r.returncode} {'PASS' if ok else 'FAIL'}")
if ok:
    psnr = ffmpeg_diff(str(tmp/"clip.mp4"), str(out3))
    print(f"  PSNR(visual=on lvl10): {psnr} dB (harusnya paling rendah)")
shutil.rmtree(tmp, ignore_errors=True)

# Test 4: Generated filter check — pastikan vfx masuk command
print("[4/4] Verify vf_suffix masuk command line")
tb4 = TimelineBuilder({})
tl4 = tb4.build_no_hook(None, 10000, 538, 268, "")
tl4.audio = ai; tl4.visual = VisualInfo(enabled=True, level=5)
tl4.output.codec = "libx264"
cmd4 = FFmpegCommandBuilder().build(tl4, "x.mp4", "y.mp4")
fc_idx = cmd4.index("-filter_complex") + 1
fc = cmd4[fc_idx]
ok = "noise=alls=" in fc and "eq=contrast" in fc and "crop=" in fc
print(f"  filter_complex contains visual filters: {'PASS' if ok else 'FAIL'}")
if not ok: fail.append("visual filters not in command")

print(f"\n{'ALL PASS' if not fail else 'FAIL: ' + ', '.join(fail)}")
sys.exit(1 if fail else 0)