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
      return false;
    }
    function from(table) {
      const f = []; let ord = null, single = false;
      const q = {
        select() { return q; },
        eq(k, v) { f.push(r => r[k] === v); return q; },
        in(k, arr) { f.push(r => arr.includes(r[k])); return q; },
        order(k, o) { ord = { k, asc: !(o && o.ascending === false) }; return q; },
        maybeSingle() { single = true; return q; },
        then(res, rej) {
          window.__calls.push(table);
          if (!net()) return fail().then(res, rej);
          const s = getSess();
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
    const storage = { from() { return {
      async download(path) {
        if (!net()) return { data: null, error: { message: "Failed to fetch" } };
        const s = getSess(); const d = SEED.tables.documents.find(x => x.storage_path === path);
        if (!d || !allowed("documents", d, s)) return { data: null, error: { message: "Object not found" } };
        return { data: new Blob([SEED.files[path] || "file"], { type: d.mime || "application/pdf" }), error: null };
      } }; } };
    return { from, auth, storage };
  }
  window.supabase = { createClient };
})();
