-- 001 — Client collections (Legacy Shaper client app)
alter table public.artworks
  add column if not exists acquisition_date date,
  add column if not exists acquisition_price numeric,
  add column if not exists acquisition_currency text,
  add column if not exists acquisition_source text,
  add column if not exists location_since date;

alter table public.collections
  add column if not exists subtitle text,
  add column if not exists cover_artwork_id text;

create index if not exists artworks_collection_idx on public.artworks(collection_id);
create index if not exists expenses_collection_idx on public.expenses(collection_id);
create index if not exists expenses_artwork_idx on public.expenses(artwork_id);
create index if not exists documents_collection_idx on public.documents(collection_id);
create index if not exists documents_expense_idx on public.documents(expense_id);
create index if not exists documents_artwork_idx on public.documents(artwork_id);
create index if not exists documents_invoice_idx on public.documents(invoice_id);
create index if not exists artwork_views_artwork_idx on public.artwork_views(artwork_id);
create index if not exists collection_members_user_idx on public.collection_members(user_id);

create or replace function private.coll_id(t text)
returns uuid language sql stable security definer set search_path to '' as $$
  select c.id from public.collections c where t is not null and t <> '' and (c.id::text = t or c.slug = t) limit 1
$$;
revoke all on function private.coll_id(text) from public, anon, authenticated;

CREATE OR REPLACE FUNCTION private.sync_master_doc()
 RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path TO ''
