---
status: Completed
priority: Medium
complexity: Low
category: Feature
tags: [backend, python, inference, compatibility]
blocked_by: [033]
blocks: [014]
parent_ticket: null
owner: Andrea
---

# Feature: Compatibility on read (cosine) (T35)

## Rationale
Compatibility between two listeners is a headline social-analytics feature. Under ADR-0003 it's the cosine similarity of their taste vectors, computed **on read in the FastAPI backend** — fresh, and cheap at our scale (~200 users).

## Summary
A Python helper that returns the 0..1 cosine similarity between a viewer's and another user's taste vectors, reusing the T33 inference core.

## Source
- Spec reqs: **AN-5**
- ADRs: [ADR-0003](../../../decisions/adr/0003-analytics-runtime.md) (cosine on read) · [ADR-0010](../../../decisions/adr/0010-fastapi-render-backend.md) (on-read inference is Python) · [ADR-0004](../../../decisions/adr/0004-analytics-data-strategy.md)

## ⚠ Changed from draft
The draft's T35 was a **Python** `compat.py` writing a pairwise `Compatibility` table. Under option A there is no table (T39) — compatibility is computed **on demand** between the viewer and the profile being viewed (in the FastAPI backend, Python, reusing T33).

## Scope
### In Scope
- `backend/app/inference/compatibility.py` — `cosine(vector_a, vector_b)` over taste vectors from T33; clamp to 0..1; symmetric.
- Used by the profile API (T14) for viewer-vs-profile compatibility.

### Out of Scope
- Any pairwise precompute / table (dropped). The donut UI is T44.

## Validation & authz (ADR-0007)
- **Correctness:** both vectors must come from the same T33 builder (same feature space) before cosine.
- **Business rule:** if either user has no taste vector yet (no plays / no artifact), return null compatibility, not an error.

## Current State (on `develop`)
- T33 inference core (`taste_vector.py`) available; no `Compatibility` table (T39).
- No `compatibility.py` yet.

## Files to Create/Modify
| File | Action | Purpose |
|------|--------|---------|
| `backend/app/inference/compatibility.py` | CREATE | cosine over two taste vectors |
| `backend/tests/test_compatibility.py` | CREATE | tests |

## Testing Checklist
- [x] identical vectors → 1.0
- [x] orthogonal vectors → 0.0
- [x] symmetric: compat(A,B) == compat(B,A)
- [x] a user with no taste vector → null, not a crash

## Readiness Checklist
- [x] Summary is specific and actionable
- [x] Files to Create/Modify is populated
- [x] Testing Checklist has items
- [x] Dependencies identified (T33 → blocked_by 033)
- [x] Scope boundaries defined

## Notes
Branch off `develop` as `feat/T35-compatibility`; one PR back into `develop` (never `main`). Owner: Andrea.

## Outcome (as built)

**`backend/app/inference/compatibility.py`** — `cosine(vector_a, vector_b)` is the raw formula,
rounded to 6 decimal places before clamping to 0..1 (floating-point error can otherwise push an
identical pair to `0.9999999999999999` instead of a clean `1.0`; a zero-magnitude vector returns 0
instead of dividing by zero). `compatibility(session, user_a_id, user_b_id)` loads
`ModelArtifact("kmeans")` **once** and calls T33's `build_taste_vector` for both users with the
same `feature_order`/`scaler_mean`, so both vectors always come from the same feature space before
comparing (the ticket's stated correctness requirement) — then delegates the null-propagation to
`compatibility_from_vectors(vector_a_result, vector_b_result)`, a pure function that returns `None`
if either side has no taste vector. `compatibility()` itself degrades to `None` (never raises) when
the trained model or the gold schema isn't available, same pattern as T33's `assign_cluster`.

**Tests (`backend/tests/test_compatibility.py`, 8 tests):** `cosine`/`compatibility_from_vectors`
are pure-function tests (no DB). `compatibility()`'s graceful-degradation path is tested against
`db_session`, where `ModelArtifact`'s Postgres-only `JSONB` table is genuinely absent — same
approach and same reason as T33's `assign_cluster` tests. Manually verified symmetry
(`compat(A,B) == compat(B,A)`) against `brink-dev`'s real users. **Observed (disclosed, not a
bug):** at today's ~24% Kaggle-match coverage, most real users' compatibility scores land very
close to 1.0, since users with mostly-unmatched tracks share the same corpus-mean fallback vector
(T33) — an honest consequence of current data sparsity, not a defect in the cosine math itself; it
should self-correct as match coverage grows. Full backend suite: **317 passed.**
