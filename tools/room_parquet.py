"""Versailles parquet panel (one 100 x 100 cm panel = N x N px), natural oak, tileable."""
import numpy as np, cv2
from PIL import Image

N = 1024
rng = np.random.default_rng(7)
y, x = np.mgrid[0:N, 0:N].astype(np.float32)
u = (x + .5) / N; v = (y + .5) / N               # panel coords 0..1

piece = np.zeros((N, N), np.int64)               # piece id
ang = np.zeros((N, N), np.float32)               # strip direction (radians)
edge = np.zeros((N, N), np.float32)              # distance to the piece border (px), for seams

F = 0.075                                        # frame width
d = np.stack([v, 1 - u, 1 - v, u])               # distance to top, right, bottom, left
side = d.argmin(0); dmin = d.min(0)
frame = dmin < F
piece[frame] = 1 + side[frame]
ang[frame] = np.where(side[frame] % 2 == 0, 0, np.pi / 2)[...]
# mitre seams of the frame: distance to the corner diagonals
dm = np.minimum(np.abs(u - v), np.abs(u + v - 1)) / np.sqrt(2) * N
edge_frame = np.minimum.reduce([np.abs(dmin - F) * N, dmin * N + 1e3 * 0, dm])
# frame strips are long: seams only at mitres and at the inner edge
edge[frame] = np.minimum(np.abs(dmin - F)[frame] * N, dm[frame])

# interior: diagonal lattice of bands, basket-woven
inner = ~frame
p = u + v; q = u - v                             # diagonal axes
S = 1 / 3.0                                      # band spacing (in p units)
Wd = 0.075 * np.sqrt(2)                          # band width (p units) = same visual width as frame strips
ia = np.round((p - 1) / S); oa = (p - 1) - ia * S       # offset from nearest band centre
ib = np.round(q / S);       ob = q - ib * S
inA = np.abs(oa) < Wd / 2; inB = np.abs(ob) < Wd / 2
both = inA & inB
overA = ((ia + ib) % 2 == 0)
useA = inA & (~inB | overA); useB = inB & ~useA
fill = ~(inA | inB)

k = 10
m = inner & useA
piece[m] = 100 + (ia[m] + 10) * 50 + np.floor((q[m] + 1) / S).astype(np.int64)      # cut at crossings
ang[m] = -np.pi / 4
m = inner & useB
piece[m] = 2000 + (ib[m] + 10) * 50 + np.floor((p[m] - 1) / S + 10).astype(np.int64)
ang[m] = np.pi / 4
m = inner & fill
# diamonds: three short strips along the A direction
cell_a = np.floor((p - 1) / S + .5); cell_b = np.floor(q / S + .5)
sub = np.floor(((p - 1) / S + .5 - cell_a) * 3)
piece[m] = 5000 + ((cell_a[m] + 10) * 100 + (cell_b[m] + 10)) * 4 + sub[m].astype(np.int64)
ang[m] = -np.pi / 4

# seams for interior: distance to band borders / strip divisions
ea = np.abs(np.abs(oa) - Wd / 2) / np.sqrt(2) * N
eb = np.abs(np.abs(ob) - Wd / 2) / np.sqrt(2) * N
es = np.abs(((p - 1) / S + .5 - cell_a) * 3 - np.round(((p - 1) / S + .5 - cell_a) * 3)) * S / 3 / np.sqrt(2) * N
edge[inner] = np.minimum.reduce([ea, eb, np.where(fill, es, 1e3), np.abs(dmin - F) * N])[inner]

# ---- wood: per-piece tone + grain stretched along the strip ----
ids, inv = np.unique(piece, return_inverse=True); inv = inv.reshape(N, N)
tone = rng.normal(0, 1, len(ids)).astype(np.float32)
offs = rng.uniform(0, 4000, len(ids)).astype(np.float32)
c, s = np.cos(ang), np.sin(ang)
along = x * c + y * s + offs[inv]
across = -x * s + y * c + offs[inv] * 1.7

def noise1d(n, scale, seed):
    r = np.random.default_rng(seed).normal(0, 1, n).astype(np.float32)
    r = np.concatenate([r, r[:64]])
    r = cv2.GaussianBlur(r.reshape(1, -1), (0, 0), scale).ravel()[:n]
    return r / (r.std() + 1e-6)
G = 16384
def samp(arr, t):
    t = np.mod(t, G); i0 = np.floor(t).astype(np.int64); f = t - i0
    return arr[i0 % G] * (1 - f) + arr[(i0 + 1) % G] * f
n_fine = noise1d(G, 0.9, 1); n_mid = noise1d(G, 3.5, 2); n_low = noise1d(G, 25, 3); n_wave = noise1d(G, 60, 4)
wav = samp(n_wave, along * 0.35 + offs[inv]) * 6.0          # fibres drift slowly along the strip
acr = across * 0.9 + wav
grain = 0.45 * samp(n_fine, acr) + 0.45 * samp(n_mid, acr * 0.5 + 300) + 0.35 * samp(n_low, acr * 0.12 + along * 0.004 + 900)
flecks = np.clip(samp(noise1d(G, 0.7, 9), along * 0.9 + acr * 7.3), 2.2, 9) - 2.2      # sparse medullary rays
base = np.array([0.43, 0.30, 0.20], np.float32)          # warm natural oak, darkened like the reference
lum = 1 + 0.06 * tone[inv] + 0.075 * grain + 0.05 * flecks
col = base[None, None, :] * lum[..., None]
col[..., 0] += 0.012 * grain; col[..., 2] -= 0.006 * grain
# seams
seam = np.clip(edge / 1.3, 0, 1)
col *= (0.45 + 0.55 * seam)[..., None]
bev = np.clip(1 - np.abs(edge - 2.2) / 1.5, 0, 1)
col *= (1 + 0.05 * bev)[..., None]
img = np.clip(col * 255, 0, 255).astype(np.uint8)
img = cv2.GaussianBlur(img, (0, 0), 0.6)
Image.fromarray(img).save("parquet.jpg", quality=86)
print("ok")
