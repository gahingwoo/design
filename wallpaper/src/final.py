"""Render one wallpaper.

    python3 final.py <WxH> <dark|light> [scale]

Writes ../<mode>/gahingwoo-ridge-<WxH>-<mode>[@<scale>x].png and, at scale 1, the
vector master ../svg/gahingwoo-ridge-<WxH>-<mode>.svg. Every rule in ridge.py and
common.py is an assertion: if a framing or palette breaks one, nothing is written.
"""
import pathlib
import shutil
import sys
import tempfile
import time

from formats import FORMATS, FORMATS_LIGHT
from ridge import DARK, LIGHT, PAL_DARK_R3, PAL_LIGHT, make

n, mode = sys.argv[1], sys.argv[2]
scale = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
w, h, fr = (FORMATS if mode == "dark" else FORMATS_LIGHT)[n]
theme, pal = (DARK, PAL_DARK_R3) if mode == "dark" else (LIGHT, PAL_LIGHT)
suffix = "" if scale == 1 else f"@{scale:g}x"
name = f"gahingwoo-ridge-{n}-{mode}{suffix}"

here = pathlib.Path(__file__).resolve().parent
t = time.time()
with tempfile.TemporaryDirectory() as tmp:
    png = pathlib.Path(tmp) / f"{name}.png"
    info = make(w, h, fr, str(png), scale=scale, theme=theme, pal=pal)
    (here.parent / mode).mkdir(exist_ok=True)
    shutil.move(png, here.parent / mode / png.name)
    if scale == 1:
        (here.parent / "svg").mkdir(exist_ok=True)
        shutil.move(png.with_suffix(".svg"), here.parent / "svg" / f"{name}.svg")
print(n, mode, suffix or "@1x", f"focal ratio {info['sky']/info['summit']:.2f}",
      f"sig {info['contrast']:.2f}", f"{time.time()-t:.0f}s", flush=True)
