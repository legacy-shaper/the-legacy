/* In-browser mock of supabase-js for The Legacy master app (tests only).
   master_docs store with updated_at, password "good-pass" + TOTP "123456" (aal2 required for data),
   collections / collection_members / profiles tables, and the collection-access function. */
(function () {
  const K = "mock-db";
  const load = () => { try { return JSON.parse(localStorage.getItem(K)) || null; } catch (e) { return null; } };
  let DB = load() || JSON.parse(JSON.stringify(window.__MASTER_SEED));
  const save = () => localStorage.setItem(K, JSON.stringify(DB));
  save();
  let tick = Date.parse("2026-10-06T10:00:00Z");
  const now = () => new Date(tick += 1000).toISOString();
  window.__mockDB = () => DB;
  window.__invokes = [];

  function createClient(url, key, opts) {
    const st = localStorage, sk = (opts && opts.auth && opts.auth.storageKey) || "sb";
    const sess = () => { try { return JSON.parse(st.getItem(sk) || "null"); } catch (e) { return null; } };
    const setSess = s => s ? st.setItem(sk, JSON.stringify(s)) : st.removeItem(sk);
    const aal2 = () => { const s = sess(); return s && s.aal === "aal2"; };
    function table(name) { if (name === "master_docs") return DB.docs; return DB.tables[name] || (DB.tables[name] = []); }
    function from(name) {
      const f = []; let ord = null, rng = null, mode = "select", payload = null, single = false;
      const rows = () => {
        if (!aal2()) return [];
        let r = table(name).filter(x => f.every(fn => fn(x)));
        if (ord) r = r.slice().sort((a, b) => String(a[ord.k]).localeCompare(String(b[ord.k])) * (ord.asc ? 1 : -1));
        if (rng) r = r.slice(rng[0], rng[1] + 1);
        return r;
      };
      const q = {
        select() { if (mode === "select") mode = "select"; return q; },
        eq(k, v) { f.push(r => r[k] === v); return q; },
        in(k, a) { f.push(r => a.includes(r[k])); return q; },
        order(k, o) { ord = { k, asc: !(o && o.ascending === false) }; return q; },
        range(a, b) { rng = [a, b]; return q; },
        maybeSingle() { single = true; return q; }, single() { single = true; return q; },
        upsert(obj) { mode = "upsert"; payload = obj; return q; },
        insert(obj) { mode = "insert"; payload = obj; return q; },
        update(obj) { mode = "update"; payload = obj; return q; },
        delete() { mode = "delete"; return q; },
        then(res, rej) {
          if (!aal2()) return Promise.resolve({ data: null, error: { message: "permission denied" } }).then(res, rej);
          const t = table(name);
          if (mode === "upsert") {
            const arr = Array.isArray(payload) ? payload : [payload];
            arr.forEach(o => { const i = t.findIndex(x => x.coll === o.coll && x.id === o.id); const row = { ...o, updated_at: now() }; if (i >= 0) t[i] = row; else t.push(row); });
            save(); return Promise.resolve({ data: null, error: null }).then(res, rej);
          }
          if (mode === "insert") { const row = { id: crypto.randomUUID(), ...payload }; t.push(row); save(); return Promise.resolve({ data: single ? row : [row], error: null }).then(res, rej); }
          if (mode === "update") { t.filter(x => f.every(fn => fn(x))).forEach(x => Object.assign(x, payload)); save(); return Promise.resolve({ data: null, error: null }).then(res, rej); }
          if (mode === "delete") { const keep = t.filter(x => !f.every(fn => fn(x))); t.length = 0; keep.forEach(x => t.push(x)); save(); return Promise.resolve({ data: null, error: null }).then(res, rej); }
          const r = JSON.parse(JSON.stringify(rows()));
          return Promise.resolve({ data: single ? (r[0] || null) : r, error: null }).then(res, rej);
        }
      };
      return q;
    }
    const auth = {
      async signInWithPassword({ email, password }) { if (password !== "good-pass") return { error: { message: "Invalid login credentials" } }; setSess({ email, aal: "aal1" }); return { data: {}, error: null }; },
      async getSession() { const s = sess(); return { data: { session: s } }; },
      async signOut() { setSess(null); return {}; },
      mfa: {
        async getAuthenticatorAssuranceLevel() { const s = sess(); return { data: { currentLevel: s ? s.aal : null, nextLevel: "aal2" } }; },
        async listFactors() { return { data: { totp: [{ id: "f1", status: "verified" }], all: [{ id: "f1", status: "verified" }] } }; },
        async challengeAndVerify({ code }) { if (code !== "123456") return { error: { message: "bad" } }; const s = sess(); s.aal = "aal2"; setSess(s); return { data: {} }; },
        async enroll() { return { error: { message: "n/a" } }; }, async unenroll() { return {}; }
      }
    };
    const channel = () => { const c = { on() { return c; }, subscribe(cb) { setTimeout(() => cb && cb("SUBSCRIBED"), 10); return c; } }; return c; };
    const storage = { from() { return {
      async upload(path, blob) { DB.files[path] = await blob.text(); save(); return { error: null }; },
      async download(path) { return DB.files[path] != null ? { data: new Blob([DB.files[path]]) } : { error: { message: "not found" } }; },
      async remove() { return {}; } }; } };
    const functions = { async invoke(name, { body }) {
      window.__invokes.push({ name, body });
      if (!aal2()) return { error: { message: "forbidden" } };
      const m = DB.tables.collection_members;
      if (body.action === "list") return { data: { members: m.filter(x => x.collection_id === body.collectionId).map(x => ({ ...x, email: (DB.tables.profiles.find(p => p.id === x.user_id) || {}).email })) } };
      if (body.action === "grant") { let p = DB.tables.profiles.find(x => x.email === body.email); if (!p) { p = { id: "u-" + DB.tables.profiles.length, email: body.email, role: "client" }; DB.tables.profiles.push(p); }
        if (!m.some(x => x.collection_id === body.collectionId && x.user_id === p.id)) m.push({ collection_id: body.collectionId, user_id: p.id }); save(); return { data: { ok: true } }; }
      if (body.action === "revoke") { DB.tables.collection_members = m.filter(x => !(x.collection_id === body.collectionId && x.user_id === body.userId)); save(); return { data: { ok: true } }; }
      return { error: { message: "action" } };
    } };
    return { from, auth, channel, storage, functions, rpc: async () => ({ data: null, error: null }), removeChannel() {} };
  }
  window.supabase = { createClient };
})();
