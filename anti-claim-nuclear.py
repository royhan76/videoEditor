#!/usr/bin/env python3
"""
anti-claim-nuclear.py — NUCLEAR OPTION (Level 11).
Kombinasi Warp Geometri + Audio Jitter + Mirror + Deep Asymmetric Crop.
Gunakan hanya jika resep Ultra gagal.
"""
import sys, os, subprocess

# ============ NUCLEAR RECIPE ============
# Audio: Masking 6 + Vibrato (Jitter)
# Vibrato 5Hz depth 0.2 bikin waveform gak stabil bagi AI YT
AUDIO_FILTER = (
    "asetrate=44100*1.241858,"
    "aresample=44100,"
    "atempo=0.805245,"
    "vibrato=f=5:d=0.2,"         
    "equalizer=f=2000:t=q:w=2:g=-10,"
    "lowpass=f=14000,"
    "aecho=0.8:0.88:40|100:0.35|0.25"
)

# Visual: Warp + Mirror + Deep Crop (Aspect 2.2)
# perspective: narik ujung sudut sedikit (warp). Koordinat HARDCODE untuk 1920x1080
# (perspective tidak support iw/ih eval).
VISUAL_FILTER = (
    "hflip,"
    "perspective=x0=10:y0=10:x1=1910:y1=5:x2=20:y2=1075:x3=1915:y3=1070:sense=destination,"
    "crop=1300:590:150:200,"      # Deep Crop Aspek ~2.2
    "scale=1614:734,"             # Preserve Deep Aspect
    "eq=contrast=1.12:saturation=1.15:brightness=0.02,"
    "noise=alls=15:allf=t+u"
)

VIDEO_CODEC = ["-c:v", "libx264", "-crf", "22", "-preset", "veryfast"]
AUDIO_CODEC = ["-c:a", "aac", "-b:a", "192k"]
# ========================================

def main():
    if len(sys.argv) < 3:
        print("Usage: python anti-claim-nuclear.py <input> <output>")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]

    filter_complex = (
        f"[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=59.94,"
        f"{VISUAL_FILTER}[vout];"
        f"[0:a]{AUDIO_FILTER}[aout]"
    )

    cmd = ["ffmpeg", "-y", "-i", input_path, "-filter_complex", filter_complex,
           "-map", "[vout]", "-map", "[aout]"] + VIDEO_CODEC + AUDIO_CODEC + [output_path]

    print("=== NUCLEAR OPTION INITIATED ===")
    r = subprocess.run(cmd)
    if r.returncode == 0:
        print(f"\n DONE: {output_path}")
    else:
        print("\n FAILED")

if __name__ == "__main__":
    main()