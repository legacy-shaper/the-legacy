// deno run push_test.ts — RFC 8291 §5 / Appendix A example, and a VAPID signature check.
import { b64u, encrypt, jwkFromRaw, vapidHeader } from "./push.ts";
const d = b64u.dec;
const asPublic = d("BP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27mlmlMoZIIgDll6e3vCYLocInmYWAmS6TlzAC8wEqKK6PBru3jl7A8");
const out = await encrypt(new TextEncoder().encode("When I grow up, I want to be a watermelon"),
  d("BCVxsr7N_eNgVRqvHtD0zTZsEc6-VV-JvLexhqUzORcxaOzi6-AYWXvTBHm4bjyPjs7Vd8pZGH6SRpkNtoIAiw4"), d("BTBZMqHH6r4Tts7J_aSIgg"),
  { asPublic, asPrivate: d("yfWPiYE-n46HLnH0KqZOF1fJJU3MYrct3AELtAQ-oRw"), salt: d("DGv6ra1nlYgDCS1FRnbzlw") });
const header = "DGv6ra1nlYgDCS1FRnbzlwAAEABBBP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27mlmlMoZIIgDll6e3vCYLocInmYWAmS6TlzAC8wEqKK6PBru3jl7A8";
const cipher = "8pfeW0KbunFT06SuDKoJH9Ql87S1QUrdirN6GcG7sFz1y1sqLgVi1VhjVkHsUoEsbI_0LpXMuGvnzQ";
const want = new Uint8Array([...d(header), ...d(cipher)]);
const same = out.length === want.length && out.every((v, i) => v === want[i]);
if (!same) { console.error("FAIL rfc8291", b64u.enc(out)); Deno.exit(1); }
console.log("ok   RFC 8291 example reproduced byte for byte (" + out.length + " bytes)");
// VAPID: signature verifies with the public key
const kp = await crypto.subtle.generateKey({ name: "ECDSA", namedCurve: "P-256" }, true, ["sign", "verify"]) as CryptoKeyPair;
const jwk = await crypto.subtle.exportKey("jwk", kp.privateKey);
const pub = new Uint8Array(await crypto.subtle.exportKey("raw", kp.publicKey));
const h = await vapidHeader("https://web.push.apple.com/abc", pub, d(jwk.d!), "mailto:office@legacy-shaper.com");
const tok = h.match(/t=([^,]+)/)![1]; const [a, b, s] = tok.split(".");
const okSig = await crypto.subtle.verify({ name: "ECDSA", hash: "SHA-256" }, kp.publicKey, d(s), new TextEncoder().encode(a + "." + b));
const claims = JSON.parse(new TextDecoder().decode(d(b)));
if (!okSig || claims.aud !== "https://web.push.apple.com" || !h.includes("k=" + b64u.enc(pub))) { console.error("FAIL vapid"); Deno.exit(1); }
console.log("ok   VAPID token signed (ES256), audience = push service origin");
console.log(JSON.stringify(jwkFromRaw(pub)).length > 50 ? "ok   key conversion" : "FAIL");
