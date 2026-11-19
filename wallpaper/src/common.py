import subprocess, pathlib, base64

W, H = 3840, 2160
DARK = dict(bg="#1A1928", purple="#A98BF0", text="#F4F2FA")
LIGHT = dict(bg="#F4F2F8", purple="#9472DB", text="#17171B")
ROOT = pathlib.Path(__file__).parent
FONT = ROOT / "node_modules/@fontsource/jetbrains-mono/files/jetbrains-mono-latin-800-normal.woff2"

MARK_RECTS = [(0, 0, 350, 70), (70, 70, 140, 140), (210, 70, 280, 140), (0, 210, 350, 280)]


def signature(theme, W=W, H=H):
    """mark + 'gahingwoo', bottom-right. Size follows frame area (1.0 at 3840x2160).
    Returns (svg, bbox + (k,))."""
    k = ((W * H) / (3840 * 2160)) ** 0.5
    margin, mark_h, font, gap = 130 * k, 92 * k, 84 * k, 38 * k
    s = mark_h / 280
    mark_w = 350 * s
    text_w = 9 * font * 0.6 - 9 * 1.1 * k  # JetBrains Mono advance 0.6em, tracking -1.1
    total = mark_w + gap + text_w
    x0 = W - margin - total
    y0 = H - margin - mark_h
    rects = "".join(
        f'<rect x="{a}" y="{b}" width="{c-a}" height="{d-b}"/>' for a, b, c, d in MARK_RECTS
    )
    # baseline so that x-height band is centred on the mark
    base = y0 + mark_h / 2 + font * 0.27
    svg = (
        f'<g id="signature"><g transform="translate({x0:.1f},{y0:.1f}) scale({s:.5f})" fill="{theme["purple"]}">{rects}</g>'
        f'<text x="{x0+mark_w+gap:.1f}" y="{base:.1f}" font-family="JBM" font-weight="800" font-size="{font}" '
        f'letter-spacing="{-1.1*k:.2f}" fill="{theme["text"]}">gahingwoo</text></g>'
    )
    return svg, (x0, y0, W - margin, H - margin, k)


def render(svg_body, out_png, scale=0.25, W=W, H=H):
    font_b64 = base64.b64encode(FONT.read_bytes()).decode()
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W*scale}" height="{H*scale}">'
        f"<style>@font-face{{font-family:JBM;font-weight:800;src:url(data:font/woff2;base64,{font_b64})}}</style>"
        f"{svg_body}</svg>"
    )
    out_png = pathlib.Path(out_png)
    svg_path = out_png.with_suffix(".svg")
    svg_path.write_text(svg)
    html = out_png.with_suffix(".html")
    html.write_text(f"<html><body style='margin:0;background:#000'>{svg}</body></html>")
    subprocess.run(
        ["google-chrome", "--headless=new", "--no-sandbox", "--hide-scrollbars", "--disable-gpu",
         "--force-device-scale-factor=1", f"--window-size={int(W*scale)},{int(H*scale)}", f"--screenshot={out_png}",
         "--virtual-time-budget=8000", f"file://{html.resolve()}"],
        check=True, capture_output=True,
    )
    return out_png


def lerp(a, b, t):
    return a + (b - a) * t


def hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def mix(c1, c2, t):
    t = max(0.0, min(1.0, t))
    a, b = hex2rgb(c1) if isinstance(c1, str) else c1, hex2rgb(c2) if isinstance(c2, str) else c2
    return tuple(lerp(a[i], b[i], t) for i in range(3))


def rgb(c):
    return "#%02x%02x%02x" % tuple(int(round(max(0, min(255, v)))) for v in c)


def rel_lum(c):
    ch = [v / 255 for v in c]
    ch = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in ch]
    return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2]


def contrast(a, b):
    la, lb = sorted((rel_lum(a), rel_lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def check_signature_zone(png, bbox, theme, scale, pad=110, min_contrast=3.0, max_spread=0.06):
    """Measure the *rendered* pixels behind the signature (render without it first).
    min_contrast: WCAG 3:1 for graphics, mark purple vs every pixel (2nd percentile).
    max_spread: relative-luminance spread (p95 - p5) so the ground is calm."""
    import numpy as np
    from PIL import Image
    im = np.asarray(Image.open(png).convert("RGB")).astype(float) / 255
    x0, y0, x1, y1 = [int(v * scale) for v in (bbox[0] - pad * bbox[4], bbox[1] - pad * bbox[4],
                                                bbox[2] + pad * bbox[4], bbox[3] + pad * bbox[4])]
    px = im[max(0, y0):y1, max(0, x0):x1].reshape(-1, 3)
    lin = np.where(px <= 0.04045, px / 12.92, ((px + 0.055) / 1.055) ** 2.4)
    lum = lin @ np.array([0.2126, 0.7152, 0.0722])
    lm = rel_lum(hex2rgb(theme["purple"]))
    cr = (np.maximum(lm, lum) + 0.05) / (np.minimum(lm, lum) + 0.05)
    worst = np.percentile(cr, 2)
    spread = np.percentile(lum, 95) - np.percentile(lum, 5)
    assert worst >= min_contrast, f"mark contrast {worst:.2f}:1 < {min_contrast}:1 in signature zone"
    assert spread <= max_spread, f"signature zone too busy: luminance spread {spread:.3f} > {max_spread}"
    return worst, spread


def oklab_chroma(c):
    """OKLab chroma of an sRGB 0-255 tuple"""
    import numpy as np
    x = np.array(c, dtype=float) / 255
    lin = np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)
    M1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929], [0.2119034982, 0.6806995451, 0.1073969566], [0.0883024619, 0.2817188376, 0.6299787005]])
    M2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468], [1.9779984951, -2.4285922050, 0.4505937099], [0.0259040371, 0.7827717662, -0.8086757660]])
    L, a, b = M2 @ np.cbrt(M1 @ lin)
    return float(np.hypot(a, b))
