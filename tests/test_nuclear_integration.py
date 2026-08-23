"""Smoke test Nuclear V2 integration: timeline -> command -> real ffmpeg 1s render."""
import subprocess, sys, json
from pathlib import Path

sys.path.insert(0, r"E:\PROJECT\desktop\videoEditor")
from renderer.timeline_builder import TimelineBuilder, VisualInfo, AudioInfo, mode_b_audio_filter
from renderer.command_builder import FFmpegCommandBuilder

# ── 1. VisualInfo nuclear chain sesuai resep terbukti ──
v = VisualInfo(enabled=True, mode="nuclear", mirror_enabled=True)
vf = v.vf_suffix(1920, 1080)
assert v.speed_factor == 1.25
assert "hflip," in vf and "perspective=x0=20:y0=20:x1=1900:y1=10:x2=10:y2=1070:x3=1910:y3=1060" in vf, vf
assert "crop=w='iw*0.5760':h='ih*0.5760'" in vf, vf
assert "scale=1536:864," in vf and "rotate=2.00*PI/180" in vf, vf
assert "hue=h=40.0:s=1.4,eq=contrast=1.15:saturation=1.2,noise=alls=18:allf=t+u" in vf, vf
assert "setpts=0.800000*PTS,fps=30" in vf, vf

# ── 2. Mode B audio: total speed harus == speed video (sync rule) ──
af = mode_b_audio_filter(1.05, 1.25)
assert af == "asetrate=44100*1.050000,aresample=44100,atempo=1.190476", af
assert abs(1.05 * 1.190476 - 1.25) < 1e-4  # produk faktor = 1.25

# custom pitch/speed juga sinkron
af2 = mode_b_audio_filter(1.06, 1.33)
assert abs(1.06 * float(af2.split("atempo=")[1]) - 1.33) < 1e-4

# ── 3. Full timeline + command (no hook path, ada audio) ──
cfg = {
    "crop": {"enabled": True, "left_pct": 8, "right_pct": 8, "top_pct": 4, "bottom_pct": 10},
    "audio": {"fade_in": 300, "fade_out": 300, "crossfade": 400,
              "masking_enabled": True, "masking_intensity": 6,
              "masking_mode": "mode_b", "pitch_ratio": 1.05},
    "visual": {"enabled": True, "level": 7, "mirror_enabled": True, "mode": "nuclear"},
    "render": {"codec": "libx264", "fallback_codec": "libx264", "crf": 22,
               "preset": "veryfast", "output_format": "mp4"},
}
tb = TimelineBuilder(cfg)
tl = tb.build_no_hook(None, 10_000, 1280, 720, "", 0, True)
cmd = FFmpegCommandBuilder().build(tl, "tmp_src.mp4", "out_test.mp4")
fc = cmd[cmd.index("-filter_complex") + 1]
assert "mode_b" not in fc
assert "asetrate=44100*1.050000,aresample=44100,atempo=1.190476" in fc, fc
assert "[0:v]crop=" in fc or "crop=w=" in fc  # crop tetap jalan sebelum nuclear chain
print("== FILTER_COMPLEX ==")
print(fc)

# ── 4. Real ffmpeg: 1s synthetic source (video+audio satu file) ──
work = Path(__file__).parent / "_nuclear_smoke"
work.mkdir(exist_ok=True)
src = work / "src.mp4"
if not src.exists():
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=1280x720:rate=60:duration=1",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
        "-c:v", "libx264", "-c:a", "aac", "-shortest", str(src)
    ], capture_output=True, check=True)

cmd = FFmpegCommandBuilder().build(tl, str(src), str(work / "out.mp4"))
r = subprocess.run(cmd, capture_output=True, text=True)
if r.returncode != 0:
    print(r.stderr[-3000:])
    sys.exit("FFMPEG FAIL")
p = subprocess.run(["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams",
                    str(work / "out.mp4")], capture_output=True, text=True)
streams = json.loads(p.stdout)["streams"]
vs = [s for s in streams if s["codec_type"] == "video"][0]
as_ = [s for s in streams if s["codec_type"] == "audio"][0]
dur_v = float(vs.get("duration", 0))
print(f"video: {vs['width']}x{vs['height']} fps={vs.get('avg_frame_rate')} dur={dur_v:.2f}s")
print(f"audio: {as_.get('sample_rate')}Hz dur={as_.get('duration')}")
# Output harus 1536x864 (resep), fps 30, durasi ~0.8s (1s @1.25x)
assert (vs["width"], vs["height"]) == (1536, 864), vs
assert abs(dur_v - 0.8) < 0.15, dur_v
assert abs(float(as_.get("duration", 0)) - dur_v) < 0.15  # A/V sync

# ── 5. Subtitle remap ikut speed ──
from renderer.ffmpeg_renderer import FFmpegRenderer
from subtitle.extractor import SubtitleEntry
rend = FFmpegRenderer(cfg, preset_dir="")
tl2 = tb.build_no_hook(None, 10_000, 1920, 1080, "", 0, True)
entries = [SubtitleEntry(index=1, start_ms=1000, end_ms=2000, text="tes")]
remapped = rend._remap_subtitles(tl2, entries)
assert len(remapped) == 1
assert remapped[0].start_ms == 800 and remapped[0].end_ms == 1600, remapped[0]

print("\nALL PASS")