AS $function$
declare d jsonb; c text; i text; aid text; cid uuid; f jsonb; keep text[]; vis boolean;
begin
  if tg_op = 'DELETE' then
    c := old.coll; i := old.id;
    if c = 'contacts' then delete from public.contacts where id = i;
    elsif c = 'artworks' then delete from public.artworks where id = i;
    elsif c = 'invoices' then delete from public.invoices where id = i;
    elsif c = 'expenses' then delete from public.expenses where id = i;
    elsif c like 'artworks/%/views' then delete from public.artwork_views where src_id = split_part(c,'/',2)||'/'||i;
    end if;
    return old;
  end if;
  d := new.data; c := new.coll; i := new.id;
  if c = 'settings' and i = 'company' then
    insert into public.company_settings(id,data) values (1,d) on conflict (id) do update set data = excluded.data;
  elsif c = 'contacts' then
    insert into public.contacts(id,name,company,email,phone,address,trn,notes)
    values (i, coalesce(nullif(d->>'name',''),nullif(d->>'company',''),'—'), d->>'company', d->>'email', d->>'phone', d->>'address', d->>'trn', d->>'notes')
    on conflict (id) do update set name=excluded.name, company=excluded.company, email=excluded.email, phone=excluded.phone, address=excluded.address, trn=excluded.trn, notes=excluded.notes;
  elsif c = 'artworks' then
    cid := private.coll_id(d->>'collectionId');
    insert into public.artworks(id, collection_id, ref, artist, title, year, medium, dimensions, category, edition_type, edition_number, owner_name, owner_contact_id,
        ownership_share, ownership_note, location_text, location_since, provenance, exhibitions, literature, condition, insured_value, insured_currency,
        acquisition_date, acquisition_price, acquisition_currency, acquisition_source, notes, thumb)
    values (i, cid, d->>'ref', d->>'artist', d->>'title', d->>'year', d->>'medium', d->>'dimensions', d->>'category', d->>'editionType', d->>'editionNumber', d->>'owner',
        (select id from public.contacts where id = nullif(d->>'ownerContactId','')),
        coalesce(private.nnum(d->>'ownershipShare'),100), nullif(d->>'ownershipNote',''),
        coalesce(nullif(d->>'clientLocation',''), d->>'location'), private.ndate(d->>'locationSince'),
        d->>'provenance', nullif(d->>'exhibitions',''), nullif(d->>'literature',''), nullif(d->>'condition',''),
        private.nnum(d->>'insuredValue'), nullif(d->>'insuredCurrency',''),
        private.ndate(d->>'acqDate'), private.nnum(d->>'acqPrice'), nullif(d->>'acqCurrency',''), nullif(d->>'acqSource',''),
        -- internal notes never reach a client collection: only clientNotes do
        case when cid is null then d->>'notes' else nullif(d->>'clientNotes','') end, d->>'photo')
    on conflict (id) do update set collection_id=excluded.collection_id, ref=excluded.ref, artist=excluded.artist, title=excluded.title, year=excluded.year, medium=excluded.medium,
      dimensions=excluded.dimensions, category=excluded.category, edition_type=excluded.edition_type, edition_number=excluded.edition_number, owner_name=excluded.owner_name,
      owner_contact_id=excluded.owner_contact_id, ownership_share=excluded.ownership_share, ownership_note=excluded.ownership_note, location_text=excluded.location_text,
      location_since=excluded.location_since, provenance=excluded.provenance, exhibitions=excluded.exhibitions, literature=excluded.literature, condition=excluded.condition,
      insured_value=excluded.insured_value, insured_currency=excluded.insured_currency, acquisition_date=excluded.acquisition_date, acquisition_price=excluded.acquisition_price,
      acquisition_currency=excluded.acquisition_currency, acquisition_source=excluded.acquisition_source, notes=excluded.notes, thumb=excluded.thumb;
    insert into public.artwork_private(artwork_id,status,price,cost,currency,discount,broker,internal_notes)
    values (i, d->>'status', private.nnum(d->>'price'), private.nnum(d->>'cost'), d->>'currency', private.nnum(d->>'discount'), d->>'broker', d->>'notes')
    on conflict (artwork_id) do update set status=excluded.status, price=excluded.price, cost=excluded.cost, currency=excluded.currency, discount=excluded.discount,
      broker=excluded.broker, internal_notes=excluded.internal_notes;
  elsif c = 'invoices' then
    insert into public.invoices(id,number,date,due,paid_date,status,currency,lang,vat_mode,vat_rate,discount,contact_id,client,items,payments,terms,reference,fx_aed)
    values (i, nullif(d->>'number',''), private.ndate(d->>'date'), private.ndate(d->>'due'), private.ndate(d->>'paidDate'),
      case when d->>'status' in ('draft','sent','paid') then d->>'status' else 'draft' end, d->>'currency', d->>'lang', d->>'vatMode', private.nnum(d->>'vatRate'), private.nnum(d->>'discount'),
      (select id from public.contacts where id = nullif(d->>'contactId','')), d->'client', coalesce(d->'items','[]'::jsonb), coalesce(d->'payments','[]'::jsonb), d->>'terms', d->>'reference', private.nnum(d->>'fxAED'))
    on conflict (id) do update set number=excluded.number, date=excluded.date, due=excluded.due, paid_date=excluded.paid_date, status=excluded.status, currency=excluded.currency, lang=excluded.lang,
      vat_mode=excluded.vat_mode, vat_rate=excluded.vat_rate, discount=excluded.discount, contact_id=excluded.contact_id, client=excluded.client, items=excluded.items, payments=excluded.payments,
      terms=excluded.terms, reference=excluded.reference, fx_aed=excluded.fx_aed;
  elsif c = 'expenses' then
    aid := (select id from public.artworks where id = nullif(d->>'artworkId',''));
    cid := coalesce(private.coll_id(d->>'collectionId'), (select collection_id from public.artworks where id = aid));
    vis := coalesce((d->>'visibleToClient') = 'true', false) and cid is not null;
    insert into public.expenses(id,supplier,ref,label,category,date,due,amount,currency,fx_usd,fx,status,payments,invoice_id,artwork_id,collection_id,visible_to_client,notes)
    values (i, d->>'supplier', d->>'ref', d->>'label', d->>'category', private.ndate(d->>'date'), private.ndate(d->>'due'), private.nnum(d->>'amount'), d->>'currency',
      private.nnum(d->>'fxUsd'), d->>'fx', case when d->>'status' in ('due','paid') then d->>'status' else 'due' end, coalesce(d->'payments','[]'::jsonb),
      (select id from public.invoices where id = nullif(d->>'invoiceId','')), aid, cid, vis, d->>'notes')
    on conflict (id) do update set supplier=excluded.supplier, ref=excluded.ref, label=excluded.label, category=excluded.category, date=excluded.date, due=excluded.due, amount=excluded.amount,
      currency=excluded.currency, fx_usd=excluded.fx_usd, fx=excluded.fx, status=excluded.status, payments=excluded.payments, invoice_id=excluded.invoice_id, artwork_id=excluded.artwork_id,
      collection_id=excluded.collection_id, visible_to_client=excluded.visible_to_client, notes=excluded.notes;
    keep := array(select 'files/'||(x->>'id') from jsonb_array_elements(coalesce(d->'files','[]'::jsonb)) x where coalesce(x->>'id','') <> '');
    delete from public.documents where expense_id = i and not (storage_path = any(keep));
    for f in select * from jsonb_array_elements(coalesce(d->'files','[]'::jsonb)) loop
      continue when coalesce(f->>'id','') = '';
      insert into public.documents(kind,name,mime,size,storage_path,artwork_id,expense_id,collection_id,visible_to_client)
      values (case when d->>'category'='art' then 'purchase_invoice' else 'invoice' end, coalesce(nullif(f->>'name',''),'document'), f->>'type',
        private.nnum(f->>'size')::bigint, 'files/'||(f->>'id'), aid, i, cid, vis)
      on conflict (storage_path) do update set name=excluded.name, mime=excluded.mime, size=excluded.size, artwork_id=excluded.artwork_id,
        expense_id=excluded.expense_id, collection_id=excluded.collection_id, visible_to_client=excluded.visible_to_client, kind=excluded.kind;
    end loop;
  elsif c like 'artworks/%/views' then
    aid := split_part(c,'/',2);
    if exists (select 1 from public.artworks where id = aid) then
      insert into public.artwork_views(artwork_id, src_id, photo) values (aid, aid||'/'||i, d->>'photo')
      on conflict (src_id) do update set photo = excluded.photo;
    end if;
  end if;
  return new;
end $function$;
