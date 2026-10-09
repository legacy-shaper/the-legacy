#!/usr/bin/env python3
"""Paints the demo collection's images that were plain colour squares (fictional artists, no rights involved).
   aur-04 Yuna Takemori, Blue Field I  — pure pigment and resin on panel, 100 × 100 cm
   aur-12 Yuna Takemori, Red Field II  — pure pigment and resin on panel, 100 × 100 cm
   aur-10 Nadia Karami, Horizon, Hatta — sumi ink on Japanese paper, 90 × 140 cm
   Usage: python3 tools/demo_art.py <out_dir>   → <id>-v2.jpg (full) and <id>-v2-t.jpg (300 px thumbnail)"""
import sys, os, numpy as np
from PIL import Image, ImageFilter
rng = np.random.default_rng(7)

def fbm(h, w, octaves=6, base=4, persistence=0.55, seed=0):
    r = np.random.default_rng(seed); out = np.zeros((h, w)); amp = 1.0; tot = 0
    for o in range(octaves):
        n = base * 2 ** o
        g = r.random((n + 1, int(n * w / h) + 2))
        im = Image.fromarray((g * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
        out += amp * (np.asarray(im, float) / 255 - .5); tot += amp; amp *= persistence
    return out / tot

def save(arr, out, name):
    im = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    im.save(os.path.join(out, name + ".jpg"), quality=90)
    t = im.copy(); s = min(t.size); t = t.crop(((t.width - s) // 2, (t.height - s) // 2, (t.width + s) // 2, (t.height + s) // 2)).resize((300, 300), Image.LANCZOS)
    t.save(os.path.join(out, name + "-t.jpg"), quality=88)

def pigment_field(deep, mid, light, seed, band):
    """A pure-pigment field: matte, powdery, cloudy density (no streaks), a second tone floating in it with soft,
       irregular edges (band = (top, bottom) as a fraction of the height), pigment pooling darker at the edges."""
    H = W = 1100; y, x = np.mgrid[0:H, 0:W] / H
    cloud = fbm(H, W, 7, 3, .62, seed)
    wob = .035 * fbm(H, W, 5, 4, .6, seed + 9)
    t0, t1 = band
    inside = 1 / (1 + np.exp(-(y - t0 + wob) / .018)) * 1 / (1 + np.exp((y - t1 - wob) / .018))
    inside *= 1 / (1 + np.exp(-(x - .07 + wob) / .02)) * 1 / (1 + np.exp((x - .93 - wob) / .02))
    edge = np.clip(np.minimum.reduce([x, 1 - x, y, 1 - y]) / .12, 0, 1) ** .5
    t = np.clip(.30 + .55 * cloud + .45 * inside, 0, 1) * (.78 + .22 * edge)
    deep, mid, light = map(np.array, (deep, mid, light))
    tt = t[..., None]
    col = np.where(tt < .5, deep + (mid - deep) * (tt / .5), mid + (light - mid) * ((tt - .5) / .5))
    grain = rng.normal(0, 1, (H, W)); grain = np.asarray(Image.fromarray(((grain * 22) + 128).clip(0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(.7)), float) - 128
    speck = (rng.random((H, W)) > .9985) * rng.uniform(-60, 40, (H, W))
    return col + (grain + speck)[..., None] * np.array([.6, .6, .75])

def ink_horizon(seed=11):
    """Sumi ink on washi: warm fibrous paper; three ridges from pale distant wash to dense near-black ink, each crest
       crisp and feathered by the paper, the wash fading downwards into mist; a sun left blank inside a faint ink ring."""
    H, W = 900, 1400; y, x = np.mgrid[0:H, 0:W].astype(float)
    paper = np.array([236, 229, 213], float) + 6 * fbm(H, W, 6, 6, .6, seed)[..., None]
    fib = (rng.random((H, W)) ** 60 * 255).astype(np.uint8)
    fib = np.asarray(Image.fromarray(fib).filter(ImageFilter.GaussianBlur(.8)), float)
    img = paper - fib[..., None] * .25
    ink = np.zeros((H, W)); feather = 6 * fbm(H, W, 5, 20, .7, seed + 4)
    def ridge(base, amp, s):
        r = np.random.default_rng(s); xs = np.linspace(0, 1, W); v = np.zeros(W)
        for k in range(1, 10): v += r.uniform(.3, 1) / k ** 1.15 * np.sin(2 * np.pi * (k * r.uniform(.7, 1.3) * xs + r.random()))
        return base - amp * (v - v.min()) / np.ptp(v)
    for base, amp, dark, fade, s in [(H * .46, H * .20, .28, .30, 31), (H * .60, H * .22, .55, .26, 32), (H * .80, H * .20, .93, .40, 33)]:
        d = y - ridge(base, amp, s)[None, :] + feather
        crest = np.clip(d / 3, 0, 1)
        body = np.exp(-np.clip(d, 0, None) / (H * fade)) * .75 + .25
        tex = 1 + .25 * fbm(H, W, 6, 8, .65, s)
        ink = np.maximum(ink, np.clip(crest * body * tex, 0, 1) * dark)
    ink = np.asarray(Image.fromarray((ink * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(.9)), float) / 255
    rr = np.hypot(x - W * .72, y - H * .22)
    ink = np.where(rr < 40, ink * .2, ink) + np.exp(-((rr - 41) / 1.6) ** 2) * .12
    inkcol = np.array([22, 21, 24], float)
    return img * (1 - ink[..., None]) + inkcol * ink[..., None]

if __name__ == "__main__":
    out = sys.argv[1]; os.makedirs(out, exist_ok=True)
    save(pigment_field((6, 12, 58), (20, 40, 140), (58, 92, 190), 3, (.30, .62)), out, "aur-04-v2")
    save(pigment_field((60, 6, 12), (140, 20, 26), (205, 74, 48), 5, (.18, .46)), out, "aur-12-v2")
    save(ink_horizon(), out, "aur-10-v2")
    print("ok")
