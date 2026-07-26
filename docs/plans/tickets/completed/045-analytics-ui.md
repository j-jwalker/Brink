---
status: Completed
priority: Medium
complexity: Medium
category: Feature
tags: [frontend, analytics, cleanup]
blocked_by: [034, 036]
blocks: [060]
parent_ticket: null
owner: Sebastian
---

# Feature: Analytics page on real tables + fold Predict (T45)

## Rationale
The analytics page currently shows hardcoded silhouette/feature-importance numbers and a fabricated `PredictPage`. This wires it to the real `ModelMetrics`/`Cluster` and migrates the only honest prediction (TS linear-predict from the regression artifact) into the analytics surface, deleting the fabricated page.

## Summary
`AnalyticsPage` reads real `ModelMetrics`/`Cluster`; remove `CLUSTER_POINTS` + hardcoded numbers; add a popularity-predict widget that runs TS linear-predict from `ModelArtifact("popularity_regression")`; delete `PredictPage` + its route + fabricated copy.

## Source
- Spec reqs: **UI-7**, **UI-8**, **AN-9**
- ADRs: [ADR-0003](../../../decisions/adr/0003-analytics-runtime.md) (TS predict from exported coefficients) · [ADR-0004](../../../decisions/adr/0004-analytics-data-strategy.md) C5

## Scope
### In Scope
- `AnalyticsPage.tsx` — read real silhouette/k/clusters/feature-importances (via an endpoint exposing `ModelMetrics`/`Cluster`, or a thin reader); remove `CLUSTER_POINTS` and all hardcoded analytics numbers.
- Popularity-predict widget: TS linear-predict from `ModelArtifact("popularity_regression")` (coefficients + scaler), labeled exploratory.
- Delete `PredictPage.tsx`, its route, and fabricated copy.

### Out of Scope
- Fitting the models (T34/T36); profile page (T44).

## Validation & authz (ADR-0007)
- Any new metrics-read endpoint passes `require_user` + Pydantic like every API route; predict input validated. (The linear-predict math runs client-side in the browser from the artifact coefficients the endpoint exposes — the frontend stays TS.)

## Current State (on `develop`)
- `apps/web/src/pages/AnalyticsPage.tsx` (hardcoded silhouette/feature-importance, `CLUSTER_POINTS`), `pages/PredictPage.tsx` (fabricated) both present.
- Real `ModelMetrics`/`Cluster` (T34/T36) + `ModelArtifact("popularity_regression")` (T36) provide the data.

## Files to Create/Modify
| File | Action | Purpose |
|------|--------|---------|
| `apps/web/src/pages/AnalyticsPage.tsx` | MODIFY | read real metrics/clusters; remove hardcoded values; add predict widget |
| `apps/web/src/pages/PredictPage.tsx` | DELETE | fabricated page removed |
| `backend/app/routers/analytics.py` | CREATE | thin authorized reader for `ModelMetrics`/`Cluster` (if no existing path) |
| `apps/web/src/App routes` | MODIFY | drop the `/predict` route |

## Testing Checklist
- [x] analytics page shows real silhouette/k/clusters from `ModelMetrics`/`Cluster` (no hardcoded constants) — verified rendering + graceful empty state; live values verified on the real Postgres/gold DB
- [x] `CLUSTER_POINTS` and fabricated numbers removed (n/a — they lived in the React SPA, deleted in T60; the Python page has none)
- [~] predict widget from `ModelArtifact` coefficients — **deferred**: needs T36's exported coefficient shape (see Outcome); the page already surfaces the popularity model's quality metrics
- [x] `PredictPage` + `/predict` route deleted (done with the SPA in T60; no such route in the Python frontend)

## Readiness Checklist
- [x] Summary is specific and actionable
- [x] Files to Create/Modify is populated
- [x] Testing Checklist has items
- [x] Dependencies identified (T34, T36 → blocked_by 034, 036)
- [x] Scope boundaries defined

## Notes
Branch off `develop` as `feat/T45-analytics-ui`; one PR back into `develop` (never `main`). Owner: Sebastian (frontend), pairing with Jonah on the metrics shape.


## Outcome (as built)
Built as the Python/Jinja frontend (ADR-0013), not React — the ticket's `AnalyticsPage.tsx` /
`PredictPage.tsx` are gone (SPA deleted in T60).

- **`GET /analytics`** (`pages.py` `_analytics_data` + `analytics.html`, login-gated, linked from the
  signed-in nav): reads the gold `ModelMetrics`/`Cluster` tables and renders **real** model output —
  no hardcoded numbers. Two sections: **Taste communities** (k + silhouette + each community's size,
  from T34) and **Popularity model** (R²/RMSE/feature-importances).
- **Designed to plug in:** it reads by model name, so the popularity section shows a friendly
  "not ready yet" until **T36** writes `ModelMetrics("popularity_regression")`, then its numbers
  appear automatically with **no code change**. Same graceful pattern if the gold tables aren't
  present at all (e.g. local dev) — the page never crashes.
- **Deferred:** the interactive client-side popularity *predict* widget (linear-predict from the
  `ModelArtifact("popularity_regression")` coefficients). It depends on T36's exported `params`
  shape, which doesn't exist yet; building it now would mean inventing that contract. Tracked as a
  small follow-up to add once T36 lands (the page already shows the popularity model's quality).
- **Files:** `backend/app/routers/pages.py`, `backend/app/templates/analytics.html`,
  `backend/app/templates/base.html` (nav link), `backend/app/static/brink.css`,
  `backend/tests/test_pages.py`. Satisfies **UI-7/UI-8/AN-9** partially (clustering live; popularity
  data + predict widget arrive with T36). Full suite green (295).

## Follow-up fix (post-merge)
`/analytics` initially rendered the **logged-out** nav for a signed-in visitor: the route
authenticated the user (the analytics content rendered) but forgot to pass `viewer` to the
template, so `base.html` fell back to its public header (Features / How it works / Sign in).
Fixed by passing `viewer=require_user(...)` to the template; added a regression test asserting the
signed-in nav (`/auth/logout` link present, no "Log in with Spotify") on the analytics page.
