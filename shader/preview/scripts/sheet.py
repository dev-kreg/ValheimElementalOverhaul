# sheet.py out.png "label|query" ...  — render each query, keep the right (overhaul) viewport, tile 3 across with labels
import sys, subprocess, os
from PIL import Image, ImageDraw
S = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
out, items = sys.argv[1], sys.argv[2:]
tiles = []
for i, it in enumerate(items):
    label, q = it.split("|", 1)
    f = f"{S}/page/_t{i}.png"
    subprocess.run([f"{S}/scripts/lab.sh", q, f, "3000"], check=False)
    im = Image.open(f).convert("RGB")
    side = im.crop((652, 37, 1260, 493)) if "left" not in label else im.crop((25, 37, 634, 493))
    side = side.resize((456, 342))
    d = ImageDraw.Draw(side); d.rectangle((0, 0, 456, 18), fill=(0, 0, 0)); d.text((6, 3), label, fill=(255, 220, 150))
    tiles.append(side)
cols = 3; rows = (len(tiles) + cols - 1) // cols
sheet = Image.new("RGB", (456 * cols, 342 * rows), (20, 20, 20))
for i, t in enumerate(tiles): sheet.paste(t, ((i % cols) * 456, (i // cols) * 342))
sheet.save(out)
