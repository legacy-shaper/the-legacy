-- 007 — Dimensions avec cadre (framed dimensions), optional, for paintings, works on paper and photographs.
-- Saved in The Legacy on the artwork (master_docs: artworks.dimsFramed). Client collections receive it in public.artworks.dimensions_framed
-- (never for sculptures, installations or furniture). The sync function is patched in place (exact text replacements, each checked).

alter table public.artworks add column if not exists dimensions_framed text;

do $migration$
declare src text; n text;
begin
  src := pg_get_functiondef('private.sync_master_doc'::regproc);
  if position('dimensions_framed' in src) > 0 then
    raise notice 'sync_master_doc already handles dimensions_framed';
    return;
  end if;
  n := replace(src, 'notes, thumb, scale_view, crating)', 'notes, thumb, scale_view, crating, dimensions_framed)');
  if n = src then raise exception '007: column list not found (run 006 first)'; end if; src := n;
  n := replace(src,
    'case when cid is not null then private.crating_public(d->''crating'') end)',
    'case when cid is not null then private.crating_public(d->''crating'') end,
        case when coalesce(d->>''category'','''') not in (''sculpture'',''installation'',''furniture'') then nullif(btrim(d->>''dimsFramed''),'''') end)');
  if n = src then raise exception '007: values list not found'; end if; src := n;
  n := replace(src, 'crating=excluded.crating;', 'crating=excluded.crating, dimensions_framed=excluded.dimensions_framed;');
  if n = src then raise exception '007: update list not found'; end if; src := n;
  execute src;
end
$migration$;

-- fill the new column for the works already saved
update public.master_docs set data = data where coll = 'artworks';
