# Brink â€” Agent & Contributor Guide

Music-native social web app. MMA course project, team of 3, **deadline 2026-07-30**.
This file is the contract every AI agent and contributor reads first. Read it before
touching the repo.

## What Brink is

A single **FastAPI/Python app** (Render) serving both the JSON API and the **HTML frontend** (Jinja2
templates + HTMX) + **Supabase** (Postgres + Auth + Storage) + a Python/scikit-learn analytics batch
job (GitHub Actions cron).

> **Stack:** one **FastAPI / Python** app (SQLModel + Alembic) on **Render** serves **both** the
> `/api/*` JSON endpoints and the server-rendered HTML pages (Jinja2 + HTMX, in
> `backend/app/templates/` + `backend/app/routers/pages.py`); **Supabase** provides Postgres, Auth,
> and Storage. See [ADR-0010](docs/decisions/adr/0010-fastapi-render-backend.md) (backend moved here
> from an earlier TypeScript/Vercel/Prisma stack, removed in T08) and
> [ADR-0013](docs/decisions/adr/0013-python-frontend.md) (the frontend became these Python-served
> pages). **The separate React/Vite SPA (`apps/web/`) was retired in T60** â€” the whole app is now one
> Python codebase we can all read and defend. All work is in `backend/` (+ `analytics/`).

**Source of truth â€” read these before planning any work:**
- `docs/plans/requirements.md` â€” requirement catalog (`AUTH-*`, `BE-*`, `SP-*`, `AN-*`, `UI-*`, `MEDIA-*`, `INFRA-*`, `DATA-*`) + requirementâ†’ticket traceability. Data model: `backend/app/models.py` (SQLModel). Decisions: `docs/decisions/`.
- `docs/plans/tickets/` â€” one file per ticket (`backlog/`, `completed/`), derived from the ADRs in `docs/decisions/`. Start at `docs/plans/tickets/README.md` for the dependency waves and reading guide.

## Layout

- `backend/` â€” **the API: FastAPI app (Python, `uv`-managed)**. App code in `backend/app/`, tests
  in `backend/tests/`, DB migrations in `backend/alembic/`.
- `backend/app/templates/` + `backend/app/static/` â€” the **Python frontend**: HTML pages
  (Jinja2 templates; HTMX to come) served by FastAPI, with routes in `backend/app/routers/pages.py` (ADR-0013).
- `analytics/` â€” Python pipeline (`uv`-managed). Created in T30.

*(The `apps/web/` React/Vite SPA was retired in T60 â€” [ADR-0013](docs/decisions/adr/0013-python-frontend.md).
The frontend is the Jinja/HTMX pages under `backend/app/` above.)*
- `docs/plans/` â€” spec + tickets (source of truth above).

## Commands

Local dev reads the root `.env` (the `brink-dev` Supabase project). **Careful: the deployed Render
app uses the SAME database** (confirmed 2026-07-23; split tracked in T99) — local writes are
visible in production, so treat local dev as production until T99 lands.

```
# The whole app â€” one process. The FastAPI app serves BOTH the JSON API and the HTML pages
# (ADR-0013). Visit http://127.0.0.1:3001/ for the pages, /api/* for the API.
cd backend && uv run uvicorn app.main:app --reload --port 3001
```

- **Test:** `cd backend && uv run pytest` (backend). Analytics: `cd analytics && uv run pytest`.
- **Frontend** is server-rendered Jinja/HTMX in `backend/` â€” no separate build/lint step (the
  React/Vite SPA was retired in T60).

## Hard rules

1. **`develop` is the integration branch; `main` is production. Never push to either directly.**
   Every change goes on a branch and through a PR **into `develop`**. One ticket = one PR.
   `main` only receives `develop` via a release PR, and Render deploys production from `main`.
2. **Branches:** name them `<type>/<ticket-id>-<slug>` where type is
   `feat | fix | chore | docs | ci` (e.g. `feat/T10-posts-api`, `chore/repo-governance`).
   Branch off the latest `develop`, keep them short-lived, and **delete the branch after its PR
   merges**. Don't let a branch drift far behind `develop` â€” rebase or re-sync instead.
3. **Never commit secrets.** The root `.env` is git-ignored and stays that way. Secrets live only in
   that file locally and in the Render (app) / GitHub (CI + cron) env. If you ever see a secret in
   tracked files, stop and flag it.
