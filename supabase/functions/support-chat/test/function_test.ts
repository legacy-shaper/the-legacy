// Local end-to-end test of the support-chat function (no network): run from this folder with
//   deno run --allow-env --import-map=import_map.json function_test.ts
import { DB } from "./stub_supabase.ts";
import { b64u } from "../push.ts";

let ok = 0;
const check = (c: unknown, label: string) => { if (!c) { console.error("FAIL:", label); Deno.exit(1); } ok++; console.log("ok  ", label); };

// ---- keys: VAPID (server) and a device subscription (user agent) ----
const vk = await crypto.subtle.generateKey({ name: "ECDSA", namedCurve: "P-256" }, true, ["sign", "verify"]) as CryptoKeyPair;
const vpub = b64u.enc(await crypto.subtle.exportKey("raw", vk.publicKey));
const vjwk = await crypto.subtle.exportKey("jwk", vk.privateKey);
const ua = await crypto.subtle.generateKey({ name: "ECDH", namedCurve: "P-256" }, true, ["deriveBits"]) as CryptoKeyPair;
const uaPub = new Uint8Array(await crypto.subtle.exportKey("raw", ua.publicKey));
const authSecret = crypto.getRandomValues(new Uint8Array(16));
Deno.env.set("SUPABASE_URL", "https://x.supabase.co"); Deno.env.set("SUPABASE_SERVICE_ROLE_KEY", "SERVICE"); Deno.env.set("SUPABASE_ANON_KEY", "ANON");
Deno.env.set("VAPID_PUBLIC_KEY", vpub);
DB.rpc.support_vapid_private = vjwk.d;

// decrypt what reaches the device (RFC 8291, user-agent side) to prove the notification is readable
const enc = new TextEncoder();
async function hmac(k: Uint8Array, d: Uint8Array) { const key = await crypto.subtle.importKey("raw", k, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]); return new Uint8Array(await crypto.subtle.sign("HMAC", key, d)); }
const cat = (...a: Uint8Array[]) => { const o = new Uint8Array(a.reduce((n, x) => n + x.length, 0)); let i = 0; for (const x of a) { o.set(x, i); i += x.length; } return o; };
async function decrypt(body: Uint8Array) {
  const salt = body.slice(0, 16), idlen = body[20], asPub = body.slice(21, 21 + idlen), ct = body.slice(21 + idlen);
  const asKey = await crypto.subtle.importKey("raw", asPub, { name: "ECDH", namedCurve: "P-256" }, false, []);
  const ecdh = new Uint8Array(await crypto.subtle.deriveBits({ name: "ECDH", public: asKey }, ua.privateKey, 256));
  const prkKey = await hmac(authSecret, ecdh);
  const ikm = await hmac(prkKey, cat(enc.encode("WebPush: info"), new Uint8Array([0]), uaPub, asPub, new Uint8Array([1])));
  const prk = await hmac(salt, ikm);
  const cek = (await hmac(prk, cat(enc.encode("Content-Encoding: aes128gcm"), new Uint8Array([0, 1])))).slice(0, 16);
  const nonce = (await hmac(prk, cat(enc.encode("Content-Encoding: nonce"), new Uint8Array([0, 1])))).slice(0, 12);
  const k = await crypto.subtle.importKey("raw", cek, "AES-GCM", false, ["decrypt"]);
  const pt = new Uint8Array(await crypto.subtle.decrypt({ name: "AES-GCM", iv: nonce }, k, ct));
  return JSON.parse(new TextDecoder().decode(pt.slice(0, pt.lastIndexOf(2))));
}

// ---- outside world: Claude API and the push service ----
let pushes: { headers: Headers; payload: any; status: number }[] = [];
let aiCalls: any[] = []; let aiAnswer: any = null; let pushStatus = 201;
globalThis.fetch = (async (input: any, init: any = {}) => {
  const url = String(input);
  if (url.startsWith("https://api.anthropic.com/")) {
    aiCalls.push({ headers: new Headers(init.headers), body: JSON.parse(init.body) });
    return new Response(JSON.stringify({ content: [{ type: "tool_use", name: "respond", input: aiAnswer }] }), { status: 200 });
  }
  if (url.startsWith("https://web.push.apple.com/")) {
    const payload = await decrypt(new Uint8Array(init.body));
    pushes.push({ headers: new Headers(init.headers), payload, status: pushStatus });
    return new Response("", { status: pushStatus });
  }
  throw new Error("unexpected fetch " + url);
}) as typeof fetch;

let handler: (r: Request) => Promise<Response>;
(Deno as any).serve = (h: any) => { handler = h; };
await import("../index.ts");

