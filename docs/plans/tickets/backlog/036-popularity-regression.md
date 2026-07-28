---
status: Obsolete
priority: Medium
complexity: Medium
category: Feature
tags: [analytics, python, regression, ml]
blocked_by: [031, 039]
blocks: [038, 045]
parent_ticket: null
owner: Jonah
---

# Feature: Popularity regression + coefficient export (T36)

> **CUT (2026-07-28) — see [ADR-0016](../../../decisions/adr/0016-cut-second-regression-model.md).**
> No Kaggle dataset supports a defensible popularity regression: the ~1.2M-track training corpus
> has no `popularity` column at all, the only file that does is frozen at April 2019, and the real
> `brink-dev` overlap (Kaggle-matched + live popularity) is 67 rows — too thin for a train/test
> split. Popularity is also a live, constantly-recomputed metric, not a fixed target the way audio
> features are. A valence-regression alternative was drafted (trained on the full Kaggle corpus,
> sidestepping the data problem) but the team chose to cut the second model entirely rather than
> build either version, given the 2026-07-30 deadline and this ticket's always-optional,
> exploratory scope (ADR-0004 C5). `Track.popularity` itself is untouched and still used for live
> display elsewhere in the app (feed/search/posts) — only this analytics *training* target is cut.
> **T38** drops its dependency on this ticket and no longer orchestrates a regression step.

## Rationale
A second real model strengthens the analytics story cheaply: a linear regression of audio features → track popularity, reported with R²/RMSE + feature importances (labeled exploratory per ADR-0004 C5).

## Summary
Fit a linear regression on Kaggle-joined track features predicting `popularity`, with a train/test split; write `ModelMetrics(popularity_regression)`; export `ModelArtifact("popularity_regression")` (feature order + scaler + coefficients/intercept) so any prediction widget runs on-demand in TS.

## Source
- Spec reqs: **AN-6**, ADR-0004 **C5**
- ADRs: [ADR-0004](../../../decisions/adr/0004-analytics-data-strategy.md) C5 · [ADR-0003](../../../decisions/adr/0003-analytics-runtime.md) (export params; TS predicts on read)

## Scope
### In Scope
- `analytics/regression.py` — assemble feature matrix from Kaggle-matched tracks; train/test split; fit linear regression; compute R²/RMSE + per-feature importances.
- Write `ModelMetrics(modelName="popularity_regression": r2, rmse, featureImportances)`.
- Export `ModelArtifact("popularity_regression")`: `featureOrder`, `scalerMean`, `scalerStd`, `params = { coefficients, intercept }`.

### Out of Scope
- Any UI prediction widget — that's TS linear-predict from this artifact, built in T45.

## Validation & authz (ADR-0007)
- **Integrity:** metrics persisted are finite; `ModelArtifact` coefficients align 1:1 with `featureOrder`.

## Current State (on `develop`)
- `analytics/db.py` (T30); Kaggle features on `Track` (T31); `ModelArtifact`/`ModelMetrics` schema (T39).
- No `regression.py` yet.

## Files to Create/Modify
| File | Action | Purpose |
|------|--------|---------|
| `analytics/regression.py` | CREATE | fit + metrics + export coefficients |
| `analytics/tests/test_regression.py` | CREATE | regression tests |

## Testing Checklist
- [ ] runs on a fixture; persists finite R²/RMSE
- [ ] `featureImportances` has one entry per feature
- [ ] `ModelArtifact("popularity_regression")` round-trips: coefficients length == len(featureOrder)
- [ ] train/test split is deterministic (seeded)

## Readiness Checklist
- [x] Summary is specific and actionable
- [x] Files to Create/Modify is populated
- [x] Testing Checklist has items
- [x] Dependencies identified (T31, T39 → blocked_by 031, 039)
- [x] Scope boundaries defined

## Notes
Branch off `develop` as `feat/T36-regression`; one PR back into `develop` (never `main`). Owner: Jonah. Reads **silver** (`Track`), writes **gold** (`ModelMetrics`/`ModelArtifact`) per ADR-0009. Labeled exploratory in the report (ADR-0004 C5).
