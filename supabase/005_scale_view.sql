-- 005 — View at scale: the composition Dylan sets in The Legacy (wall colour, position of the work and the chair)
-- reaches the client collections. Adds artworks.scale_view and copies artworks.scaleView from master_docs into it.
-- The sync function is patched in place (exact text replacements, each checked) so nothing else in it changes.

alter table public.artworks add column if not exists scale_view jsonb;

do $migration$
declare src text; n text;
begin
  src := pg_get_functiondef('private.sync_master_doc'::regproc);
  if position('scale_view' in src) > 0 then
    raise notice 'sync_master_doc already handles scale_view';
    return;
  end if;
  n := replace(src,
    'acquisition_date, acquisition_price, acquisition_currency, acquisition_source, notes, thumb)',
    'acquisition_date, acquisition_price, acquisition_currency, acquisition_source, notes, thumb, scale_view)');
  if n = src then raise exception '005: column list not found'; end if; src := n;
  n := replace(src,
    'case when cid is null then d->>''notes'' else nullif(d->>''clientNotes'','''') end, d->>''photo'')',
    'case when cid is null then d->>''notes'' else nullif(d->>''clientNotes'','''') end, d->>''photo'',
        case when jsonb_typeof(d->''scaleView'') = ''object'' then d->''scaleView'' end)');
  if n = src then raise exception '005: values list not found'; end if; src := n;
  n := replace(src,
    'notes=excluded.notes, thumb=excluded.thumb;',
    'notes=excluded.notes, thumb=excluded.thumb, scale_view=excluded.scale_view;');
  if n = src then raise exception '005: update list not found'; end if; src := n;
  execute src;
end
$migration$;

-- fill the new column for the works already saved
update public.master_docs set data = data where coll = 'artworks';