4. **TDD (expected practice).** Write a failing test first, then minimal code to pass,
   with frequent small commits. Claude Code agents should use the `test-driven-development`
   skill; everyone else follows the same loop by hand. This is the expected workflow, not an
   automated guarantee â€” CI (`.github/workflows/ci.yml`) runs the backend tests (`uv run pytest`)
   and a secret scan on every PR, and is what actually blocks untested code.
   Don't execute multiple tickets at once.
5. **Don't widen scope.** Build exactly what the ticket/requirement specifies â€” no extra
   features, abstractions, or error handling beyond what's asked.
6. **Auth:** validate Supabase JWTs server-side via `getUser()` (no JWT secret). We own
   Spotify token refresh; tokens are encrypted at rest (AES-256-GCM, `TOKEN_ENC_KEY`).

## Working norms (expected of humans and agents)

These are expectations, not automated guarantees â€” they set how we work.

- **State assumptions and risks explicitly** â€” in the PR description and when proposing a
  plan. If you had to guess at anything, say so.
- **Stop on ambiguity.** If a ticket or requirement is underspecified or unclear, ask â€”
  don't invent scope, data shapes, or behavior to fill the gap. A wrong guess costs more
  than a question. (Pairs with hard rule #5.)
- **Smallest change that satisfies the ticket.** Surface follow-ups as notes; don't silently
  build them.
- **Reuse before reinventing.** Search for an existing helper before writing a new one. Shared
  logic lives in `backend/app/` (API + Jinja page routes/templates) â€” extend or import it; don't
  copy-paste or write a second version of something that already exists. If you find duplication,
  factor it out as part of the change.
- **Comments: explain both *what* and *why*, written for a reader new to the language/stack.**
  This repo is read by a mixed team including a non-technical owner, so code must be *followable
  by someone who doesn't already know* Python/SQLModel/FastAPI/Jinja/HTMX. This deliberately overrides
  the usual "why, not what" convention. Concretely:
  - Every file that does real work opens with a short **`WHAT THIS FILE IS`** comment (2â€“5 lines,
    plain English) covering its purpose and why it exists.
  - Add a brief plain-language note on each non-trivial block: what it does, why it's there, and
    what any unfamiliar syntax/concept means (e.g. foreign keys, decorators, `Optional`). Explain
    a recurring idea *once* (e.g. in a file header) rather than repeating it on every line.
  - Favor clarity over brevity â€” stating the *what* is expected here, not a smell. But don't
    narrate truly trivial lines, and keep comments **accurate**: a stale/wrong comment is worse
    than none, so update comments in the same change as the code.
  This is a project standard for Brink; individual contributors' global preferences don't override it.
- **Guard against regressions.** A bug fix starts with a failing test that reproduces the bug,
  then the fix. Changes to shared code (`backend/app/db.py`, `backend/app/models.py`,
  `backend/app/deps.py`) have a wide blast radius â€” call out in the PR what depends on them, and
  run the full suite (`cd backend && uv run pytest`).
- **Commit messages:** Conventional Commits â€” `type(scope): summary`
  (`feat`, `fix`, `chore`, `docs`, `ci`, `test`, `refactor`). Scope is usually the ticket id,
  e.g. `feat(T10): add posts endpoint`.
- **Keep docs in sync in the same PR.** Code and its docs change together â€” stale docs are a
  bug. When a PR changes behavior, update the relevant doc in the same PR:
  - Architecture/decision changes -> add or supersede an ADR in `docs/decisions/adr/`.
  - Spec/ticket scope changes -> update `docs/plans/`.
  - Commands, env, conventions, or status -> update this file (`CLAUDE.md`).
- **ADRs are append-only history.** Never rewrite or delete an accepted ADR. To change a past
  decision, write a new ADR and set the old one's status to
  `Superseded by [ADR-NNNN](NNNN-...md)`. This is *why* the log doesn't go stale: history is
  preserved, the current decision is always the latest non-superseded ADR.

## Developer skills (Claude Code and Codex)

Four committed skills (in `.agents/skills/`) support Brink work. Invoke one by typing `/<name>` in
Claude Code, or just describe the situation. They're **guided checklists, not auto-runners** - they
do the steps and flag problems, but stop for your judgement and never bypass review or push to
`develop`/`main`.

The work cycle:

> **`get-me-started`** (begin session) -> work a ticket -> **`close-out`** (finish the *ticket*) ->
> repeat -> **`close-session`** (finish the *session*).

- **`get-me-started` - start of a session.** Pulls in what changed, lists open PRs, audits whether
  each kept its docs in sync with its code, and briefs you on where things stand + what's next. It
  **flags, doesn't fix.** Use it whenever you sit down or feel out of the loop ("catch me up",
  "what's ready to review", "where am I").
