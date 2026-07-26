---
status: Completed
priority: High
complexity: High
category: Feature
tags: [analytics, python, kmeans, ml]
blocked_by: [031, 039]
blocks: [033, 038, 045]
parent_ticket: null
owner: Jonah
---

# Feature: K-means training on tracks + ModelArtifact export (T34)

## Rationale
K-means is the graded ML centerpiece. Per ADR-0004 C2 it is trained on the **Kaggle track audio-space** (real elbow/silhouette on ~1M tracks) — one model over tracks, not a weak second clustering over our few users. The trained parameters are exported so the FastAPI backend can assign any user on-demand.

## Summary
Fit K-means on Kaggle track audio features, select k via elbow + silhouette, write human-readable `Cluster` rows + `ModelMetrics(kmeans)`, and export the self-describing `ModelArtifact("kmeans")` (feature order + scaler mean/std + centroids) that the on-read inference (T33) reads.

## Source
- Spec reqs: **AN-3**, **AN-4**
- ADRs: [ADR-0004](../../../decisions/adr/0004-analytics-data-strategy.md) C2 · [ADR-0003](../../../decisions/adr/0003-analytics-runtime.md) (train→infer; export params)

## ⚠ Changed from draft
The draft also **assigned each user** to a cluster and wrote `User.clusterId`. Under option A that assignment is **on-demand in TS** (T33/T14), so this ticket does **not** touch users — it trains on tracks and exports params only.

## Scope
### In Scope
- `analytics/cluster.py` — standardize track features (`StandardScaler`); fit K-means; select k via elbow + silhouette; derive human-readable cluster labels.
- Write `Cluster` rows (label, centroid, size).
- Write `ModelMetrics(modelName="kmeans": silhouette, k)`.
- **Export `ModelArtifact("kmeans")`:** `featureOrder`, `scalerMean`, `scalerStd`, `params = { centroids }` (the guardrail — fully self-describing for the on-read inference).

### Out of Scope
- Assigning users / writing `User.clusterId` (dropped — T39; computed on read in T33/T14).
- Compatibility (T35), regression (T36).

## Validation & authz (ADR-0007)
- **Integrity:** `ModelArtifact("kmeans")` is the single source for inference params; centroids and scaler must be in the **same standardized space** and feature order the on-read inference (T33) will use.
- **Determinism:** fixed random seed so k/labels are stable and defensible in the report.

## Current State (on `develop`)
- `analytics/db.py` (T30); Kaggle-joined `Track` audio features (T31); `ModelArtifact` + `Cluster` + `ModelMetrics` schema (T39).
- No `cluster.py` yet.

## Files to Create/Modify
| File | Action | Purpose |
|------|--------|---------|
| `analytics/cluster.py` | CREATE | fit + select k + label + write Cluster/ModelMetrics + export ModelArtifact |
| `analytics/tests/test_cluster.py` | CREATE | clustering + export tests |

## Testing Checklist
- [x] deterministic seed → stable k and labels
- [x] `Cluster` rows written with label, centroid, size
- [x] `ModelMetrics("kmeans")` has silhouette + k
- [x] `ModelArtifact("kmeans")` round-trips: featureOrder + scalerMean/Std + centroids, all aligned
- [x] centroid dimensionality == len(featureOrder)

## Readiness Checklist
- [x] Summary is specific and actionable
- [x] Files to Create/Modify is populated
- [x] Testing Checklist has items
- [x] Dependencies identified (T31, T39 → blocked_by 031, 039)
- [x] Scope boundaries defined

## Outcome
`analytics/cluster.py` reads the full local Kaggle file directly (not `Track` — ADR-0004 C2 calls
for training on the ~1M-track audio space, and the file is already the complete archive per T31),
standardizes features (`StandardScaler`), and fits K-means. Writes `gold.Cluster` (label, centroid
in original units, size), `gold.ModelMetrics("kmeans")` (silhouette, k), and
`gold.ModelArtifact("kmeans")` (featureOrder, scalerMean/Std, centroids in **standardized** space —
the space T33's on-demand inference must compare a new point in). Re-running replaces the previous
`kmeans` results (delete-then-insert) rather than accumulating, matching T31's dataset-swap
pattern — training must be safe to redo.

**Feature set widened to 10** (from the original 5): `danceability, energy, valence, tempo,
loudness, acousticness, instrumentalness, liveness, speechiness, mode` — added by owner request to
give clustering a genuine shot at more separable structure. **This adds a new, concrete dependency
for T33**: real `Track` rows only carry the original 5 features from T31's join, so on-demand
inference will need `Track`'s schema (and `ingest_kaggle.py`'s join) extended with the other 5
before a real user can be compared against these centroids. Flagged directly on T33's ticket file.

**k forced to 7, disclosed, not silently chosen.** Silhouette + elbow were computed honestly across
k=2–10 on the full 1.2M-track corpus and consistently preferred **k=2** (silhouette 0.240) — this
held across both the original 5-feature set and the widened 10-feature set, and a Gaussian Mixture
Model comparison (tried specifically to see if a different algorithm would find more natural
structure) did no better: BIC never plateaued within the tested range, and silhouette on GMM's hard
assignments was lower than K-means at every k tried. The data genuinely only supports ~2–3
well-separated groups. Since the listener-persona feature needs at least 5 groups to be usable, k
was **deliberately forced to 7** — `run_cluster()` now takes a `forced_k` param that still computes
and records the honest silhouette-preferred k (`k_metrics`, `silhouette_best_k` in the returned
summary and in the run's printed output) rather than hiding the trade-off. Final result: **k=7,
silhouette=0.160** (vs. 0.240 at the silhouette-optimal k=2), 7 clusters ranging 43,615–250,769
tracks each, with genuinely varied, interpretable labels (e.g. "High Valence, High Danceability",
"High Acousticness, Low Energy", "High Speechiness, High Danceability"). Verified idempotent at
full scale (two full 1.2M-row runs, identical k/labels/sizes).

## Notes
Branch off `develop` as `feat/T34-kmeans`; one PR back into `develop` (never `main`). Owner: Jonah. Reads the **Kaggle CSV file directly** (not `silver.Track` — see Outcome), writes **gold** (`Cluster`/`ModelMetrics`/`ModelArtifact`) per ADR-0009. The on-read inference (T33) depends on the exact `featureOrder`/scaler stored here — keep them authoritative, never duplicate the constants in the backend.
