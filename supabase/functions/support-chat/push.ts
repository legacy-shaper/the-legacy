// Web Push (RFC 8291 message encryption, RFC 8188 aes128gcm, RFC 8292 VAPID) with WebCrypto only.
// Verified against the RFC 8291 section 5 example (see push_test.ts).
const enc = new TextEncoder();
export const b64u = {
  enc: (b: ArrayBuffer | Uint8Array) => btoa(String.fromCharCode(...new Uint8Array(b))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, ""),
  dec: (s: string) => { const t = s.replace(/-/g, "+").replace(/_/g, "/"); const p = t + "===".slice((t.length + 3) % 4); return Uint8Array.from(atob(p), (c) => c.charCodeAt(0)); },
};
const cat = (...a: Uint8Array[]) => { const o = new Uint8Array(a.reduce((n, x) => n + x.length, 0)); let i = 0; for (const x of a) { o.set(x, i); i += x.length; } return o; };
async function hmac(key: Uint8Array, data: Uint8Array) {
  const k = await crypto.subtle.importKey("raw", key, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return new Uint8Array(await crypto.subtle.sign("HMAC", k, data));
}
export const jwkFromRaw = (pub: Uint8Array, d?: Uint8Array): JsonWebKey => ({
  kty: "EC", crv: "P-256", x: b64u.enc(pub.slice(1, 33)), y: b64u.enc(pub.slice(33, 65)), ...(d ? { d: b64u.enc(d) } : {}),
});

/** Encrypt one push message body (aes128gcm). asKeys/salt can be fixed for tests; normally random. */
export async function encrypt(plaintext: Uint8Array, uaPublic: Uint8Array, authSecret: Uint8Array,
  opts: { asPublic?: Uint8Array; asPrivate?: Uint8Array; salt?: Uint8Array } = {}) {
  let asPriv: CryptoKey, asPub: Uint8Array;
  if (opts.asPrivate && opts.asPublic) {
    asPub = opts.asPublic;
    asPriv = await crypto.subtle.importKey("jwk", jwkFromRaw(asPub, opts.asPrivate), { name: "ECDH", namedCurve: "P-256" }, false, ["deriveBits"]);
  } else {
    const kp = await crypto.subtle.generateKey({ name: "ECDH", namedCurve: "P-256" }, true, ["deriveBits"]) as CryptoKeyPair;
    asPriv = kp.privateKey; asPub = new Uint8Array(await crypto.subtle.exportKey("raw", kp.publicKey));
  }
  const ua = await crypto.subtle.importKey("raw", uaPublic, { name: "ECDH", namedCurve: "P-256" }, false, []);
  const ecdh = new Uint8Array(await crypto.subtle.deriveBits({ name: "ECDH", public: ua }, asPriv, 256));
  const prkKey = await hmac(authSecret, ecdh);
  const keyInfo = cat(enc.encode("WebPush: info"), new Uint8Array([0]), uaPublic, asPub);
  const ikm = await hmac(prkKey, cat(keyInfo, new Uint8Array([1])));
  const salt = opts.salt || crypto.getRandomValues(new Uint8Array(16));
  const prk = await hmac(salt, ikm);
  const cek = (await hmac(prk, cat(enc.encode("Content-Encoding: aes128gcm"), new Uint8Array([0, 1])))).slice(0, 16);
  const nonce = (await hmac(prk, cat(enc.encode("Content-Encoding: nonce"), new Uint8Array([0, 1])))).slice(0, 12);
  const key = await crypto.subtle.importKey("raw", cek, "AES-GCM", false, ["encrypt"]);
  const ct = new Uint8Array(await crypto.subtle.encrypt({ name: "AES-GCM", iv: nonce }, key, cat(plaintext, new Uint8Array([2]))));
  const header = cat(salt, new Uint8Array([0, 0, 0x10, 0]), new Uint8Array([asPub.length]), asPub);
  return cat(header, ct);
}

/** VAPID authorization header for an endpoint. */
export async function vapidHeader(endpoint: string, vapidPublic: Uint8Array, vapidPrivate: Uint8Array, subject: string) {
  const aud = new URL(endpoint).origin;
  const head = b64u.enc(enc.encode(JSON.stringify({ typ: "JWT", alg: "ES256" })));
  const body = b64u.enc(enc.encode(JSON.stringify({ aud, exp: Math.floor(Date.now() / 1000) + 12 * 3600, sub: subject })));
  const key = await crypto.subtle.importKey("jwk", jwkFromRaw(vapidPublic, vapidPrivate), { name: "ECDSA", namedCurve: "P-256" }, false, ["sign"]);
  const sig = await crypto.subtle.sign({ name: "ECDSA", hash: "SHA-256" }, key, enc.encode(head + "." + body));
  return `vapid t=${head}.${body}.${b64u.enc(sig)}, k=${b64u.enc(vapidPublic)}`;
}

export type Sub = { endpoint: string; p256dh: string; auth: string };
/** Send one notification. Returns the HTTP status (201 = delivered to the push service, 404/410 = subscription gone). */
export async function sendPush(sub: Sub, payload: unknown, vapid: { pub: string; priv: string; subject: string }, o: { ttl?: number; topic?: string; urgent?: boolean } = {}) {
  const body = await encrypt(enc.encode(JSON.stringify(payload)), b64u.dec(sub.p256dh), b64u.dec(sub.auth));
  const h: Record<string, string> = {
    "Content-Encoding": "aes128gcm", "Content-Type": "application/octet-stream", TTL: String(o.ttl ?? 24 * 3600),
    Urgency: o.urgent ? "high" : "normal",
    Authorization: await vapidHeader(sub.endpoint, b64u.dec(vapid.pub), b64u.dec(vapid.priv), vapid.subject),
  };
  if (o.topic) h.Topic = o.topic.replace(/[^A-Za-z0-9_-]/g, "").slice(0, 32);
  const r = await fetch(sub.endpoint, { method: "POST", headers: h, body });
  try { await r.text(); } catch { /* body unused */ }
  return r.status;
}
