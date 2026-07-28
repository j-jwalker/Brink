---
status: Backlog
priority: Medium
complexity: Medium
category: Chore
tags: [infra, db, supabase, render, environments]
blocked_by: []
blocks: []
parent_ticket: null
owner: Andrea
---

# Chore: give production its own database (split from brink-dev) (T99)

## Rationale
Discovered 2026-07-23 while releasing T96: running the production migration was a no-op
because the dev migration had already applied it — **the Render production service and local
dev point at the SAME Supabase project (`brink-dev`)**. There is no separate production
database. Consequences today:

- Every local dev run reads and writes the data real users see (test posts, experiments,
  the T32 synthetic seeding all land in "production").
- A destructive local mistake (bad migration downgrade, delete experiment) hits live data
  directly — CLAUDE.md's old claim that local dev "never touches production" was false
  (corrected in this ticket's PR).

**Deliberate timing decision:** do NOT execute this before the 2026-07-30 course deadline.
An environment split a week before the demo risks auth/storage breakage for little gain.
Until then the working rule is: *treat local dev as production* — no destructive
experiments, no throwaway seed data you wouldn't demo.

## Summary
Create a separate production Supabase project and repoint the Render service at it, so dev
and production are isolated. `brink-dev` then becomes what its name says.

## Source
- Spec reqs: **INFRA** (environment hygiene); BE-1 (Postgres + schema)
- Docs: `CLAUDE.md` § Environment / Watch-outs (corrected alongside this ticket)

## Scope
### In Scope
- New Supabase project ("brink-prod"): apply the schema via
  `uv run alembic -x dburl="<new DIRECT_URL>" upgrade head` (works with dashboard URLs
  as-is since T98), preserving the medallion schemas (`bronze`/`silver`/`gold` must be
  created first — check what the baseline migration expects).
- Decide the data question: copy existing rows to the new prod project (they are the real
  users/posts) and let brink-dev keep a snapshot as dev data, or start prod fresh.
- Recreate storage buckets on the prod project: `avatars` (public), `artist-images`
  (private) — and their policies.
- Supabase Auth config on the prod project: Spotify provider + redirect allow-lists
  (deployed `/auth/callback` + `/auth/confirm`), email confirmations ON.
- Spotify developer app: add the prod project's callback if it differs.
- Render env: `DATABASE_URL`, `DIRECT_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`
  swapped to the prod project (keep `TOKEN_ENC_KEY` identical or all stored Spotify tokens
  become undecryptable — decide explicitly).
- GitHub Actions env (snapshot + analytics crons): repoint any DB/Supabase secrets that
  should now target prod.
- Smoke-test the deployed app end to end (login, post, react, artist image upload).

### Out of Scope
- Any application code changes (none should be needed — everything reads env vars).
- CI changes (tests use in-memory SQLite).

## Files to Create/Modify
| File | Action | Purpose |
|------|--------|---------|
| — (mostly owner-managed infrastructure: Supabase, Render, GitHub dashboards) | | |
| `CLAUDE.md` | MODIFY | flip the shared-DB Watch-out once the split is done |
| `docs/plans/tickets/README.md` | MODIFY | record completion |

## Testing Checklist
- [ ] deployed app logs in via Spotify and email against the new project
- [ ] posting/reactions/comments/follow work in production
- [ ] avatar upload + artist image signed reads work (buckets + policies)
- [ ] snapshot cron writes plays to the PROD database
- [ ] local dev against brink-dev no longer appears in production
- [ ] `alembic current` at head on both databases

## Readiness Checklist
- [x] Summary is specific and actionable
- [x] Files to Create/Modify is populated
- [x] Testing Checklist has items
- [x] Dependencies identified
- [x] Scope boundaries defined
