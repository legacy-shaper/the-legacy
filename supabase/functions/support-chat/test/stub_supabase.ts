// Minimal in-memory stand-in for supabase-js, for local tests of the function (not deployed).
// Row rules follow 004_support_chat.sql: a collector reaches only their own conversation; the service key reaches everything.
export const DB: any = (globalThis as any).__DB = (globalThis as any).__DB || { tables: {}, users: {}, rpc: {} };
const T = (n: string) => DB.tables[n] || (DB.tables[n] = []);
export function createClient(_url: string, key: string, opts: any = {}) {
  const authH: string = opts?.global?.headers?.Authorization || "";
  const service = key === "SERVICE";
  const uid = service ? null : DB.users[authH.replace(/^Bearer\s+/i, "")]?.id || null;
  const admin = !service && DB.users[authH.replace(/^Bearer\s+/i, "")]?.admin;
  const member = (cid: string) => (T("collection_members")).some((m: any) => m.user_id === uid && m.collection_id === cid);
  const visible = (t: string, r: any) => {
    if (service || admin) return true;
    if (t === "support_threads") return r.user_id === uid && member(r.collection_id);
    if (t === "support_messages") { const th = T("support_threads").find((x: any) => x.id === r.thread_id); return !!th && th.user_id === uid && member(th.collection_id); }
    if (t === "collections") return member(r.id);
    if (t === "artworks") return member(r.collection_id);
    if (t === "company_settings") return false;
    return false;
  };
  function from(t: string) {
    const f: ((r: any) => boolean)[] = []; let mode = "select", payload: any = null, single = false, ord: any = null, lim = 0;
    const q: any = {
      select() { return q; }, eq(k: string, v: any) { f.push((r) => r[k] === v); return q; },
      order(k: string, o: any) { ord = { k, asc: !(o && o.ascending === false) }; return q; }, limit(n: number) { lim = n; return q; },
      maybeSingle() { single = true; return q; }, update(p: any) { mode = "update"; payload = p; return q; },
      insert(p: any) { mode = "insert"; payload = p; return q; }, delete() { mode = "delete"; return q; },
      then(res: any, rej: any) {
        try {
          if (mode === "insert") {
            if (!service) throw new Error("insert not allowed in stub");
            DB.clock = Math.max(DB.clock || 0, Date.now()) + 1000; const row = { id: crypto.randomUUID(), created_at: new Date(DB.clock).toISOString(), ...payload }; T(t).push(row);
            if (t === "support_messages") { const th = T("support_threads").find((x: any) => x.id === row.thread_id);
              Object.assign(th, { last_author: row.author, unread_client: th.unread_client + (["ai", "dylan"].includes(row.author) ? 1 : 0) }); }
            return Promise.resolve({ data: null, error: null }).then(res, rej);
          }
          let rows = T(t).filter((r: any) => visible(t, r)).filter((r: any) => f.every((fn) => fn(r)));
          if (mode === "update") { if (!(service || admin)) rows = []; rows.forEach((r: any) => Object.assign(r, payload)); return Promise.resolve({ data: null, error: null }).then(res, rej); }
          if (mode === "delete") { DB.tables[t] = T(t).filter((r: any) => !rows.includes(r)); return Promise.resolve({ data: null, error: null }).then(res, rej); }
          if (ord) rows = rows.slice().sort((a: any, b: any) => String(a[ord.k]).localeCompare(String(b[ord.k])) * (ord.asc ? 1 : -1));
          if (lim) rows = rows.slice(0, lim);
          rows = JSON.parse(JSON.stringify(rows));
          return Promise.resolve({ data: single ? rows[0] || null : rows, error: null }).then(res, rej);
        } catch (e) { return Promise.resolve({ data: null, error: { message: String(e) } }).then(res, rej); }
      },
    };
    return q;
  }
  return {
    from,
    rpc: async (n: string) => service && DB.rpc[n] !== undefined ? { data: DB.rpc[n], error: null } : { data: null, error: { message: "denied" } },
    auth: { getUser: async (jwt: string) => ({ data: { user: DB.users[jwt] ? { id: DB.users[jwt].id } : null } }) },
  };
}
