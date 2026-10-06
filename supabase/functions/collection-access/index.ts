// Legacy Shaper — collection access (admin only).
// POST { action: "grant", collectionId, email, label? }  -> creates the collector's account if needed (no password,
//        email confirmed: they sign in with a six-digit code sent by email) and gives access to that collection only.
// POST { action: "revoke", collectionId, userId }       -> removes access to that collection.
// POST { action: "list", collectionId }                 -> members with their email.
// The caller must be Dylan: profile role "admin" and a session verified with the authenticator (aal2).
import { createClient } from "npm:@supabase/supabase-js@2.45.4";

const URL_ = Deno.env.get("SUPABASE_URL")!;
const SERVICE = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const ANON = Deno.env.get("SUPABASE_ANON_KEY")!;
const ORIGINS = ["https://legacy-shaper.github.io", "https://app.legacy-shaper.com", "https://legacy-shaper.com"];

function cors(req: Request) {
  const o = req.headers.get("origin") || "";
  return {
    "Access-Control-Allow-Origin": ORIGINS.includes(o) ? o : ORIGINS[0],
    "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Vary": "Origin",
  };
}
const json = (req: Request, status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { ...cors(req), "Content-Type": "application/json" } });

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors(req) });
  if (req.method !== "POST") return json(req, 405, { error: "method" });
  const auth = req.headers.get("Authorization") || "";
  const jwt = auth.replace(/^Bearer\s+/i, "");
  if (!jwt) return json(req, 401, { error: "auth" });

  const caller = createClient(URL_, ANON, { global: { headers: { Authorization: auth } }, auth: { persistSession: false } });
  const { data: u } = await caller.auth.getUser(jwt);
  if (!u?.user) return json(req, 401, { error: "auth" });
  const admin = createClient(URL_, SERVICE, { auth: { persistSession: false } });
  // Same rule as the database (private.is_admin(): admin profile + authenticator-verified session):
  // company_settings is readable only by such a session.
  const { data: gate, error: gateErr } = await caller.from("company_settings").select("id").limit(1);
  if (!gate || gate.length !== 1) { console.error("forbidden", gateErr?.message || "no admin session"); return json(req, 403, { error: "forbidden" }); }

  let body: any = {};
  try { body = await req.json(); } catch { return json(req, 400, { error: "body" }); }
  const cid = String(body.collectionId || "");
  const { data: coll, error: collErr } = await admin.from("collections").select("id,name").eq("id", cid).maybeSingle();
  if (!coll) { console.error("collection", cid, collErr?.message || "not found"); return json(req, 404, { error: "collection" }); }

  if (body.action === "list") {
    const { data: m } = await admin.from("collection_members").select("user_id,label,created_at").eq("collection_id", cid);
    const ids = (m || []).map((x) => x.user_id);
    const { data: p } = ids.length ? await admin.from("profiles").select("id,email,full_name").in("id", ids) : { data: [] as any[] };
    return json(req, 200, { members: (m || []).map((x) => ({ ...x, email: p?.find((y) => y.id === x.user_id)?.email || "" })) });
  }

  if (body.action === "revoke") {
    const uid = String(body.userId || "");
    await admin.from("collection_members").delete().eq("collection_id", cid).eq("user_id", uid);
    return json(req, 200, { ok: true });
  }

  if (body.action === "grant") {
    const email = String(body.email || "").trim().toLowerCase();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return json(req, 400, { error: "email" });
    let userId = "";
    const { data: existing } = await admin.from("profiles").select("id").eq("email", email).maybeSingle();
    if (existing) userId = existing.id;
    else {
      const { data: created, error } = await admin.auth.admin.createUser({ email, email_confirm: true, user_metadata: { source: "legacy-shaper" } });
      if (created?.user) userId = created.user.id;
      else {
        // already registered in auth but without a profile: look it up
        for (let page = 1; page <= 20 && !userId; page++) {
          const { data: list } = await admin.auth.admin.listUsers({ page, perPage: 200 });
          const hit = list?.users?.find((x) => (x.email || "").toLowerCase() === email);
          if (hit) userId = hit.id;
          if (!list || list.users.length < 200) break;
        }
        if (!userId) return json(req, 500, { error: error?.message || "create" });
      }
    }
    const { data: p } = await admin.from("profiles").select("id,role").eq("id", userId).maybeSingle();
    if (!p) await admin.from("profiles").insert({ id: userId, email, role: "client", full_name: body.label || null });
    await admin.from("collection_members").upsert({ collection_id: cid, user_id: userId, label: body.label || null }, { onConflict: "collection_id,user_id" });
    return json(req, 200, { ok: true, userId, email });
  }
  return json(req, 400, { error: "action" });
});
