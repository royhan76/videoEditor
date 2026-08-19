# placeholder mouth images (transparent background)
# state0: closed – simple line
# state1: small – short line
# state2: wide – long line

from pathlib import Path
from PIL import Image, ImageDraw

out_dir = Path(r"E:/PROJECT/desktop/videoEditor/assets/avatar")
out_dir.mkdir(parents=True, exist_ok=True)

w, h = 200, 100  # size of mouth canvas
for i, name in enumerate(["state0.png","state1.png","state2.png"]):
    img = Image.new("RGBA", (w, h), (0,0,0,0))
    d = ImageDraw.Draw(img)
    y = h//2
    if i==0:
        d.line((w//2-30, y, w//2+30, y), fill="black", width=8)  # closed line
    elif i==1:
        d.line((w//2-20, y, w//2+20, y), fill="black", width=8)  # small
    else:
        d.line((w//2-40, y, w//2+40, y), fill="black", width=8)  # wide
    img.save(out_dir / name)
print("mouth placeholders saved")
