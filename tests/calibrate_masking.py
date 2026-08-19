#!/usr/bin/env python3
"""Kalibrasi audio masking — ukur fingerprint distance tiap intensity.

Verifikasi renderer/command_builder._build_audio_masking_filter:
  - intensity 1-3, 5, 8, 10 → distance harus >= 0.01 (editstrength threshold)
  - kontrol: tanpa masking → distance ~0

Pakai:
  python tests/calibrate_masking.py <video_dengan_audio.mp4>
"""
import shutil, subprocess, sys, tempfile
from pathlib import Path

FP = Path(__file__).resolve().parent.parent / "resources" / "bin" / "fpcalc.exe"
if not FP.exists():
    # fallback: cari fpcalc global
    FP = shutil.which("fpcalc")
    if not FP:
        sys.exit("fpcalc.exe tidak ditemukan")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from renderer.command_builder import FFmpegCommandBuilder

def fp(path):
    out = subprocess.check_output([str(FP), "-json", str(path)], text=True)
    import json
    data = json.loads(out)
    return {"fingerprint": data.get("fingerprint") or data.get("Fingerprint") or data.get("finger_print", ""),
            "duration": data.get("duration") or data.get("Duration") or 0}

def bits(s):
    import base64
    # Chromaprint base64 URL-safe (- dan _), perlu padding
    s += "=" * (-len(s) % 4)
    return "".join(f"{c:08b}" for c in base64.urlsafe_b64decode(s))

def dist(a, b):
    ba, bb = bits(a), bits(b)
    n = min(len(ba), len(bb))
    if n == 0: return 1.0
    return sum(1 for i in range(n) if ba[i] != bb[i]) / n

def main():
    src = sys.argv[1]
    builder = FFmpegCommandBuilder()
    tmp = Path(tempfile.mkdtemp(prefix="maskcal-"))

    # kontrol: tanpa masking
    cmd = builder.build(
        timeline=None,  # dipanggil langsung via helper
        video_path=src, output_path=str(tmp / "none.mp4")
    ) if False else None
    # panggil builder private — butuh AudioInfo; simulasi dgn filter langsung
    from renderer.timeline_builder import AudioInfo
    results = {}
    for level in [1, 3, 5, 7, 8, 10]:
        ai = AudioInfo(fade_in_ms=0, fade_out_ms=0, crossfade_ms=0,
                       masking_enabled=True, masking_intensity=level)
        chain = builder._build_audio_masking_filter(ai)
        outp = tmp / f"mask-{level}.wav"
        filt = f"[0:a]{chain}[a]"
        subprocess.run(["ffmpeg", "-y", "-i", src,
                        "-filter_complex", filt, "-map", "[a]",
                        "-c:a", "pcm_s16le", str(outp)],
                       check=True, capture_output=True)
        results[level] = (chain, str(outp))

    orig_fp = fp(src)["fingerprint"]
    print(f"Sumber: {src} — fp {len(orig_fp)} chars")
    print(f"{'lvl':>4} {'distance':>9}  chain")
    for lvl, (chain, path_) in results.items():
        d = dist(orig_fp, fp(path_)["fingerprint"])
        flag = "OK" if d >= 0.01 else "WEAK!"
        print(f"{lvl:>4} {d:>9.4f}  {flag}  {chain}")
    shutil.rmtree(tmp, ignore_errors=True)

if __name__ == "__main__":
    main()