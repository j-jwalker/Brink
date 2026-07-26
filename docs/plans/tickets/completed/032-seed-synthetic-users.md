---
status: Completed
priority: High
complexity: Medium
category: Feature
tags: [analytics, python, data, synthetic]
blocked_by: [030, 031, 034]
blocks: []
parent_ticket: null
owner: Jonah
---

# Feature: Synthetic user seeding — genre-coherent personas (T32)

## Rationale
The live user base is tiny (5 real users as of 2026-07-23), so compatibility scores and
listening-history features have nothing real to demo against. Seeding synthetic listeners gives
those features real population. The `User.isSynthetic` flag already exists for exactly this.

Note: the original rationale ("clusters wouldn't separate") no longer applies — **T34 already
trained K-means directly on the full ~1.2M-track Kaggle corpus**, not on synthetic users, so
cluster quality doesn't depend on this ticket's user count. The remaining purpose is populating
the demo (feed variety, compatibility scoring, profile listening-history), not model training.

## Summary
Seed **~50** `User(isSynthetic=true)` as **genre-coherent personas**, each with a `Play` history
sampled from Kaggle tracks matching that persona's audio profile.

## Source
- Spec reqs: **DATA-2**, **DATA-3**, ADR-0004 **C3**
- ADRs: [ADR-0004](../../../decisions/adr/0004-analytics-data-strategy.md) C3 (genre-coherent personas; disclosed as demo data)

## ⚠ Changed from draft
The draft said "varied taste profiles." **ADR-0004 C3 is more specific:** build each synthetic user as a **genre-coherent persona** (e.g. "mellow indie," "high-energy mainstream") from 1–3 genres/audio-profiles sampled from real Kaggle tracks. Personas — not random sampling — are what make clusters actually separate and compatibility meaningful on screen. Disclosed as demo data in the final report.

## ⚠ Changed from ADR-0004 C3 (disclosed, not an ADR rewrite)
Scoped from ADR-0004 C3's **~100–200** down to **~50** synthetic users, same kind of disclosed
deviation as T31's dataset-size call (see its ticket's Outcome) rather than a rewrite of the ADR —
"~100–200" was always approximate. Reasons:
- Population is now a **demo/UX need, not a modeling one** (see Rationale) — 50 users, spread
  across T34's 7 trained clusters, still gives ~7 users/cluster for both same-cluster and
  cross-cluster compatibility demos.
- **The `Track` table can't actually support 100–200 genre-coherent users today.** `Play.track_id`
  is a hard FK (`ondelete=RESTRICT`) to `silver.Track.spotifyId` — a synthetic play must point at a
  row already in `Track`, not an arbitrary Kaggle CSV row. Live `brink-dev` currently has 662
  `Track` rows, only **67** with Kaggle audio features at all, and `ingest_kaggle.py` (T31) only
  ever *updates* existing `Track` rows — it never inserts new ones. That pool is too thin and too
  narrow in feature-space for genre-coherent sampling at any real N, let alone 100–200 (see next
  section — this ticket now also seeds `Track` rows).
- 7 days remain before the 2026-07-30 deadline; a smaller, well-populated set is a better use of
  that time than a larger, thinner one.

## Persona definition (no genre column exists in the Kaggle data)
Neither Kaggle CSV (`tracks_features.csv`, `SpotifyAudioFeaturesApril2019.csv`) has a genre field —
only audio features + artist/year metadata. So "genre-coherent" is operationalized as **audio
feature-space region**, not a literal genre tag: **each persona = one of T34's 7 trained
`gold.Cluster` rows**, reusing the already-computed centroids instead of inventing new grouping
logic. A user's persona is one cluster; their plays are sampled from Kaggle tracks near that
cluster's centroid (in the same standardized feature space `gold.ModelArtifact("kmeans")`
describes).

