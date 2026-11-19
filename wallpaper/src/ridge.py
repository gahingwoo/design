"""Direction A (approved r1): low-poly ridge at first light.

Terrain is built once in world space (seed 7). Each format is a separate camera
framing of the same world -- focal length and principal point change, nothing is
cropped. 16:9 with the BASE framing reproduces the approved r1 preview exactly.
"""
import numpy as np
from scipy.ndimage import gaussian_filter
from scipy.spatial import Delaunay
from scipy.interpolate import RegularGridInterpolator
from common import *

SEED = 7
F0 = 2.05 * 1920          # r1 focal length in px at 3840x2160

# ---------- terrain (world space, identical for every format) ----------
rng = np.random.default_rng(SEED)
NX, NY = 84, 36
xs = np.linspace(-5.6, 5.6, NX)
ys = np.linspace(0.0, 6.0, NY)
X, Y = np.meshgrid(xs, ys)
X = X + (rng.random(X.shape) - .5) * (xs[1] - xs[0]) * .62
Y = Y + (rng.random(Y.shape) - .5) * (ys[1] - ys[0]) * .62


def _noise(shape, sigma, amp):
    return gaussian_filter(rng.standard_normal(shape), sigma) * amp * sigma


def _peak(cx, cy, h, sx, sy):
    return h * np.exp(-((((X - cx) / sx) ** 2 + ((Y - cy) / sy) ** 2) ** 0.62) * 1.5)


SUMMIT = np.array([-1.05, 3.3])
Z = np.zeros_like(X)
Z += _peak(*SUMMIT, 1.75, 1.0, 1.0)
Z += _peak(0.45, 3.9, 1.05, 0.9, 0.9)
Z += _peak(1.9, 4.3, 1.35, 1.1, 1.0)
Z += _peak(-2.9, 4.2, 1.15, 1.0, 1.0)
Z += _peak(3.6, 3.9, 1.0, 1.0, 0.9)
Z += _peak(-4.4, 3.6, 0.8, 1.0, 0.9)
Z += _peak(0.3, 2.0, 0.42, 1.3, 0.6)
Z += _peak(2.6, 1.6, 0.38, 1.2, 0.6)
Z += _peak(-2.6, 1.7, 0.35, 1.2, 0.6)
Z += (0.45 - np.abs(_noise(X.shape, 2.2, 1.0))) * 0.75 * np.clip(Z, 0, 1.0)
Z += _noise(X.shape, 1.0, 0.10)
Z = np.maximum(Z, 0.02 * rng.random(Z.shape))
SKY_RNG_STATE = rng.bit_generator.state     # sky jitter continues from here, as in r1

P = np.stack([X, Y, Z], -1).reshape(-1, 3)
_t = []
for j in range(NY - 1):
    for i in range(NX - 1):
        a, b, c, d = j * NX + i, j * NX + i + 1, (j + 1) * NX + i, (j + 1) * NX + i + 1
        _t += [(a, b, d), (a, d, c)] if (i + j) % 2 else [(a, b, c), (b, d, c)]
TRIS = np.array(_t)

CAM = np.array([0.15, -2.3, 1.15])
PITCH = np.deg2rad(4.0)
SUN = np.array([0.80, 0.42, 0.30]); SUN = SUN / np.linalg.norm(SUN)

v0, v1, v2 = P[TRIS[:, 0]], P[TRIS[:, 1]], P[TRIS[:, 2]]
NRM = np.cross(v1 - v0, v2 - v0)
NRM /= np.linalg.norm(NRM, axis=1, keepdims=True)
NRM[NRM[:, 2] < 0] *= -1
CENT = (v0 + v1 + v2) / 3
LAM = NRM @ SUN
_hf = RegularGridInterpolator((ys, xs), Z, bounds_error=False, fill_value=0)
LIT = np.ones(len(TRIS))
for s in np.linspace(0.08, 2.5, 40):
    q = CENT + SUN * s
    LIT = np.minimum(LIT, np.clip((q[:, 2] - _hf(q[:, [1, 0]])) * 9 + 1, 0, 1))

PAL_DARK = dict(base="#151422", sky_top="#171628", sky_mid="#3A2C6B", glow="#B4587A",
                sh_lo="#1F1C3A", sh_hi="#5B4AA8", lit_rock="#F2876B", lit_snow="#FFD9A8",
                shade_snow="#A98BF0", fg="#151422")
LUM = lambda c: 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]

# framing: F as a multiple of F0*(H/2160); (cx, cy) projection centre as fractions of W, H
BASE = dict(f=1.0, cx=0.5, cy=0.60)
GLOW_FLOOR = 0.10


