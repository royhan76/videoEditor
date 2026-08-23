#!/usr/bin/env python3
"""
anti-claim-render.py — Render video dengan Anti-Claim Ultra recipe.
Resep: Audio Masking L6 + Visual L7 + Mirror (hflip).
Recipe teruji lolos Content ID YouTube (TEST_KISAH_mask6_vis7.mp4 + MIRROR variant).

Cara pakai:
  python anti-claim-render.py <input.mp4> <output.mp4> [start_sec] [duration_sec]

Contoh:
  python anti-claim-render.py "D:/downloads/kisah.mp4" "D:/output/hasil.mp4" 0 180
  python anti-claim-render.py "D:/downloads/kisah_akhir3min.mp4" "D:/output/hasil.mp4"

Default: full duration, no trim.
"""
import sys, os, subprocess

# ============ KONFIGURASI RESEP ============
# Audio Masking Level 6 (lolos DRM)
AUDIO_FILTER = (
    "asetrate=44100*1.241858,"    # pitch +3.75 semitone
    "aresample=44100,"
    "atempo=0.805245,"             # compensate tempo
    "equalizer=f=2000:t=q:w=2:g=-9,"  # notch -9dB @ 2kHz
    "lowpass=f=15000,"
    "aecho=0.8:0.9:50|110:0.30|0.21"  # reverb tipis
)

# Visual Level 7 + Mirror (lolos DRM)
# Crop asimetris: lebar -11%, tinggi -30% → aspek 2.075
# Scale pertahankan aspek crop (NOT scale balik ke asli)
# hflip = mirror horizontal (kunci rontokkin Content ID visual)
VISUAL_FILTER = (
    "hflip,"
    "crop=1436:692:88:150,"       # crop asimetris dari 1614x994
    "scale=1614:776,"             # pertahankan aspek 2.08
    "eq=contrast=1.10:saturation=1.10,"
    "noise=alls=10:allf=t+u"
)

# Encode settings (CPU libx264, 930MX no NVENC)
VIDEO_CODEC = ["-c:v", "libx264", "-crf", "23", "-preset", "veryfast", "-threads", "4"]
AUDIO_CODEC = ["-c:a", "aac", "-b:a", "192k"]
# ============ END KONFIGURASI ============


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]
    start = sys.argv[3] if len(sys.argv) > 3 else None
    duration = sys.argv[4] if len(sys.argv) > 4 else None

    if not os.path.exists(input_path):
        print(f"ERROR: input tidak ditemukan: {input_path}")
        sys.exit(1)

    # Build filter complex
    # Video: scale ke 1920x1080 (normalize) → crop margin → visual treatment
    # Audio: masking chain
    filter_complex = (
        f"[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,"
        f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=60,"
        f"crop=1614:994:153:43,"           # app crop margin (8/8/4/10)
        f"{VISUAL_FILTER}"
        f"[vout];"
        f"[0:a]{AUDIO_FILTER}[aout]"
    )

    cmd = ["ffmpeg", "-y"]

    # Trim flags
    if start is not None:
        cmd += ["-ss", str(start)]
    if duration is not None:
        cmd += ["-t", str(duration)]

    cmd += [
        "-i", input_path,
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-map", "[aout]",
    ] + VIDEO_CODEC + AUDIO_CODEC + [output_path]

    print("=== ANTI-CLAIM RENDER ===")
    print(f"  input  : {input_path}")
    print(f"  output : {output_path}")
    if start:    print(f"  start  : {start}s")
    if duration: print(f"  dur    : {duration}s")
    print(f"  recipe : Audio L6 + Visual L7 + Mirror (hflip)")
    print()

    r = subprocess.run(cmd)
    if r.returncode == 0:
        print(f"\n DONE: {output_path}")
        print(f" Upload ke YouTube untuk verifikasi Content ID.")
    else:
        print(f"\n FAIL: ffmpeg exit {r.returncode}")
        sys.exit(1)


if __name__ == "__main__":
    main()