---
status: Completed
priority: High
complexity: Medium
category: Feature
tags: [backend, python, inference, analytics, validation]
blocked_by: [034, 039]
blocks: [014, 035]
parent_ticket: null
owner: Andrea
---

# Feature: On-demand inference core (Python) — taste vector + cluster assignment (T33)

## Rationale
Under ADR-0003 (option A), a user's taste vector and cluster are computed **live in the FastAPI backend** from the exported `ModelArtifact`, so profiles reflect the user's latest listening instantly. This ticket builds that shared inference core, which the profile API (T14), compatibility (T35), and profile UI (T44) all use. (Under ADR-0010 this is Python in the FastAPI backend — the natural home for ML inference, which is why on-read inference no longer needs a TS reimplementation.)

## Summary
A Python module that builds a user's taste vector from their tracks' audio features (with the C4 genre-only fallback + coverage), standardizes it using the `ModelArtifact` scaler, and assigns the nearest K-means centroid — reading every parameter from the artifact, never hardcoding.

## Source
- Spec reqs: **AN-2**, ADR-0004 **C4**
- ADRs: [ADR-0003](../../../decisions/adr/0003-analytics-runtime.md) (inference on read from exported params) · [ADR-0010](../../../decisions/adr/0010-fastapi-render-backend.md) (on-read inference is Python in the FastAPI backend) · [ADR-0004](../../../decisions/adr/0004-analytics-data-strategy.md) C2 (assign to track-centroid), C4 (fallback in the on-read runtime too)

## ⚠ Changed from draft
The draft's T33 was a **Python** `features.py` writing a `TasteVector` table. Under option A there is no `TasteVector` table (T39); the taste vector is built **on read**. Originally (ADR-0003 under the TS API) this was a TS reimplementation; under ADR-0010 the backend is Python, so the on-read standardize → nearest-centroid lives directly in the FastAPI backend — **one shared feature definition with T34**, no cross-language port.

## Scope
### In Scope
- `backend/app/inference/taste_vector.py` — aggregate a user's `Play`/`Post` tracks into a vector in the K-means feature space (mean audio features, etc.); **C4 fallback:** genre-only vector for tracks where `kaggleMatched=false`; return coverage %.
- `backend/app/inference/assign.py` — load `ModelArtifact("kmeans")`; standardize the taste vector with `scalerMean/scalerStd` in `featureOrder`; return nearest centroid → `Cluster` (label).
- Graceful path when no `ModelArtifact` exists yet (returns null cluster, not 500).

### Out of Scope
- The profile endpoint itself (T14), compatibility (T35), UI (T44).

## Validation & authz (ADR-0007)
- **Integrity / correctness:** read `featureOrder` + scaler from the artifact and apply in that exact order — must match how T34 fit the model (the documented sync point).
- **Business rule:** report coverage % (ADR-0004 C4); a low-coverage user still gets a defensible fallback vector, never a crash.

## Current State (on `develop`)
- `ModelArtifact` schema (T39) + a written `ModelArtifact("kmeans")` and `Cluster` rows (T34).
- `Track.kaggleMatched` + audio-feature columns exist; `Play`/`Post` link users to tracks.
- No `backend/app/inference/*` yet.

**⚠ New prerequisite surfaced by T34:** the trained `ModelArtifact("kmeans")`'s `featureOrder` has
**10** features, not 5 — `danceability, energy, valence, tempo, loudness, acousticness,
instrumentalness, liveness, speechiness, mode`. `silver.Track` only has columns for the original 5
(from T31's join). Before this ticket can build a real user's taste vector in the same feature
space the model was trained on, `Track`'s schema (and `analytics/ingest_kaggle.py`'s join) need
extending with the other 5 — a small Alembic migration + a join update, not built as part of T34
(out of its scope). Do this first, or the standardize/nearest-centroid step has no way to compute a
comparable vector for a real track.

## Files to Create/Modify
| File | Action | Purpose |
|------|--------|---------|
| `backend/app/inference/taste_vector.py` | CREATE | build user taste vector + C4 fallback + coverage |
| `backend/app/inference/assign.py` | CREATE | standardize + nearest-centroid assignment |
| `backend/tests/test_inference.py` | CREATE | vector + fallback + assignment tests |