def build(Wt, Ht, frame=BASE, theme=DARK, pal=PAL_DARK):
    F = F0 * frame["f"] * Ht / 2160
    cx, cy = frame["cx"] * Wt, frame["cy"] * Ht
    u = F / F0                               # px-per-world scale relative to r1

    q = P - CAM
    yy = q[:, 1] * np.cos(PITCH) + q[:, 2] * np.sin(PITCH)
    zz = -q[:, 1] * np.sin(PITCH) + q[:, 2] * np.cos(PITCH)
    S = np.stack([cx + F * q[:, 0] / yy, cy - F * zz / yy], -1)
    dz = yy[TRIS].mean(1)

    # coverage: terrain must reach the bottom edge and both side edges
    SG = S.reshape(NY, NX, 2)
    assert SG[0, :, 1].min() > Ht, "nearest terrain row does not reach below the frame"
    for col, side in ((0, "left"), (-1, "right")):
        inside = SG[:, col, 1] < Ht
        ok = SG[inside, col, 0] < 0 if side == "left" else SG[inside, col, 0] > Wt
        assert ok.all(), f"terrain {side} edge visible inside the frame"

    polys, ter, drawn = [], [], []
    for k in np.argsort(-dz):
        h = CENT[k, 2]
        snow = np.clip((h - 0.85) / 0.4, 0, 1)
        l = np.clip(LAM[k] * pal.get("lit_gain", 1.5), 0, 1) * LIT[k]
        # alpenglow only reaches high ground; valley floor stays in shadow (stops it turning brown)
        l *= np.clip((h - GLOW_FLOOR) / 0.40, 0, 1)
        shade = mix(mix(pal["sh_lo"], pal["sh_hi"], np.clip(h / 1.4, 0, 1) * (0.55 + 0.45 * NRM[k, 2])),
                    pal["shade_snow"], snow * 0.75)
        c = mix(shade, mix(pal["lit_rock"], pal["lit_snow"], snow), l ** 0.8)
        c = mix(c, pal["sky_mid"], np.clip((dz[k] - 4.6) / 4.0, 0, pal.get("fog_amt", 0.55)))
        c = mix(c, pal["fg"], np.clip((pal.get("fg_depth", 4.3) - dz[k]) / 1.6, 0, 0.9))
        if pal.get("mist"):
            lo = pal.get("mist_lo", 0.0)
            t = np.clip((pal["mist_h"] - h) / (pal["mist_h"] - lo), 0, 1)
            c = mix(c, pal["fg"], (t * t * (3 - 2 * t)) * pal["mist"])
        tri = S[TRIS[k]]
        if tri[:, 0].max() < 0 or tri[:, 0].min() > Wt or tri[:, 1].max() < 0 or tri[:, 1].min() > Ht:
            continue                            # off-frame: not drawn, not counted
        drawn.append(tri)
        ter.append((oklab_chroma(c) * 1000 if pal.get("focal") == "chroma" else LUM(c), tri.mean(0), k))
        col = rgb(c)
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in tri)
        polys.append(f'<polygon points="{pts}" fill="{col}" stroke="{col}" stroke-width="1.5" stroke-linejoin="round"/>')

    # sky: same triangle language, density and glow tied to the world scale u
    srng = np.random.default_rng(); srng.bit_generator.state = SKY_RNG_STATE
    px, py = 200 * u, 150 * u
    nx = int(round((Wt + 2 * px) / (302.857 * u))) + 1
    ny = int(round((Ht + 2 * py) / (273.333 * u))) + 1
    sp = np.array([(x, y) for x in np.linspace(-px, Wt + px, nx) for y in np.linspace(-py, Ht + py, ny)])
    sp = sp + (srng.random((len(sp), 2)) - .5) * [200 * u, 150 * u]
    gdx, gdy = pal.get("glow_pos", (845, 130))
    gsx, gsy = pal.get("glow_size", (1700, 430))
    glow_c = np.array([cx + gdx * u, cy + gdy * u])
    vref = cy + 43 * u
    sky, sky_l = [], []
    for t in Delaunay(sp).simplices:
        c0 = sp[t].mean(0)
        col = mix(pal["sky_top"], pal["sky_mid"], np.clip(c0[1] / vref, 0, 1) ** 1.5)
        g = np.exp(-(((c0[0] - glow_c[0]) / (gsx * u)) ** 2 + ((c0[1] - glow_c[1]) / (gsy * u)) ** 2))
        col = mix(col, pal["glow"], g * pal.get("glow_str", 0.62))
        if "glow_core" in pal:
            col = mix(col, pal["glow_core"], max(0, g - 0.72) * pal.get("core_str", 2.4))
        if 0 <= c0[0] <= Wt and 0 <= c0[1] <= Ht:
            sky_l.append(oklab_chroma(col) * 1000 if pal.get("focal") == "chroma" else LUM(col))
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in sp[t])
        sky.append(f'<polygon points="{pts}" fill="{rgb(col)}" stroke="{rgb(col)}" stroke-width="1.5"/>')

    # coverage (pixel-level): every point along the bottom edge must lie inside a drawn terrain
    # triangle -- vertex checks alone missed holes beyond the world's side edge on wide frames
    T = np.array(drawn)
    a, b, c3 = T[:, 0], T[:, 1], T[:, 2]
    for sx in np.linspace(0.5, Wt - 0.5, 61):
        for sy in (Ht - 0.5, Ht * 0.97):
            p = np.array([sx, sy])
            v0, v1, v2 = c3 - a, b - a, p - a
            d00 = (v0 * v0).sum(1); d01 = (v0 * v1).sum(1); d11 = (v1 * v1).sum(1)
            d20 = (v2 * v0).sum(1); d21 = (v2 * v1).sum(1)
            den = d00 * d11 - d01 * d01
            with np.errstate(divide="ignore", invalid="ignore"):
                u = (d11 * d20 - d01 * d21) / den; v = (d00 * d21 - d01 * d20) / den
            assert ((u >= -1e-9) & (v >= -1e-9) & (u + v <= 1 + 1e-9)).any(), f"terrain hole at ({sx:.0f},{sy:.0f})"

    # rule 2: one focal point -- brightest visible face is on the main summit, sky stays under it
    best_l, best_xy, best_k = max(ter, key=lambda t: t[0])
    if pal.get("_debug_skip_focal"):  # diagnostics only; final.py never sets this
        best_k = None
    assert best_k is None or np.linalg.norm(CENT[best_k, :2] - SUMMIT) < 0.9, f"brightest face is off the main summit: {CENT[best_k]}"
    assert best_k is None or max(sky_l) <= pal.get("sky_cap", 0.62) * best_l, f"sky ({max(sky_l):.0f}) competes with summit ({best_l:.0f})"
    top = S[np.argmax(np.where(np.linalg.norm(P[:, :2] - SUMMIT, axis=1) < 0.6, P[:, 2], -1))]
    assert 0.08 * Ht < top[1] < 0.6 * Ht and 0.1 * Wt < top[0] < 0.75 * Wt, f"summit top framed badly at {top}"

    sig, bbox = signature(theme, W=Wt, H=Ht)
    bg = f'<rect width="{Wt}" height="{Ht}" fill="{pal["base"]}"/>' + "".join(sky) + "".join(polys)
    info = dict(sky=max(sky_l), summit=best_l, top=(top / [Wt, Ht]).round(3))
    return bg, sig, bbox, info


