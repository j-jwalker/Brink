---
status: Backlog
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
- [ ] known fixture → expected taste vector (matches T34's feature definition)
- [ ] fallback path: track not in Kaggle → valid genre-only vector; coverage reflects it
- [ ] standardize uses artifact `scalerMean/Std` in `featureOrder` order
- [ ] nearest-centroid returns the correct `Cluster` for a planted vector
- [ ] no `ModelArtifact` present → null cluster, 200 (graceful), not 500

## Readiness Checklist
- [x] Summary is specific and actionable
- [x] Files to Create/Modify is populated
- [x] Testing Checklist has items
- [x] Dependencies identified (T34, T39 → blocked_by 034, 039)
- [x] Scope boundaries defined

## Notes
Branch off `develop` as `feat/T33-taste-vectors`; one PR back into `develop` (never `main`). The feature definition here and in T34 must stay in lockstep — the `ModelArtifact` is the contract; treat any divergence as a bug. (Both are now Python, so the definition can be shared directly rather than reimplemented.) Owner: Andrea, pairing with Jonah on the feature definition.
