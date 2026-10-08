# Supabase — schema changes

SQL files in this folder are applied to the `the-legacy` project (id `uinwjwooodacuahqaowf`) in order.

- `001_client_collections.sql` — client collections: acquisition, insurance, ownership and client-facing location on artworks; expenses and their files linked to a collection and shown to the client when `visibleToClient` is true.
- `004_support_chat.sql` — messages between collectors, the assistant and Dylan (conversations, messages, settings, push devices, `support-files` bucket, Vault reader for the push signing key).
