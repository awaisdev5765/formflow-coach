from pathlib import Path
from PIL import Image


root = Path(__file__).resolve().parent
source = Image.open(root / "assets" / "app-icon.png").convert("RGBA")
source.save(root / "assets" / "app-icon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
source.save(root / "assets" / "app-icon.icns", format="ICNS")

iconset = root / "assets" / "AppIcon.iconset"
iconset.mkdir(exist_ok=True)
for size in (16, 32, 128, 256, 512):
    source.resize((size, size), Image.Resampling.LANCZOS).save(iconset / f"icon_{size}x{size}.png")
    source.resize((size * 2, size * 2), Image.Resampling.LANCZOS).save(iconset / f"icon_{size}x{size}@2x.png")
print("PNG, ICO, and ICNS created.")
