# The Legacy — read-only app (phone, tablet, Mac)

Private consultation app for Legacy Shaper Collection - FZCO. Data is encrypted
(data.enc, files/*.enc); only the owner's devices, unlocked with his access code,
can read it. No secret is stored here.

## Layout
- `index.html`, `sw.js` — the app (generated, do not edit by hand)
- `tools/master.html` — master source = the Claude artifact "The Legacy"
- `tools/build.py` — builds index.html + sw.js from master.html
- `tools/publish.py <export_dir>` — encrypts the database export into data.enc (+ receipts into files/)
- `tools/viewer-head.html`, `tools/viewer-tail.html`, `tools/sw.template.js` — viewer wrapper
- `key.enc`, `pub.json` — owner's encrypted private key / public key (never modify)

## Change the app
1. Edit `tools/master.html`.
2. Publish it to the artifact https://claude.ai/artifact/MfqmNZvqdzzQCXTsEQcNG1.
3. `python3 tools/build.py`, commit, push.

## Refresh the data
Export the artifact database (settings, invoices, contacts, artworks, expenses,
artworks/<id>/views; receipts to <export>/assets/<asset_id>.<ext>), then
`python3 tools/publish.py <export>`, commit data.enc (+ files/), push.
