#!/usr/bin/env python3
"""Cut-out mask for the view at scale (sculptures, objects shot on a plain backdrop).

A white or silver piece on a white backdrop cannot be told apart by colour, and its outline is often too faint for the
app's edge detection. Claude runs a salient-object model here once per photo and stores the mask on the artwork:
master_docs artworks/<id> -> data.scaleView.cutout = {w, h, mask}. tools/room.js combines it with its own edge detection.

Model: ISNet (general use), ONNX, downloaded once from the rembg releases on GitHub:
  curl -L -o /tmp/isnet.onnx https://github.com/danielgatis/rembg/releases/download/v0.0.0/isnet-general-use.onnx
  pip install --break-system-packages onnxruntime

Usage: python3 tools/cutout.py <model.onnx> <photo.jpg|png> <out.json> [--base cx,cy,rx,ry,t ...]
  out.json = {"w": photo width, "h": photo height, "mask": "data:image/png;base64,..."} (16 grey levels, long side 640 px)
  --base: a white pedestal the model left out (it treats a pale disc as backdrop), measured on the photo in its pixels:
          top ellipse centre (cx, cy), half-width rx, half-depth ry, thickness t. Repeat for each pedestal.

Every cut-out is checked by eye before it is stored (rendered on the green wall, where any flaw shows): the dimensions of
a piece "including pedestal" scale the whole silhouette, so a missing pedestal would also make the piece look too large.
"""
import base64, io, json, sys

import numpy as np
import onnxruntime as ort
from PIL import Image

LONG = 640


def _run(sess, im):
    inp = sess.get_inputs()[0]
    S = inp.shape[2] if isinstance(inp.shape[2], int) else 1024
    x = np.asarray(im.resize((S, S), Image.BICUBIC)).astype(np.float32) / 255.0 - 0.5
    o = sess.run(None, {inp.name: x.transpose(2, 0, 1)[None].astype(np.float32)})[0][0, 0]
    o = (o - o.min()) / (o.max() - o.min() + 1e-8)
    return np.asarray(Image.fromarray((o * 255).astype(np.uint8)).resize(im.size, Image.BICUBIC)).astype(np.float32) / 255.0


def _pieces(m, W, H):
    """bounding boxes of the pieces found by the first pass (columns of the mask separated by empty backdrop)"""
    cols = (m > 0.5).sum(0) > max(2, H * 0.01)
    boxes, x = [], 0
    while x < W:
        if not cols[x]:
            x += 1
            continue
        x0 = x
        while x < W and cols[x]:
            x += 1
        x1 = x - 1
        if x1 - x0 < W * 0.04:
            continue
        rows = np.where((m[:, x0:x1 + 1] > 0.5).sum(1) > 0)[0]
        boxes.append((x0, rows[0], x1, rows[-1]))
    return boxes


def _pedestal(m, cx, cy, rx, ry, t):
    """silhouette of a disc pedestal seen from slightly above: top ellipse, bottom ellipse and the band between"""
    H, W = m.shape
    yy, xx = np.mgrid[0:H, 0:W]
    top = ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2 <= 1
    bot = ((xx - cx) / rx) ** 2 + ((yy - cy - t) / ry) ** 2 <= 1
    band = (np.abs(xx - cx) <= rx) & (yy >= cy) & (yy <= cy + t)
    m[top | bot | band] = 1.0


def mask_for(model, path, bases=()):
    im = Image.open(path).convert("RGB")
    W, H = im.size
    sess = ort.InferenceSession(model, providers=["CPUExecutionProvider"])
    m = _run(sess, im)
    # second pass on each piece, framed closer: a white piece on a white backdrop is found far better at that scale
    for (x0, y0, x1, y1) in _pieces(m, W, H):
        mx, my = round((x1 - x0) * 0.12), round((y1 - y0) * 0.08)
        bx = (max(0, x0 - mx), max(0, y0 - my), min(W, x1 + mx + 1), min(H, y1 + my + 1))
        sub = _run(sess, im.crop(bx))
        m[bx[1]:bx[3], bx[0]:bx[2]] = np.maximum(m[bx[1]:bx[3], bx[0]:bx[2]], sub)
    for b in bases:
        _pedestal(m, *b)
    k = LONG / max(W, H)
    mi = Image.fromarray((m * 255).astype(np.uint8)).resize((max(1, round(W * k)), max(1, round(H * k))), Image.BICUBIC)
    # 16 grey levels are plenty (the app reads "piece" from 128 up, and the model's leaning over an area): a far smaller file
    q = (np.asarray(mi).astype(np.int32) + 8) // 17 * 17
    mi = Image.fromarray(np.clip(q, 0, 255).astype(np.uint8)).convert("P", palette=Image.ADAPTIVE, colors=16)
    buf = io.BytesIO()
    mi.save(buf, "PNG", optimize=True, bits=4)
    return {"w": W, "h": H, "mask": "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()}


if __name__ == "__main__":
    model, src, dst = sys.argv[1:4]
    bases, a = [], sys.argv[4:]
    while a:
        if a[0] == "--base":
            bases.append(tuple(float(v) for v in a[1].split(",")))
            a = a[2:]
        else:
            sys.exit("unknown option " + a[0])
    r = mask_for(model, src, bases)
    json.dump(r, open(dst, "w"))
    print(f"{r['w']}x{r['h']} mask {len(r['mask'])} chars")