- **`close-out` - finishing a *ticket* (pre-merge).** The per-ticket bookkeeping: move the ticket
  `backlog -> completed`, flip its `status` + the `requirements.md` rows it satisfied, update
  `CLAUDE.md` only when the current map changes, and refresh the tickets README. Since **T93 this
  runs *before* merge** - the edits are committed onto your feature branch so they ride the
  **same PR** as the code (no separate follow-up PR). Run it as the **last step before you
  open/finalize a feature PR**, once the code is done and tests are green. Deferring to a follow-up
  PR is still allowed but only as a **stated** exception (e.g. a very large PR). Say "close out
  T<NN>".
- **`close-session` - end of a *session* (final validation).** The "am I safe to stop?" gate and
  bookend to `get-me-started`: runs the full backend suite (no frontend build step - the frontend
  is server-rendered Jinja), confirms the tree is clean and pushed and open PRs are green, prunes
  already-merged branches, and writes the handoff. Use it when wrapping up ("sign off", "I'm done",
  "final validation").
- **`impeccable` - frontend design work.** Use it for Brink UI design, redesign, critique, audit,
  polish, layout, typography, color, responsive behavior, copy, empty states, and other Jinja/HTMX
  frontend improvements. It is not for backend-only work.

**Key distinction:** `close-out` is per **ticket** (its docs, folded into the feature PR);
`close-session` is per **work session** (validate + clean up + handoff). You may run `close-out`
several times in a session, `close-session` once at the end.

## Database migrations

Schema changes use **SQLModel + Alembic**: edit `backend/app/models.py`, then
`cd backend && uv run alembic revision --autogenerate -m "..."` and `uv run alembic upgrade head`.
Alembic was baselined against the live schema in T05 (stamped, not recreated), so `upgrade head`
is a no-op on the existing DB. `alembic check` reports any drift between the models and the DB.

**Medallion schemas (T39, ADR-0009).** Tables live in Postgres schemas: `silver` (`Track`, `Play`),
`gold` (`Cluster`, `ModelMetrics`, `ModelArtifact`), `bronze` (raw `*_raw` landing tables); the
social/auth tables stay in the default `public` schema. Two consequences: (1) **autogenerate runs
with schema reflection on** â€” `env.py` sets `include_schemas=True` (+ an `include_name` allow-list
so only our schemas are reflected, not Supabase's `auth`/`storage`, and a schema-qualified
`include_object` check), so `--autogenerate` sees the medallion tables correctly (done in **T37**;
verified with `alembic check`). (2) SQLite tests map the schemas to none via a
`schema_translate_map` in `tests/conftest.py`. A migration that **moves** a table between schemas
must use `ALTER TABLE ... SET SCHEMA` (preserves rows) â€” never autogenerate's drop+recreate.

## Environment

- Supabase project `brink-dev` (ref `ljzwskfhiviunmqxerwu`). Data API disabled â€” tables are
  reached only through the backend's ORM (SQLModel/SQLAlchemy). **This is currently the ONLY
  database: the deployed Render service points at it too** (confirmed 2026-07-23) — there is no
  separate production DB yet. `T99` (backlog) tracks the split, deliberately deferred past the
  2026-07-30 deadline.
- Root `.env`: `DATABASE_URL`/`DIRECT_URL` (Supabase pooler 6543/5432), `SUPABASE_URL`,
  `SUPABASE_SERVICE_ROLE_KEY`, `SPOTIFY_CLIENT_ID`/`SECRET`, `TOKEN_ENC_KEY`.
- **Getting the values (onboarding):** the `.env` file is git-ignored and never shared in the
  repo. Copy `.env.example`, then get the real secret values from the Render (app) / GitHub env or
  ask Andrea. Don't paste secrets into chat, issues, or commits.
