#!/usr/bin/env python3
"""Build the encrypted data snapshot (data.enc) for The Legacy read-only app.

Usage:
  python3 tools/publish.py <export_dir> [--out data.enc]

<export_dir> holds the JSON documents exported from the Claude artifact database
(ArtifactData `list ... out_dir`), laid out as:
  settings/company.json, invoices/*.json, contacts/*.json, artworks/*.json,
  artworks/<id>/views/*.json, expenses/*.json
Optional: <export_dir>/assets/<asset_id>.<ext> — receipt files (from the
artifact's asset store). Each is encrypted to files/<asset_id>.enc once
(files are immutable per id, so existing .enc files are kept).
Each file is {"id":..., "data":{...}} or the bare document.

Encryption: a fresh AES-256-GCM key per snapshot, wrapped with the RSA-OAEP
(SHA-256) public key in pub.json. Only the owner's devices, holding the private
key unlocked with their access code, can read it. No secret is needed here.
"""
import base64, json, os, sys, glob, datetime
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load(path):
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    return d.get("data", d) if isinstance(d, dict) else d

def collect(export_dir):
    out = {"company": {}, "invoices": {}, "contacts": {}, "artworks": {}, "views": {}, "expenses": {}}
    comp = os.path.join(export_dir, "settings", "company.json")
    if os.path.exists(comp):
        out["company"] = load(comp)
    for coll in ("invoices", "contacts", "artworks", "expenses"):
        for p in glob.glob(os.path.join(export_dir, coll, "*.json")):
            doc = load(p); did = doc.get("id") or os.path.splitext(os.path.basename(p))[0]
            doc["id"] = did; out[coll][did] = doc
    for p in glob.glob(os.path.join(export_dir, "artworks", "*", "views", "*.json")):
        aid = p.split(os.sep)[-3]; v = load(p); vid = v.get("id") or os.path.splitext(os.path.basename(p))[0]
        v["id"] = vid; out["views"].setdefault(aid, {})[vid] = v
    return out

def seal(pk, plain, extra=None):
    key = AESGCM.generate_key(bit_length=256); iv = os.urandom(12)
    ct = AESGCM(key).encrypt(iv, plain, None)
    ek = pk.encrypt(key, padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
    env = {"v": 1, "ek": base64.b64encode(ek).decode(), "iv": base64.b64encode(iv).decode(), "ct": base64.b64encode(ct).decode()}
    if extra: env.update(extra)
    return env

MIME = {".pdf": "application/pdf", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".gif": "image/gif"}

def seal_files(pk, export_dir):
    src = os.path.join(export_dir, "assets"); dst = os.path.join(ROOT, "files"); n = 0
    if not os.path.isdir(src): return 0
    os.makedirs(dst, exist_ok=True)
    for p in glob.glob(os.path.join(src, "*")):
        aid, ext = os.path.splitext(os.path.basename(p))
        out = os.path.join(dst, aid + ".enc")
        if os.path.exists(out): continue
        with open(p, "rb") as f: env = seal(pk, f.read(), {"type": MIME.get(ext.lower(), "application/octet-stream")})
        with open(out, "w") as f: json.dump(env, f)
        n += 1
    return n

def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    export_dir = sys.argv[1]
    out_path = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else os.path.join(ROOT, "data.enc")
    pub = json.load(open(os.path.join(ROOT, "pub.json")))["pub"]
    pk = serialization.load_der_public_key(base64.b64decode(pub))
    data = collect(export_dir)
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    data["exportedAt"] = now
    plain = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    env = seal(pk, plain, {"exportedAt": now})
    with open(out_path, "w") as f:
        json.dump(env, f)
    n = {k: len(v) for k, v in data.items() if isinstance(v, dict)}
    nf = seal_files(pk, export_dir)
    print(f"receipt files newly encrypted: {nf}")
    print(f"data.enc written ({os.path.getsize(out_path)//1024} KB) at {now}: {n}")

if __name__ == "__main__":
    main()
