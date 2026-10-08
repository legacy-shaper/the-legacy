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

## View at scale: cut-out masks
White or silver sculptures on a white backdrop are cut out with a mask Claude computes once per photo
(`tools/cutout.py`, ISNet model, pedestals measured on the photo with `--base`), checked by eye, then stored on the
artwork as `scaleView.cutout` = {w, h, mask, srcLen, srcTail}. `tools/room.js` combines it with its own edge detection;
the mask is tied to its exact photo. Test: `tests/test_cutout_mask.py`.