- **Git hooks:** running `npm install` (root `package.json`'s `prepare` script) points git at
  `.githooks/` (a pre-commit secret guard). If you skipped it, run
  `git config core.hooksPath .githooks` once.

## Ownership & review (CODEOWNERS intent)

- **Andrea** â€” backend / API / auth / DB (`backend/`).
- **Sebastian** â€” frontend: the Jinja/HTMX page layer (`backend/app/templates|static|routers/pages.py`).
- **Jonah** â€” analytics (`analytics/`).

The owner of an area is the default reviewer for PRs touching it (every ticket also has an
`owner` in its frontmatter). **Auth and crypto changes** â€” `backend/app/deps.py`,
`backend/app/security/crypto.py`, `backend/app/security/supabase.py`, anything touching tokens or
`TOKEN_ENC_KEY` â€” are the highest-risk area, so a second review is **encouraged** where a reviewer
is available. It is **not required**, though: the area owner may self-merge them (call out in the
PR that it went in without a second review).

## Current Status

For detailed ticket history, use [`docs/plans/tickets/README.md`](docs/plans/tickets/README.md),
the individual completed tickets, and the ADRs. Keep this section short: it is the current map for
agents, not a changelog.

- **App shape:** one FastAPI/Python app on Render serves both `/api/*` and the Jinja/HTMX pages;
  the old TypeScript backend and React/Vite SPA are retired (ADR-0010, ADR-0013, T60).
- **Recent app state:** user discovery, profile pages, feed reactions/comments, artist posts,
  editable profile, email/password auth, and self-serve artist designation are implemented. Profile
  avatars use a public `avatars` bucket; artist images use private `artist-images` signed reads.
  The feed's social quick-wins wave (`T94`–`T97`) shipped: song cards play in place via the
  Spotify embed, show their newest comments inline, carry a "Liked by X and N others" line with a
  reactors list, and support double-tap-to-heart. `T100` freshened listening history: the snapshot
  cron now runs every 30 min (was 2 h), and `POST /api/me/plays/refresh` lets your own profile pull
  your latest plays on load (fire-and-forget, throttled 2/600s, reuses the snapshot ingest). `T101`
  added a one-tap "🎧 Share what you're hearing" button to the composer: it reads `GET
  /api/me/now-playing` and drops the current track into the existing composer selected state,
  publishing with `PostSource.SPOTIFY` (no new endpoint; reuses T20 + T10). `T102` added a
  "▶ played N times by {author}" endorsement line to feed song cards (shown from 2 plays up),
  computed as one batched `(author, track)` count over `silver.Play` in `build_feed`. `T103`
  hardened artist-image signing: a single un-signable image now degrades to a placeholder via the
  shared `create_signed_read_url_or_blank` wrapper, instead of blanking the whole feed or 500ing
  `/artist` (fixes a 2026-07-22 production incident whose trigger was a bad Render Supabase key).
  `T104` made posts **text-only-capable**: the song is now optional on a regular post
  (`Post.trackId` nullable) and the photo optional on an artist post (`ArtistPost.imageUrl`/
  `caption` nullable) — migration `fe4e66a13f08` (additive; applied to brink-dev). Both create
  endpoints reject a post with neither media nor text (400); the composer shows an always-visible
  text box + Share with the song/photo as an optional attach step; text-only posts render a distinct
  note card (`.post-note` / `.artist-post-note`). Artist feed `image_url` is now tri-state
  (URL / `""` T103 placeholder / `None` text-only note).
- **Analytics state:** Kaggle audio features are joined into `silver.Track`; K-means is trained on
  the full local Kaggle file (10 features) and exported as `ModelArtifact("kmeans")` (`T34`) — k
  was deliberately forced to 7 for a usable persona system (silhouette preferred k=2; disclosed in
  `T34`'s Outcome + `AN-3`). `T32` seeded **50 synthetic `User` rows** as personas built from
  `T34`'s 7 trained clusters (scoped down from ADR-0004 C3's ~100–200 — disclosed on the ticket,
  not an ADR change), each with its own shared pool of 25 new Kaggle-sourced `Track` rows and
  15–25 `Play` rows spread across 8–15 days; every seeded user's `bio` discloses it as synthetic
  demo data. `T33` built on-demand inference: `silver.Track` was widened with the 5 remaining
  kmeans features (migration `ce6e2ca7edac`, additive, applied to `brink-dev`) and
  `ingest_kaggle.py`'s join + a full re-ingest backfilled them (269 matched tracks, 257 with all 10
  features present). `backend/app/inference/taste_vector.py` + `assign.py` build a user's taste
  vector on read and assign their nearest `gold.Cluster`, standardizing with the trained
  `ModelArtifact("kmeans")`'s scaler — the C4 fallback for an unmatched/incomplete track is the
  training corpus's own mean vector, not literally "genre" (disclosed; neither Kaggle file has a
  genre field, same gap `T32` hit). Degrades to a null cluster, never a 500, when the model or gold
  schema isn't available. `T14` (the profile endpoint that surfaces this) and `T35` (compatibility)
  are next, both now unblocked.