// ---- data ----
const CID = "c1", OTHER = "c2";
DB.users = { "jwt-client": { id: "u1" }, "jwt-other": { id: "u2" }, "jwt-dylan": { id: "u9", admin: true } };
DB.tables = {
  collection_members: [{ user_id: "u1", collection_id: CID }, { user_id: "u2", collection_id: OTHER }],
  collections: [{ id: CID, name: "The Aurelian Collection" }, { id: OTHER, name: "Collection B" }],
  artworks: [{ id: "aur-01", collection_id: CID, artist: "Élise Marchetti", title: "Crimson Threshold", year: "2014", location_text: "Paris" },
             { id: "b-1", collection_id: OTHER, artist: "Other Artist", title: "Secret Work", year: "2000", location_text: "" }],
  company_settings: [{ id: 1 }],
  support_settings: [{ id: 1, notify: "all", quiet_start: null, quiet_end: null, tz: "Europe/Paris", handoff_minutes: 10 }],
  push_subscriptions: [{ endpoint: "https://web.push.apple.com/QWERTY", p256dh: b64u.enc(uaPub), auth: b64u.enc(authSecret) }],
  support_threads: [{ id: "t1", collection_id: CID, user_id: "u1", client_email: "client@example.com", lang: "fr", status: "open", mode: "ai", human_last_at: null, category: null, priority: "normal", summary: null, unread_admin: 0, unread_client: 0 }],
  support_messages: [],
};
const say = (body: string) => { DB.clock = Math.max(DB.clock || 0, Date.now()) + 1000; DB.tables.support_messages.push({ id: crypto.randomUUID(), thread_id: "t1", author: "client", body, created_at: new Date(DB.clock).toISOString() }); };
const call = (jwt: string, body: unknown) => handler(new Request("https://f/support-chat", { method: "POST", headers: { Authorization: "Bearer " + jwt, origin: "https://app.legacy-shaper.com" }, body: JSON.stringify(body) }));
const replies = () => DB.tables.support_messages.filter((m: any) => m.author === "ai");

// 1. no assistant key yet: courteous acknowledgement, sorted, Dylan notified
Deno.env.delete("ANTHROPIC_API_KEY");
say("Bonjour, je n’arrive pas à télécharger l’image de Crimson Threshold");
let r = await call("jwt-client", { action: "reply", threadId: "t1" });
check(r.status === 200 && r.headers.get("Access-Control-Allow-Origin") === "https://app.legacy-shaper.com", "collector's call accepted (CORS for app.legacy-shaper.com)");
check(replies().length === 1 && replies()[0].body.includes("L’équipe Legacy Shaper y porte toute son attention"), "without assistant key (personal mode): personal acknowledgement in French");
check(DB.tables.support_threads[0].category === "bug", "message sorted as a technical matter");
check(pushes.length === 1 && pushes[0].payload.title === "client@example.com · The Aurelian Collection" && pushes[0].payload.body.startsWith("Bonjour, je n’arrive pas") && pushes[0].payload.url.endsWith("#messages/t1"), "Dylan's device receives a readable notification that opens the conversation");
check(/^vapid t=.+, k=/.test(pushes[0].headers.get("Authorization") || "") && pushes[0].headers.get("Content-Encoding") === "aes128gcm" && pushes[0].headers.get("Topic") === "t1", "notification signed (VAPID), encrypted (aes128gcm), grouped by conversation");
say("C’est sur l’iPhone");
await call("jwt-client", { action: "reply", threadId: "t1" });
check(replies().length === 1 && pushes.length === 2, "second message within the hour: no repeated acknowledgement, Dylan still told");

// 2. with the assistant
Deno.env.set("ANTHROPIC_API_KEY", "test-key");
aiAnswer = { reply: "Merci pour ces précisions. L’équipe s’en occupe et vous tient informé.", category: "bug", priority: "high", summary_fr: "Le client ne peut pas télécharger l’image de Crimson Threshold sur iPhone.", needs_team: true, artwork_id: "aur-01" };
say("Pouvez-vous regarder rapidement ? J’en ai besoin pour l’assurance demain.");
await call("jwt-client", { action: "reply", threadId: "t1" });
const a = aiCalls[0];
check(a && a.headers.get("x-api-key") === "test-key" && a.body.model === "claude-sonnet-5-5" && a.body.tool_choice.name === "respond", "assistant called with the key, model and the reply tool");
check(a.body.system.includes("aur-01 | Élise Marchetti | Crimson Threshold, 2014") && !a.body.system.includes("Secret Work"), "assistant knows only this collector's works (no other collection)");
const roles = a.body.messages.map((m: any) => m.role).join(",");
check(roles === "user,assistant,user" && a.body.messages[0].content.includes("télécharger"), "conversation passed in order, consecutive messages merged");
check(replies().length === 2 && replies()[1].body === aiAnswer.reply, "assistant's reply saved in the conversation");
check(DB.tables.support_threads[0].priority === "high" && DB.tables.support_threads[0].summary === aiAnswer.summary_fr, "summary and priority saved for Dylan");
check(pushes.length === 3 && pushes[2].headers.get("Urgency") === "high" && pushes[2].payload.body === aiAnswer.summary_fr, "urgent notification carries the summary");

