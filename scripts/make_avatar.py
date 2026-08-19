# scripts/make_avatar.py
from pathlib import Path
from PIL import Image
import sys

def make_avatar(base_path: Path, mouth_dir: Path, out_dir: Path):
    base = Image.open(base_path).convert("RGBA")
    out_dir.mkdir(parents=True, exist_ok=True)
    for i in range(3):  # 0 closed,1 small,2 wide
        avatar = base.copy()
        mouth_path = mouth_dir / f"state{i}.png"
        if not mouth_path.exists():
            print(f"Mouth image {mouth_path} not found, skip")
            continue
        mouth = Image.open(mouth_path).convert("RGBA")
        # position mouth roughly at lower middle of face
        w, h = base.size
        mw, mh = mouth.size
        # heuristic: 60% height down, centered horizontally
        pos = ((w - mw) // 2, int(h * 0.6))
        avatar.paste(mouth, pos, mouth)
        avatar.save(out_dir / f"avatar_{i}.png")
    print("Combined avatars saved to", out_dir)

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: make_avatar.py <base_photo> <mouth_dir> <out_dir>")
        sys.exit(1)
    base_path = Path(sys.argv[1])
    mouth_dir = Path(sys.argv[2])
    out_dir = Path(sys.argv[3])
    make_avatar(base_path, mouth_dir, out_dir)
