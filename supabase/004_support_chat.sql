-- 004 — Assistant in the client app: conversations, messages, Dylan's notifications and take-over.
-- One conversation per collector and per collection. The AI answers by default (edge function support-chat);
-- Dylan sees every conversation live in The Legacy, can take over ("Prendre le relais") and hand back.
-- Collectors only ever see their own conversation; the AI never changes any collection data.

create table if not exists public.support_threads (
  id uuid primary key default gen_random_uuid(),
  collection_id uuid not null references public.collections(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  client_email text,
  lang text not null default 'en',
  status text not null default 'open' check (status in ('open','resolved')),
  mode text not null default 'ai' check (mode in ('ai','human')),
  human_last_at timestamptz,
  category text,
  priority text not null default 'normal' check (priority in ('normal','high')),
  summary text,
  last_message_at timestamptz not null default now(),
  last_author text,
  unread_admin int not null default 0,
  unread_client int not null default 0,
  created_at timestamptz not null default now(),
  unique (collection_id, user_id)
);

create table if not exists public.support_messages (
  id uuid primary key default gen_random_uuid(),
  thread_id uuid not null references public.support_threads(id) on delete cascade,
  author text not null check (author in ('client','ai','dylan','system')),
  body text not null check (char_length(body) between 1 and 4000),
  artwork_id text,
  attachment_path text,
  attachment_name text,
  attachment_type text,
  created_at timestamptz not null default now()
);
create index if not exists support_messages_thread on public.support_messages (thread_id, created_at);

create table if not exists public.support_settings (
  id int primary key default 1 check (id = 1),
  notify text not null default 'all' check (notify in ('all','important')),
  quiet_start text,                    -- "22:00" (Dylan's time zone) or null
  quiet_end text,                      -- "08:00"
  tz text not null default 'Europe/Paris',
  handoff_minutes int not null default 10 check (handoff_minutes between 2 and 240),
  updated_at timestamptz not null default now()
);
insert into public.support_settings (id) values (1) on conflict (id) do nothing;

create table if not exists public.push_subscriptions (
  endpoint text primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  p256dh text not null,
  auth text not null,
  device text,
  created_at timestamptz not null default now()
);

alter table public.support_threads enable row level security;
alter table public.support_messages enable row level security;
alter table public.support_settings enable row level security;
alter table public.push_subscriptions enable row level security;

-- ---------- rules ----------
drop policy if exists st_read on public.support_threads;
create policy st_read on public.support_threads for select to authenticated
  using (private.is_admin() or (user_id = auth.uid() and private.is_member(collection_id)));
drop policy if exists st_admin_update on public.support_threads;
create policy st_admin_update on public.support_threads for update to authenticated
  using (private.is_admin()) with check (private.is_admin());

drop policy if exists sm_read on public.support_messages;
create policy sm_read on public.support_messages for select to authenticated
  using (exists (select 1 from public.support_threads t where t.id = thread_id
                 and (private.is_admin() or (t.user_id = auth.uid() and private.is_member(t.collection_id)))));
drop policy if exists sm_client_write on public.support_messages;
create policy sm_client_write on public.support_messages for insert to authenticated
  with check (author = 'client'
    and exists (select 1 from public.support_threads t where t.id = thread_id and t.user_id = auth.uid() and private.is_member(t.collection_id))
    and (attachment_path is null or attachment_path like auth.uid()::text || '/%'));
drop policy if exists sm_admin_write on public.support_messages;
create policy sm_admin_write on public.support_messages for insert to authenticated
  with check (author in ('dylan','system') and private.is_admin());

drop policy if exists ss_admin on public.support_settings;
create policy ss_admin on public.support_settings for all to authenticated
  using (private.is_admin()) with check (private.is_admin());

drop policy if exists ps_admin on public.push_subscriptions;
create policy ps_admin on public.push_subscriptions for all to authenticated
  using (private.is_admin() and user_id = auth.uid()) with check (private.is_admin() and user_id = auth.uid());

grant select on public.support_threads, public.support_messages to authenticated;
grant update on public.support_threads to authenticated;
grant insert on public.support_messages to authenticated;
grant select, insert, update, delete on public.support_settings, public.push_subscriptions to authenticated;
revoke all on public.support_threads, public.support_messages, public.support_settings, public.push_subscriptions from anon;

-- The edge function writes only the assistant's replies and the conversation's summary, nothing else.
grant select, update on public.support_threads to service_role;
grant select, insert on public.support_messages to service_role;
grant select on public.support_settings to service_role;
grant select, delete on public.push_subscriptions to service_role;

-- ---------- the collector opens (or finds) their conversation ----------
create or replace function public.support_open_thread(cid uuid, lng text default 'en')
returns public.support_threads language plpgsql security definer set search_path = '' as $$
declare t public.support_threads;
begin
  if auth.uid() is null or not private.is_member(cid) then raise exception 'forbidden'; end if;
  insert into public.support_threads (collection_id, user_id, client_email, lang)
    values (cid, auth.uid(), (select email from auth.users where id = auth.uid()), case when lng in ('fr','en') then lng else 'en' end)
    on conflict (collection_id, user_id) do update set lang = excluded.lang
    returning * into t;
  return t;
end $$;
revoke all on function public.support_open_thread(uuid, text) from public, anon;
grant execute on function public.support_open_thread(uuid, text) to authenticated;

create or replace function public.support_mark_read(tid uuid)
returns void language sql security definer set search_path = '' as $$
  update public.support_threads set unread_client = 0 where id = tid and user_id = auth.uid();
$$;
revoke all on function public.support_mark_read(uuid) from public, anon;
grant execute on function public.support_mark_read(uuid) to authenticated;

-- ---------- every message updates its conversation ----------
create or replace function private.support_after_message() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  update public.support_threads set
    last_message_at = new.created_at,
    last_author = new.author,
    unread_admin = unread_admin + case when new.author = 'client' then 1 else 0 end,
    unread_client = unread_client + case when new.author in ('ai','dylan') then 1 else 0 end,
    status = case when new.author = 'client' then 'open' else status end,
    mode = case when new.author = 'dylan' then 'human' else mode end,
    human_last_at = case when new.author = 'dylan' then now() else human_last_at end
  where id = new.thread_id;
  return new;
end $$;
drop trigger if exists support_after_message on public.support_messages;
create trigger support_after_message after insert on public.support_messages
  for each row execute function private.support_after_message();

-- ---------- live updates ----------
do $$ begin
  begin alter publication supabase_realtime add table public.support_threads; exception when duplicate_object then null; end;
  begin alter publication supabase_realtime add table public.support_messages; exception when duplicate_object then null; end;
end $$;

-- ---------- photos or PDFs the collector adds to a message ----------
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('support-files', 'support-files', false, 15728640,
        array['image/jpeg','image/png','image/heic','image/heif','image/webp','image/gif','application/pdf'])
on conflict (id) do nothing;
drop policy if exists support_files_write on storage.objects;
create policy support_files_write on storage.objects for insert to authenticated
  with check (bucket_id = 'support-files' and (storage.foldername(name))[1] = auth.uid()::text);
drop policy if exists support_files_read on storage.objects;
create policy support_files_read on storage.objects for select to authenticated
  using (bucket_id = 'support-files' and ((storage.foldername(name))[1] = auth.uid()::text or private.is_admin()));

-- ---------- web push: the signing key lives in the Vault (secret "vapid_private"), read only by the edge function ----------
create or replace function public.support_vapid_private() returns text
language sql stable security definer set search_path = '' as $$
  select decrypted_secret from vault.decrypted_secrets where name = 'vapid_private' limit 1;
$$;
revoke all on function public.support_vapid_private() from public, anon, authenticated;
grant execute on function public.support_vapid_private() to service_role;