// 3. Dylan has taken over: the assistant stays quiet
Object.assign(DB.tables.support_threads[0], { mode: "human", human_last_at: new Date().toISOString() });
DB.clock += 1000; DB.tables.support_messages.push({ id: "d1", thread_id: "t1", author: "system", body: "Dylan Lessel a rejoint la conversation.", created_at: new Date(DB.clock).toISOString() });
DB.clock += 1000; DB.tables.support_messages.push({ id: "d2", thread_id: "t1", author: "dylan", body: "Bonjour, c’est Dylan, je m’en occupe.", created_at: new Date(DB.clock).toISOString() });
say("Merci Dylan !");
r = await call("jwt-client", { action: "reply", threadId: "t1" });
check((await r.json()).mode === "human" && replies().length === 2 && aiCalls.length === 1, "Dylan in the conversation: no assistant reply");
check(pushes.length === 4 && pushes[3].payload.body === "Merci Dylan !", "Dylan is notified of the collector's message");

// 4. Dylan away for longer than the hand-back delay: the assistant resumes
DB.tables.support_threads[0].human_last_at = new Date(Date.now() - 20 * 60000).toISOString();
aiAnswer = { ...aiAnswer, reply: "Avec plaisir.", priority: "normal", category: "question", needs_team: false, summary_fr: "Remerciements." };
say("Une autre question : comment installer l’application ?");
await call("jwt-client", { action: "reply", threadId: "t1" });
check(DB.tables.support_threads[0].mode === "ai" && replies().length === 3, "after 10 minutes without Dylan, the assistant takes the conversation back");
const ctx2 = aiCalls[1].body.messages; check(ctx2.some((m: any) => m.role === "assistant" && m.content.includes("[Dylan Lessel] Bonjour, c’est Dylan")) && !ctx2.some((m: any) => m.content.includes("a rejoint")), "Dylan's own words are in the assistant's context, notices are not");

// 5. settings: only important messages / quiet hours
DB.tables.support_settings[0].notify = "important";
const before = pushes.length;
say("Merci beaucoup");
await call("jwt-client", { action: "reply", threadId: "t1" });
check(pushes.length === before, "'important only': a simple thank-you does not notify Dylan");
DB.tables.support_settings[0] = { ...DB.tables.support_settings[0], notify: "all", quiet_start: "00:00", quiet_end: "23:59" };
say("Encore merci");
await call("jwt-client", { action: "reply", threadId: "t1" });
check(pushes.length === before, "quiet hours: no notification for a normal message");
aiAnswer = { ...aiAnswer, priority: "high", needs_team: true, summary_fr: "Transport demain matin." };
say("Le transporteur arrive demain à 8 h");
await call("jwt-client", { action: "reply", threadId: "t1" });
check(pushes.length === before + 1, "quiet hours: an urgent message still reaches Dylan");
DB.tables.support_settings[0] = { ...DB.tables.support_settings[0], quiet_start: null, quiet_end: null };

// 6. strict separation and access
r = await call("jwt-other", { action: "reply", threadId: "t1" });
check(r.status === 404, "another collector cannot reach this conversation");
r = await call("nobody", { action: "reply", threadId: "t1" });
check(r.status === 401, "no session: refused");
r = await call("jwt-client", { action: "test" });
check(r.status === 403, "a collector cannot send Dylan a test notification");
r = await call("jwt-client", { action: "status" });
check(r.status === 403, "a collector cannot ask whether the assistant is on");
r = await call("jwt-dylan", { action: "status" });
check((await r.json()).ai === true, "status: assistant on when the key exists");
Deno.env.delete("ANTHROPIC_API_KEY");
r = await call("jwt-dylan", { action: "status" });
check((await r.json()).ai === false, "status: personal mode without the key");
Deno.env.set("ANTHROPIC_API_KEY", "test-key");
r = await call("jwt-dylan", { action: "test" });
check((await r.json()).sent === 1, "Dylan's test notification is sent");
pushStatus = 410; await call("jwt-dylan", { action: "test" });
check(DB.tables.push_subscriptions.length === 0, "a device that unsubscribed is removed");
r = await call("jwt-client", { action: "reply", threadId: "t1" });
check((await r.json()).skipped, "nothing new from the collector: no reply");
console.log(`\nALL ${ok} CHECKS PASSED`);
