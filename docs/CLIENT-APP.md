# Legacy Shaper — client collection app (state at 6 Oct 2026, 15:35)

Hand-over note: everything needed to resume work in a new conversation. No secret is stored here.

## What exists and works (tested by Dylan on his iPhone, 6 Oct 2026)
- **Client app** live at **https://app.legacy-shaper.com** (GitHub repo `legacy-shaper/app`, GitHub Pages, CNAME, HTTPS enforced).
  Source: `tools/client.html` + `tools/build_client.py` in this repo → `client/` → copied to the `legacy-shaper/app` repo (clone /home/claude/app) and pushed to main.
- Sign-in: email → **8-digit code** by email (Supabase email OTP, `shouldCreateUser:false`) → collection opens. Admin (Dylan) also gets the TOTP step and a collection picker.
- Install: Safari → Partager → Sur l'écran d'accueil. The proposed name is the collection's short name (e.g. "Aurelian"):
  written at page parse time from `localStorage["ls-home"]`, one automatic reload after sign-in, no manifest linked once a collection is known.
- Offline: the device copy opens first (IndexedDB `ls-client`), photos stored as data URLs (`img:<viewId>`), service worker caches shell + libs
  with network timeouts (3.5 s navigation). iOS home-screen apps have their own storage: the installed app must be opened once online.
- "Ordinateur partagé" option: nothing kept on the device (sessionStorage only).
- Tabs: Overview, Works (search, location filter), Locations, Expenses (per year, per category, general/per work), Documents. Work page: views, facts,
  inventory sheet (print), image download. Export zip (CSV + images). EN/FR.
- Co-owners (other session, commit 63591f1, SQL 003 applied): client sees names + % only, per-work visibility switch.

## Back office (master app The Legacy)
- Société → **Collections clients**: create a collection, rename, give access by email ("Donner l'accès"), remove access.
- Artwork card → "Collection client" block (collectionId + client fields). Expense editor → collection + "visible par le collectionneur".
- Edge function **collection-access** (v4, verify_jwt on): admin check = caller can read `company_settings` under RLS; tables read/written with the
  caller's own session (service_role has no table grants on purpose); service key used only for `auth.admin.createUser`. Logs: `console.error` per step.

## Supabase settings (project uinwjwooodacuahqaowf)
- SQL applied by Dylan: 001_client_collections, 002_demo_collection, 003_co_owners. (Claude's DDL calls are "cancelled": prepare SQL, Dylan runs it.)
- Custom SMTP: smtp.gmail.com:465, user dylan@legacy-shaper.com, Google **app password** (Dylan only; never seen by Claude), sender office@legacy-shaper.com "Legacy Shaper".
  The app password depends on Google 2-Step Verification staying ON for dylan@. If codes stop: auth logs show `535 Username and Password not accepted`
  → Dylan creates a new app password (myaccount.google.com/apppasswords) and types it in Auth → Emails → SMTP Settings → Save changes.
- Email template "Magic Link": `supabase/email-access-code.html` (bilingual, logo https://app.legacy-shaper.com/email-logo.png).
- Demo: "The Aurelian Collection" (id a0e1d2c3-0000-4000-8000-00000000d3e0), member office@legacy-shaper.com (role client).

## Tests (zero failure before publishing)
- `python3 tests/test_client.py` (62 checks, Supabase mock), `python3 tests/test_client_offline.py` (real service worker, no network, photos),
  `python3 tests/test_master_collections.py`, `python3 tests/test_master_coowners.py`.

## Next steps
1. Design review of the client app with Dylan on his iPhone (he dictates remarks; fix, test, publish).
2. Client invitation email (Legacy Shaper charter, positive vocabulary, signature): install on iPhone / iPad / Mac, open once online,
   Face ID later, legacy-shaper.com → "Accès membre" on another computer. Draft shown to Dylan before any sending.
3. Site Supabase **Site URL**: set to https://app.legacy-shaper.com (still http://localhost:3000).
4. Before the first real client: dedicated sending service (Resend or Postmark) instead of Gmail SMTP, and a daily check of auth logs for failed code emails.
5. Face ID (passkeys) once the final domain is settled; legacy-shaper.com site (EN/FR/AR) with "Accès membre"; apex DNS still at GoDaddy Website Builder.
6. Master shows "0 œuvre(s)" for the demo collection (demo artworks are not in master_docs) — optional.
