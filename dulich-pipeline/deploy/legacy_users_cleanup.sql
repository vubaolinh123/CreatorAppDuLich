-- Run manually only after the pipeline has switched to data/auth.sqlite3.
-- Confirm no other application still depends on public.users first.
begin;

alter table if exists public.users enable row level security;
revoke all on table public.users from anon;
revoke all on table public.users from authenticated;
alter table if exists public.users drop column if exists password;

commit;