def make(Wt, Ht, frame, out, scale=1.0, theme=DARK, pal=PAL_DARK):
    bg, sig, bbox, info = build(Wt, Ht, frame, theme, pal)
    chk = render(bg, str(out).replace(".png", "_nosig.png"), scale=scale, W=Wt, H=Ht)
    worst, spread = check_signature_zone(chk, bbox, theme, scale)
    render(bg + sig, out, scale=scale, W=Wt, H=Ht)
    info.update(contrast=round(worst, 2), spread=round(spread, 3))
    return info


# r3 -- approved by Woo + DavidQyn 2026-11-19 ("3 最好，有个 balance").
# Summit lit side brightened (snow #FFF1D8, gain 2.0); r0-shaped warm sky restored.
# sky_cap 0.70: deliberate trade-off chosen by the designer (was 0.62) -- sky may reach
# 70% of the summit's peak luminance, never more.
PAL_DARK_R3 = dict(
    base="#151422", sky_top="#171628", sky_mid="#452d87", sh_lo="#1f1942", sh_hi="#6648cd",
    lit_rock="#ff7650", lit_snow="#FFF1D8", shade_snow="#A98BF0", fg="#151422",
    lit_gain=2.0,
    glow="#F08A6C", glow_core="#FFC27A", core_str=1.2, glow_str=0.65,
    glow_pos=(768, -173), glow_size=(1500, 520),
    sky_cap=0.70,
)


# light r1 -- morning: same world and sun; valleys fill with a sea of mist (the light-theme
# mirror of the dark version's pooled shadow). Focus is judged by OKLab chroma, not luminance,
# because the brightest thing in a light frame is the sky. mist_lo 0.70 is forced by the
# signature: #9472DB on #F4F2F8 tops out at 3.32:1, so the ground under it must be ~pure mist.
PAL_LIGHT = dict(
    base="#F4F2F8", sky_top="#B8B0E2", sky_mid="#DDD4F4", sh_lo="#4532B4", sh_hi="#8467EC",
    lit_rock="#FF5530", lit_snow="#FFFFFF", shade_snow="#B6A4F2", fg="#F4F2F8",
    lit_gain=2.4, fog_amt=0.25, fg_depth=4.9,
    glow="#FFA574", glow_core="#FFCDA6", core_str=1.2, glow_str=0.65,   # o2: designer asked for more orange
    glow_pos=(768, -173), glow_size=(1500, 520),
    mist=1.0, mist_lo=0.70, mist_h=1.15,
    focal="chroma", sky_cap=0.70,
)