## Scope
### In Scope
- `analytics/seed_users.py`:
  - Create ~50 `User(isSynthetic=true)` — `handle`/`display_name` generated, no
    `supabase_user_id`/`email`/`spotify_id` (synthetic users don't log in).
  - Assign each user a persona = one of T34's 7 `gold.Cluster` rows (roughly even split, ~7
    users/cluster).
  - **Build one shared Kaggle track pool per persona/cluster** (~20–30 tracks sampled near that
    cluster's centroid from the local Kaggle CSV) and **insert them as new `silver.Track` rows**
    (`kaggleMatched=true`, real Spotify track IDs from the Kaggle `id` column) — required because
    `Play.track_id` FKs to `Track`, and the existing 67 Kaggle-matched tracks aren't enough to
    sample from. The pool is shared across all users in a persona (not per-user), so `Track` growth
    (~150–200 new rows total) doesn't scale with user count.
  - Generate ~15–25 `Play` rows per user, sampled (with repeats allowed, distinct `playedAt`) from
    their persona's shared track pool, with `playedAt` **spread across multiple distinct days**
    (not all at once) — T44's profile listening summary shows a streak and a 30-day view, which
    need real time spread to look genuine.
- Personas span the feature space so clusters separate (satisfied by using T34's actual clusters).

### Out of Scope
- Clustering / taste vectors (T33/T34 already done); compatibility (T35).
- Posts/feed content for synthetic users — this ticket seeds `User` + `Track` + `Play` only;
  synthetic accounts don't post, so they don't crowd the visible feed.

## Validation & authz (ADR-0007)
- **Integrity:** every seeded user flagged `isSynthetic=true`; `Play` rows respect the `@@unique([userId, playedAt])` dedup; FKs valid.
- **Business rule:** synthetic data is disclosed (demo data) — recorded for the report, not hidden.

## Current State (on `develop`)
- `backend/app/models.py`: `User.isSynthetic` (default false); `Play` with a unique constraint on `(userId, playedAt)`; `Play.trackId` FKs `silver.Track.spotifyId` with `ondelete=RESTRICT`.
- `analytics/db.py` (T30) + Kaggle-joined `Track` features (T31, 67/662 matched as of 2026-07-23) available.
- `gold.Cluster`/`gold.ModelArtifact("kmeans")` (T34) trained and exported — 7 clusters, centroids in both original and standardized units.
- Local Kaggle CSV (`analytics/data/tracks_features.csv`, gitignored, ~1.2M rows) available to sample new `Track` rows from.
- No `seed_users.py` yet.

## Files to Create/Modify
| File | Action | Purpose |
|------|--------|---------|
| `analytics/seed_users.py` | CREATE | persona-based synthetic user + Track pool + play seeding |
| `analytics/tests/test_seed_users.py` | CREATE | seeding tests |

## Testing Checklist
- [x] seeds ~50 users, all flagged `isSynthetic=true`
- [x] each user is assigned exactly one persona (one of T34's 7 clusters)
- [x] each persona's shared Track pool is seeded once (not duplicated per user) and reused across that persona's users
- [x] each user's plays are sampled only from their persona's track pool (genre/audio-profile coherent)
- [x] personas vary across users (roughly even spread across the 7 clusters)
- [x] `Play` rows respect the dedup constraint (`userId`, `playedAt`)
- [x] `Play.playedAt` values are spread across multiple distinct days per user, not clustered at one instant
- [x] idempotent: re-running doesn't duplicate synthetic users, Track pool rows, or Play rows

## Readiness Checklist
- [x] Summary is specific and actionable
- [x] Files to Create/Modify is populated
- [x] Testing Checklist has items
- [x] Dependencies identified (T30, T31 → blocked_by 030, 031)
- [x] Scope boundaries defined

## Outcome
`analytics/seed_users.py` seeds synthetic personas by reusing T34's 7 trained `gold.Cluster`
centroids (no genre column exists in either Kaggle CSV, so "genre-coherent" is operationalized as
the same audio feature-space regions T34 already trained on — see the ticket's persona-definition
note above). For each persona it builds one shared pool of new `silver.Track` rows (real Spotify
ids from the local Kaggle CSV, nearest that persona's centroid — needed because `Play.trackId` FKs
`Track` and the 67 pre-existing Kaggle-matched rows weren't enough to sample from) and every user
in that persona draws their `Play` history from the same shared pool, so `Track` growth scales with
persona count (7), not user count. No `User`/`Track` column records persona assignment — per
ADR-0003 a user's cluster is computed on read (T33), so it's implicit in which pool a user's plays
came from, same as it will be for real users. Idempotent by construction: pool selection is a pure
function of `(csv, centroids, pool_size)` so a rerun computes the identical pool and handles are
assigned in a fixed traversal order, so `ON CONFLICT DO NOTHING` (Track, User) makes reruns a
no-op rather than piling up duplicates.

Tests: pure-function coverage (standardization, nearest-neighbor selection, pool building, evenly
splitting users across personas, timestamp spreading) with no DB, plus one live-DB idempotency test
against `brink-dev` (gated behind `RUN_ANALYTICS_DB_TESTS=1`, snapshots/restores `gold.Cluster` and
`gold.ModelArtifact` via `test_cluster.py`'s existing helpers, cleans up its own disposable rows).

**Actually run against the real corpus (2026-07-23):** `uv run python seed_users.py
data/tracks_features.csv` against live `brink-dev`. Seeded **50 synthetic users** across all 7
personas, **175 new `Track` rows** (25 per persona, `kaggleMatched` went 67 → 242), and **1012
`Play` rows** (every user landed in the intended 15–25 range, spread across 8–15 distinct days
each). Verified post-run: 50/50 synthetic-flagged users, all with 15–25 plays, all 7 personas
represented. Each seeded user's `bio` discloses it's synthetic demo data and names its persona
(e.g. "Synthetic listener seeded for demo purposes (T32; disclosed per ADR-0004 C3). Persona: Low
Loudness, Low Energy.") — disclosure is visible on the profile itself, not just in docs/report.

## Notes
Branch off `develop` as `feat/T32-seed-users`; one PR back into `develop` (never `main`). Owner: Jonah (analytics).
