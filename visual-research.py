#!/usr/bin/env python3
"""
visual-research.py — Riset visual murni (audio copy).
Ukur similarity visual antara source dan varian treatment pakai MPEG-7 signature.
Rank semua varian, terendah = paling beda dari source.

Usage:
  python visual-research.py              # run all variants
  python visual-research.py --quick      # 30s sample only
"""
import sys, os, subprocess, json, tempfile
from pathlib import Path

SRC = Path(r"D:/WEB/project_rekomendasi/worker-python/downloads/clips/klip_KISAH_SANTRI_TERJAUH_PLOSO_PAPUA_MERAUKE_PENGHALANG_DOA_TERJAWAB_GUS_IQDAM_NGEGAS_akhir3min.mp4")
OUTDIR = Path(r"E:/PROJECT/desktop/videoEditor/output/research")
OUTDIR.mkdir(parents=True, exist_ok=True)

# ── Varian resep visual ──────────────────────────────────────────
# Semua audio copy. Fokus: geometri + warna + noise.
VARIANTS = {
    # Baseline: tanpa treatment (harus similarity ~1.0)
    "00_raw": "",

    # A: Mirror only
    "A_mirror": "hflip",

    # B: Deep crop aspek 2.16 + mirror
    "B_crop_mirror": "hflip,crop=1300:600:310:240,scale=1614:744",

    # C: Warp perspective + mirror + crop
    "C_warp": ("hflip,"
               "perspective=x0=20:y0=20:x1=1900:y1=10:x2=10:y2=1070:x3=1910:y3=1060:sense=destination,"
               "crop=1400:680:260:200,scale=1614:784"),

    # D: Zoompan slow zoom in (geometri berubah per frame)
    "D_zoompan": ("hflip,zoompan=z='min(zoom+0.0005,1.15)':d=1:"
                  "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1614x780"),

    # E: Rotate slight + crop (rotasi 1.5 derajat)
    "E_rotate": ("hflip,rotate=1.5*PI/180:fillcolor=black,"
                 "crop=1500:760:210:160,scale=1614:816"),

    # F: Zoompan + Rotate (lebih ringan dari nuclear_visual lama)
    "F_zoompan_rotate": ("hflip,"
                         "zoompan=z='min(zoom+0.0005,1.15)':d=1:"
                         "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1614x780,"
                         "rotate=1*PI/180:fillcolor=black"),

    # G: Hue rotation besar (warna total beda)
    "G_hue": ("hflip,crop=1440:694:240:193,scale=1614:778,"
              "hue=h=45:s=1.5,eq=contrast=1.15:saturation=1.15,"
              "noise=alls=10:allf=t+u"),

    # H: Vignette (gelap pinggir) + Mirror + Crop
    "H_vignette": ("hflip,crop=1400:680:260:200,scale=1614:784,"
                  "vignette=angle=PI/4:mode=backward,eq=contrast=1.10,"
                  "noise=alls=8:allf=t+u"),
}

QUICK_SECONDS = 30


def render_variant(name: str, vf: str, quick: bool) -> Path:
    out = OUTDIR / f"{name}.mp4"
    base = "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=60"
    full_vf = f"{base},{vf}" if vf else base

    cmd = ["ffmpeg", "-y", "-i", str(SRC)]
    if quick:
        cmd += ["-ss", "60", "-t", str(QUICK_SECONDS)]
    cmd += [
        "-filter_complex", f"[0:v]{full_vf}[vout]",
        "-map", "[vout]", "-map", "0:a",
        "-c:v", "libx264", "-crf", "23", "-preset", "veryfast", "-threads", "4",
        "-c:a", "copy",
        str(out)
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  [FAIL] {name}: {r.stderr[-300:]}")
        return None
    return out


def measure_similarity(vid_a: Path, vid_b: Path) -> float:
    """MPEG-7 signature matching score. Lower = more different."""
    r = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(vid_a), "-i", str(vid_b),
         "-filter_complex", "signature=detectmode=full:nb_inputs=2",
         "-f", "null", "-"],
        capture_output=True, text=True, timeout=300
    )
    # Parse "matching of video 0 at X.XXXXX and video 1 at X.XXXXX" scores
    import re
    scores = []
    for m in re.finditer(r"matching of video (\d) at ([\d.]+) and video (\d) at ([\d.]+)", r.stderr):
        pass
    # Simpler: look for similarity score lines
    for line in r.stderr.splitlines():
        if "similarity" in line.lower() or "score" in line.lower():
            print(f"    {line.strip()}")
    # fallback: count matches
    matches = len(re.findall(r"matching of video", r.stderr))
    return matches


def main():
    quick = "--quick" in sys.argv
    print(f"=== VISUAL RESEARCH {'(QUICK 30s)' if quick else '(FULL)'} ===\n")

    results = {}
    for name, vf in VARIANTS.items():
        print(f"[{name}] rendering...")
        out = render_variant(name, vf, quick)
        if out is None:
            continue
        results[name] = out

    # Compare each variant vs raw baseline AND vs source directly
    print("\n=== SIMILARITY vs SOURCE ===")
    src_sample = OUTDIR / "_src_sample.mp4"
    if quick:
        subprocess.run(["ffmpeg", "-y", "-i", str(SRC), "-ss", "60", "-t", str(QUICK_SECONDS),
                        "-c:v", "libx264", "-crf", "23", "-preset", "veryfast",
                        "-an", str(src_sample)], capture_output=True)
    else:
        subprocess.run(["ffmpeg", "-y", "-i", str(SRC), "-c:v", "libx264", "-crf", "23",
                        "-preset", "veryfast", "-an", str(src_sample)], capture_output=True)

    ranked = []
    for name, path in results.items():
        if name == "00_raw":
            continue
        try:
            n_matches = measure_similarity(src_sample, path)
            ranked.append((name, n_matches))
            print(f"  {name:24s} matches={n_matches}")
        except Exception as e:
            print(f"  {name}: measure fail {e}")

    ranked.sort(key=lambda x: x[1])
    print("\n=== RANKING (lower = lebih beda dari source) ===")
    for name, score in ranked:
        print(f"  {name:24s} {score}")

    best = ranked[0] if ranked else None
    if best:
        print(f"\n>>> BEST VARIANT: {best[0]} (matches={best[1]})")


if __name__ == "__main__":
    main()