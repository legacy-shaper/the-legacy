/* In-browser mock of supabase-js for the Legacy Shaper client app tests.
   Emulates: email OTP sign-in (no sign-up), TOTP MFA for admins, row-level security
   (members read only their collection; expenses/documents only when visible_to_client),
   storage downloads, and network loss (window.__NET === false). */
(function () {
  const SEED = window.__SEED;
  const CODE = "42424242", TOTP = "123456";
  const net = () => window.__NET !== false;
  const fail = () => Promise.reject(new TypeError("Failed to fetch"));
  window.__calls = window.__calls || [];

  function createClient(url, key, opts) {
    const st = (opts && opts.auth && opts.auth.storage) || localStorage;
    const sk = (opts && opts.auth && opts.auth.storageKey) || "sb-auth";
    const getSess = () => { try { return JSON.parse(st.getItem(sk) || "null"); } catch (e) { return null; } };
    const setSess = s => { if (s) st.setItem(sk, JSON.stringify(s)); else st.removeItem(sk); };
    const userOf = s => s && SEED.users.find(u => u.id === s.uid);

    function allowed(table, row, s) {
      const u = userOf(s); if (!u) return false;
      const admin = u.role === "admin" && s.aal === "aal2";
      if (admin) return true;
      const member = cid => SEED.members.some(m => m.user_id === u.id && m.collection_id === cid);
      if (table === "profiles") return row.id === u.id;
      if (table === "collections") return member(row.id);
      if (table === "artworks") return row.collection_id && member(row.collection_id);
      if (table === "artwork_views") { const a = SEED.tables.artworks.find(x => x.id === row.artwork_id); return !!(a && a.collection_id && member(a.collection_id)); }
      if (table === "expenses" || table === "documents") return row.visible_to_client && row.collection_id && member(row.collection_id);
      if (table === "support_threads") return row.user_id === u.id && member(row.collection_id);
      if (table === "support_messages") { const th = (SEED.tables.support_threads || []).find(x => x.id === row.thread_id); return !!th && th.user_id === u.id && member(th.collection_id); }
      return false;
    }
    const missing = t => (t === "support_threads" || t === "support_messages") && !SEED.tables.support_threads;
    let clock = Date.parse("2026-10-08T09:00:00Z");
    const stamp = () => new Date(clock += 1000).toISOString();
    function afterMessage(m) { const th = SEED.tables.support_threads.find(x => x.id === m.thread_id);
      Object.assign(th, { last_author: m.author, unread_client: th.unread_client + (["ai", "dylan"].includes(m.author) ? 1 : 0), unread_admin: th.unread_admin + (m.author === "client" ? 1 : 0) }); }
    window.__supportReply = (tid, body, author) => { const m = { id: "m" + Math.random().toString(36).slice(2), thread_id: tid, author: author || "ai", body, created_at: stamp() }; SEED.tables.support_messages.push(m); afterMessage(m); };
    function from(table) {
      const f = []; let ord = null, single = false, ins = null;
      const q = {
        insert(row) { ins = row; return q; },
        select() { return q; },
        eq(k, v) { f.push(r => r[k] === v); return q; },
        in(k, arr) { f.push(r => arr.includes(r[k])); return q; },
        order(k, o) { ord = { k, asc: !(o && o.ascending === false) }; return q; },
        maybeSingle() { single = true; return q; },
        then(res, rej) {
          window.__calls.push(table);
          if (!net()) return fail().then(res, rej);
          if (missing(table)) return Promise.resolve({ data: null, error: { code: "PGRST205", message: "Could not find the table" } }).then(res, rej);
          const s = getSess();
          if (ins) {   // rule sm_client_write: a collector writes only 'client' messages in their own conversation
            const u = userOf(s); const th = (SEED.tables.support_threads || []).find(x => x.id === ins.thread_id);
            const okIns = table === "support_messages" && u && ins.author === "client" && th && th.user_id === u.id && SEED.members.some(m => m.user_id === u.id && m.collection_id === th.collection_id)
              && (!ins.attachment_path || ins.attachment_path.startsWith(u.id + "/"));
            if (!okIns) return Promise.resolve({ data: null, error: { message: "new row violates row-level security policy" } }).then(res, rej);
            const m = { id: "m" + Math.random().toString(36).slice(2), created_at: stamp(), ...ins }; SEED.tables.support_messages.push(m); afterMessage(m);
            return Promise.resolve({ data: null, error: null }).then(res, rej);
          }
          let rows = (SEED.tables[table] || []).filter(r => allowed(table, r, s)).filter(r => f.every(fn => fn(r)));
          if (ord) rows = rows.slice().sort((a, b) => String(a[ord.k] || "").localeCompare(String(b[ord.k] || "")) * (ord.asc ? 1 : -1));
          rows = JSON.parse(JSON.stringify(rows));
          return Promise.resolve({ data: single ? (rows[0] || null) : rows, error: null }).then(res, rej);
        }
      };
      return q;
    }
    const auth = {
      async signInWithOtp({ email, options }) {
        if (!net()) return fail();
        const u = SEED.users.find(x => x.email === email);
        if (!u) return { data: null, error: { message: "Signups not allowed for otp", status: 422 } };
        window.__lastOtp = { email, at: Date.now() }; return { data: {}, error: null };
      },
      async verifyOtp({ email, token, type }) {
        if (!net()) return fail();
        const u = SEED.users.find(x => x.email === email);
        if (!u || token !== CODE || !window.__lastOtp || window.__lastOtp.email !== email) return { data: null, error: { message: "Token has expired or is invalid", status: 403 } };
        const s = { uid: u.id, aal: "aal1" }; setSess(s); return { data: { session: s, user: { id: u.id, email: u.email } }, error: null };
      },
      async getSession() { const s = getSess(); return { data: { session: s ? { user: { id: s.uid } } : null }, error: null }; },
      async getUser() { if (!net()) return fail(); const s = getSess(); const u = userOf(s); return { data: { user: u ? { id: u.id, email: u.email } : null }, error: null }; },
      async signOut() { setSess(null); return { error: null }; },
      mfa: {
        async getAuthenticatorAssuranceLevel() { const s = getSess(); const u = userOf(s); return { data: { currentLevel: s ? s.aal : null, nextLevel: u && u.totp ? "aal2" : "aal1" }, error: null }; },
        async listFactors() { const u = userOf(getSess()); return { data: { totp: u && u.totp ? [{ id: "f1", status: "verified" }] : [], all: [] }, error: null }; },
        async challengeAndVerify({ factorId, code }) { if (code !== TOTP) return { data: null, error: { message: "Invalid TOTP code" } }; const s = getSess(); s.aal = "aal2"; setSess(s); return { data: {}, error: null }; }
      }
    };
    const storage = { from(bucket) { return {
      async upload(path, file) {
        const u = userOf(getSess()); if (!net()) return { error: { message: "Failed to fetch" } };
        if (bucket !== "support-files" || !u || !path.startsWith(u.id + "/")) return { error: { message: "denied" } };
        SEED.files[path] = await file.text(); (window.__uploads = window.__uploads || []).push({ path, type: file.type }); return { data: { path }, error: null };
      },
      async download(path) {
        if (bucket === "support-files") { const u = userOf(getSess()); if (!u || !path.startsWith(u.id + "/") || SEED.files[path] == null) return { data: null, error: { message: "not found" } };
          return { data: new Blob([SEED.files[path]], { type: "image/png" }), error: null }; }
        if (!net()) return { data: null, error: { message: "Failed to fetch" } };
        const s = getSess(); const d = SEED.tables.documents.find(x => x.storage_path === path);
        if (!d || !allowed("documents", d, s)) return { data: null, error: { message: "Object not found" } };
        return { data: new Blob([SEED.files[path] || "file"], { type: d.mime || "application/pdf" }), error: null };
      } }; } };
    async function rpc(name, args) {
      if (!net()) return fail();
      const u = userOf(getSess()); window.__calls.push("rpc:" + name);
      if (missing("support_threads")) return { data: null, error: { message: "function not found" } };
      if (name === "support_open_thread") {
        if (!u || !SEED.members.some(m => m.user_id === u.id && m.collection_id === args.cid)) return { data: null, error: { message: "forbidden" } };
        let th = SEED.tables.support_threads.find(x => x.user_id === u.id && x.collection_id === args.cid);
        if (!th) { th = { id: "t-" + u.id, collection_id: args.cid, user_id: u.id, lang: args.lng, status: "open", mode: "ai", unread_client: 0, unread_admin: 0 }; SEED.tables.support_threads.push(th); }
        return { data: JSON.parse(JSON.stringify(th)), error: null };
      }
      if (name === "support_mark_read") { const th = SEED.tables.support_threads.find(x => x.id === args.tid && u && x.user_id === u.id); if (th) th.unread_client = 0; return { data: null, error: null }; }
      return { data: null, error: { message: "unknown" } };
    }
    const functions = { async invoke(name, { body }) {
      (window.__invokes = window.__invokes || []).push({ name, body });
      if (!net()) return { error: { message: "Failed to fetch" } };
      if (name === "support-chat" && body.action === "reply") {
        const th = SEED.tables.support_threads.find(x => x.id === body.threadId);
        if (th && th.mode !== "human") setTimeout(() => window.__supportReply(th.id, window.__aiText || "Merci beaucoup, nous nous en occupons."), window.__aiDelay || 300);
        return { data: { ok: true }, error: null };
      }
      return { error: { message: "unknown" } };
    } };
    const channel = () => { const c = { on() { return c; }, subscribe() { return c; } }; return c; };
    return { from, auth, storage, rpc, functions, channel, removeChannel() {} };
  }
  window.supabase = { createClient };
})();