- **Next feature work:** start from `docs/plans/tickets/README.md` before choosing a ticket. The
  Wave 2 music-identity trio (`T100`–`T102`), `T103` signing hardening, and `T104` text-only posts
  are **complete**, as is the 2026-07-22 non-analytics UI hardening wave (`T80`–`T86`) and the
  social quick-wins wave (`T94`–`T97`). For analytics, `T32` and `T33` are **complete**; `T14` and
  `T35` are unblocked next. **`T45` (analytics UI) is done**: `/analytics` reads the real gold
  `ModelMetrics`/`Cluster` (no hardcoded numbers), shows the K-means/community half live, and
  auto-fills the popularity half the moment `T36` writes `ModelMetrics("popularity_regression")` —
  no code change (the client-side predict widget is the one deferred piece, pending `T36`'s
  exported coefficients).

## Watch-outs

- **Dev and production share one database** (the `brink-dev` Supabase project — confirmed
  2026-07-23, split tracked in `T99`, deferred past the deadline). Until then: no destructive
  local experiments, no throwaway seed data you wouldn't demo, and remember any local write is
  live for real users. One upside: a migration run locally is already applied for production.
- Spotify `provider_token` from the browser lasts about 1 hour and is **not** refreshed by Supabase.
  Server/long-term Spotify access must go through our stored refresh token path (T22/T21).
- Supabase redirect allow-lists matter for auth: deployed and localhost `/auth/callback` and
  `/auth/confirm` URLs must be configured, or login/signup flows cannot return cleanly.
- Storage buckets are owner-managed infrastructure: `artist-images` is private and needs signed read
  URLs; `avatars` is public and must exist before profile-picture uploads work.
- Schema changes still need manual care: run Alembic migrations from `backend/` against `brink-dev`
  (and against production at each release — `uv run alembic -x dburl="<Render DIRECT_URL>" upgrade head`
  accepts a dashboard URL as-is since T98), and preserve medallion schemas (`bronze`, `silver`,
  `gold`) when autogenerating. The T96 `Reaction.createdAt` migration (`f4a2d81c96e0`) is applied
  on both brink-dev and production (verified 2026-07-23).
- The DB still has a `_prisma_migrations` table from the retired Prisma stack. Alembic ignores it
  (`backend/alembic/env.py`); it is harmless and can be dropped later.
- Render deploys production from `main`, not `develop`. Scheduled GitHub workflows also only run
  from the default branch, so release PRs and back-merges matter.

## Deployment topology (ADR-0010, T07, ADR-0013, T60)

> **One app, one host (since T60).** The separate React/Vite SPA on Vercel was retired ([ADR-0013](docs/decisions/adr/0013-python-frontend.md)),
> so the frontend and API are the **same FastAPI app on Render**. The deployed Render `/auth/callback`
> URL must be in the Supabase Auth + Spotify redirect allow-lists, or Spotify login can't return.

- **App (API + frontend):** one FastAPI service on **Render** (`backend/`, config in `render.yaml`)
  â€” build `uv sync`, start `uvicorn app.main:app`. It serves the `/api/*` JSON endpoints **and** the
  server-rendered Jinja/HTMX pages (`/`, `/feed`, `/u/{handle}`, `/artist`, `/auth/*`), same-origin,
  so there's no CORS and no rewrite layer. Env vars (`DATABASE_URL`, `DIRECT_URL`, `SUPABASE_*`,
  `SPOTIFY_*`, `TOKEN_ENC_KEY`, `CRON_SECRET`) live only in Render, never committed. The service
  is on the **free plan**, which spins down after ~15 idle minutes (â†’ a ~50s "waking up" screen);
  `.github/workflows/keepalive.yml` (T64) pings `/api/health` every 10 min from `main` to prevent
  that.
- **Release flow:** **Render deploys production from `main`**, so changes reach production only via a
  `develop â†’ main` release PR, and each release must be followed by a back-merge of `main` into
  `develop` (or the next release PR is blocked as BEHIND, since `main` protection is `strict`).
- **Retired in T60:** the Vercel project, `apps/web/vercel.json`'s `/api/*` rewrite, the legacy
  `/api/state` POC path, and the `web` CI build job (also removed from branch-protection required
  checks). If a separate JS frontend is ever reintroduced, restore the CI job + required check.