## Testing Checklist
- [x] known fixture → expected taste vector (matches T34's feature definition)
- [x] fallback path: track not in Kaggle → valid corpus-mean vector (see Outcome — not literally
      "genre-only"); coverage reflects it
- [x] standardize uses artifact `scalerMean/Std` in `featureOrder` order
- [x] nearest-centroid returns the correct `Cluster` for a planted vector
- [x] no `ModelArtifact` present → null cluster, graceful, not 500

## Readiness Checklist
- [x] Summary is specific and actionable
- [x] Files to Create/Modify is populated
- [x] Testing Checklist has items
- [x] Dependencies identified (T34, T39 → blocked_by 034, 039)
- [x] Scope boundaries defined

## Notes
Branch off `develop` as `feat/T33-taste-vectors`; one PR back into `develop` (never `main`). The feature definition here and in T34 must stay in lockstep — the `ModelArtifact` is the contract; treat any divergence as a bug. (Both are now Python, so the definition can be shared directly rather than reimplemented.) Owner: Andrea, pairing with Jonah on the feature definition.

## Outcome (as built)

**Prerequisite done first, as flagged above.** `silver.Track` widened with the 5 remaining kmeans
features (`acousticness`, `instrumentalness`, `liveness`, `speechiness`, `mode`) as nullable
`Float` columns — migration `ce6e2ca7edac` (additive, applied to `brink-dev`) — and
`analytics/ingest_kaggle.py`'s join extended to fill them the same way as T31's original 5.
`ingest_kaggle.py` was then **re-run against the full `tracks_features.csv`** to backfill
already-`kaggleMatched` tracks (242 → 269 matched, 257 with all 10 features now present; the
remaining 12 were matched by an older, since-superseded Kaggle file absent from this run's CSV —
expected, documented behavior, not a gap this ticket introduced).

**`backend/app/inference/taste_vector.py`** — `build_taste_vector(session, user_id, feature_order,
corpus_mean)` averages the feature vectors of every track a user has played (`Play`) or shared
(`Post`, text-only posts excluded since `trackId` is `NULL`), returning `None` for a user with no
eligible tracks. Returns `{"vector", "coverage_pct", "track_count"}`.

**`backend/app/inference/assign.py`** — `assign_cluster(session, user_id)` loads
`ModelArtifact("kmeans")`, calls `build_taste_vector`, standardizes with `scaler_mean`/`scaler_std`
in `feature_order`, and returns the nearest `gold.Cluster` (`{"cluster": {"id", "label"}}`) plus the
coverage %. Wrapped in a broad `try/except` so a missing model, missing gold schema (e.g. local
dev), or a track-less user all degrade to `{"cluster": None, "coverage_pct": None}` — same "not
ready yet" pattern as T45's `_analytics_data`, never a 500.

**Two implementation-level decisions not spelled out in the ticket, made and disclosed here rather
than guessed silently:**
- **C4 fallback is a corpus-mean vector, not literally "genre-only."** Neither Kaggle CSV has a
  genre field at all — T32 hit this identical gap building its personas (see 032's Outcome). The
  fallback for an unmatched/incomplete track is `ModelArtifact.scaler_mean` (the training corpus's
  own average point): free (already stored), and "assume average" is the same honest-fallback
  spirit ADR-0004 C4 asks for.
- **"Matched" requires all 10 features present, not just `kaggleMatched=True`.** A track matched by
  an ingest run before this ticket's schema widening had `kaggleMatched=True` but `NULL` in the 5
  new columns until re-ingested — averaging a `None` would crash. `taste_vector.py` checks
  completeness directly rather than trusting the flag alone, so this stays correct even if a future
  ingest gap reopens it.
- **Nearest-`Cluster` lookup re-standardizes each `Cluster`'s centroid at read time**, rather than
  matching by its position in `ModelArtifact.params["centroids"]`. `gold.Cluster` stores its
  centroid in original units (for the analytics page, T45) with no stable column linking a row back
  to that array's order — relying on insertion order would be fragile. Standardizing each `Cluster`
  row's own centroid with the same scaler at comparison time sidesteps that.

**Tests (`backend/tests/test_inference.py`, 12 tests):** `taste_vector` is tested against a real
in-memory SQLite DB (`Play`/`Post`/`Track` have no Postgres-only columns, so this works like
`test_stats.py` does). `standardize`/`nearest_cluster_label` are tested as pure functions on plain
data — `Cluster`/`ModelArtifact` use Postgres-only `JSONB` columns SQLite can't build, which is
also why `conftest.py`'s `db_session` fixture excludes the gold tables entirely. `assign_cluster`'s
graceful-degradation path is tested against that same fixture, since the gold tables being absent
there **is** the "gold schema unavailable" case it needs to handle. The full wired pipeline (real
`ModelArtifact` + real `Cluster` rows together) isn't covered by an automated test for the same
JSONB/SQLite reason — manually verified end-to-end against `brink-dev`'s real trained model instead
(7 clusters, correct `feature_order`, sane per-user coverage % after the backfill above), matching
how T31/T34/T45 verified their own gold-table code. Full backend suite: **309 passed.**
