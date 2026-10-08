-- 006 — Emballage & caisse (crating). The full section lives on the artwork in master_docs (artworks.crating, Legacy Shaper only).
-- When Dylan ticks "Visible par le client" and the work is in a client collection, a read-only subset reaches the client app:
-- status, crates (type, features, dimensions, weights, marking), crate location, handling, orientation and the client note.
-- Never copied: maker, date, quote, linked bill, internal notes. Crate photos / packing lists go to public.documents (kind 'crating'),
-- shown to the client only when the section is visible and the file is not marked internal.
-- The sync function is patched in place (exact text replacements, each checked) so nothing else in it changes.

alter table public.artworks add column if not exists crating jsonb;

create or replace function private.crating_public(c jsonb) returns jsonb
language sql immutable set search_path to '' as $$
  select case when jsonb_typeof(c) = 'object' and c->>'visibleToClient' = 'true' then jsonb_strip_nulls(jsonb_build_object(
    'status', nullif(c->>'status',''), 'where', nullif(c->>'where',''), 'handling', nullif(c->>'handling',''),
    'orientation', nullif(c->>'orientation',''), 'clientNote', nullif(c->>'clientNote',''),
    'crates', (select jsonb_agg(jsonb_strip_nulls(jsonb_build_object(
        'type', nullif(x->>'type',''),
        'features', case when jsonb_typeof(x->'features') = 'array' and jsonb_array_length(x->'features') > 0 then x->'features' end,
        'h', private.nnum(x->>'h'), 'w', private.nnum(x->>'w'), 'd', private.nnum(x->>'d'),
        'kg', private.nnum(x->>'kg'), 'tare', private.nnum(x->>'tare'), 'ref', nullif(x->>'ref',''))))
      from jsonb_array_elements(case when jsonb_typeof(c->'crates') = 'array' then c->'crates' else '[]'::jsonb end) x)
  )) end
$$;

do $migration$
declare src text; n text;
begin
  src := pg_get_functiondef('private.sync_master_doc'::regproc);
  if position('crating_public' in src) > 0 then
    raise notice 'sync_master_doc already handles crating';
    return;
  end if;
  n := replace(src, 'notes, thumb, scale_view)', 'notes, thumb, scale_view, crating)');
  if n = src then raise exception '006: column list not found (run 005 first)'; end if; src := n;
  n := replace(src,
    'case when jsonb_typeof(d->''scaleView'') = ''object'' then d->''scaleView'' end)',
    'case when jsonb_typeof(d->''scaleView'') = ''object'' then d->''scaleView'' end,
        case when cid is not null then private.crating_public(d->''crating'') end)');
  if n = src then raise exception '006: values list not found'; end if; src := n;
  n := replace(src, 'scale_view=excluded.scale_view;', 'scale_view=excluded.scale_view, crating=excluded.crating;');
  if n = src then raise exception '006: update list not found'; end if; src := n;
  n := replace(src,
    '    -- the work changed collection: its expenses and documents follow',
    '    -- crate photos and packing lists (Emballage & caisse)
    keep := array(select ''files/''||(x->>''id'') from jsonb_array_elements(case when jsonb_typeof(d->''crating''->''files'') = ''array'' then d->''crating''->''files'' else ''[]''::jsonb end) x where coalesce(x->>''id'','''') <> '''');
    delete from public.documents where artwork_id = i and kind = ''crating'' and not (storage_path = any(keep));
    for f in select * from jsonb_array_elements(case when jsonb_typeof(d->''crating''->''files'') = ''array'' then d->''crating''->''files'' else ''[]''::jsonb end) loop
      continue when coalesce(f->>''id'','''') = '''';
      insert into public.documents(kind,name,mime,size,storage_path,artwork_id,collection_id,visible_to_client)
      values (''crating'', coalesce(nullif(f->>''name'',''''),''document''), f->>''type'', private.nnum(f->>''size'')::bigint, ''files/''||(f->>''id''), i, cid,
        cid is not null and d->''crating''->>''visibleToClient'' = ''true'' and coalesce(f->>''internal'','''') <> ''true'')
      on conflict (storage_path) do update set name=excluded.name, mime=excluded.mime, size=excluded.size, artwork_id=excluded.artwork_id,
        collection_id=excluded.collection_id, visible_to_client=excluded.visible_to_client, kind=excluded.kind;
    end loop;
    -- the work changed collection: its expenses and documents follow');
  if n = src then raise exception '006: collection-change comment not found'; end if; src := n;
  execute src;
end
$migration$;

-- fill the new column for the works already saved
update public.master_docs set data = data where coll = 'artworks';
