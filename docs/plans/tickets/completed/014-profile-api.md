---
status: Completed
priority: High
complexity: Medium
category: Feature
tags: [backend, api, profile, analytics, validation]
blocked_by: [033, 035]
blocks: []
parent_ticket: null
owner: Andrea
---

# Feature: Profile analytics — cluster + compatibility on the profile (T14, absorbs T37)

## ⚠ Re-scoped (2026-07-15)
The **live listening-stats** half of this ticket (AN-7: top tracks/artists, recent, 30-day, streak)
was **moved into [T44](044-profile-live-ui.md)** and folded into that one server-rendered ticket, so
the profile's listening summary can ship now without the analytics engine (per
[ADR-0014](../../../decisions/adr/0014-feed-manual-posts-listening-summary.md)). What remains here is
the **analytics-dependent** part — cluster label + compatibility — which stays **blocked on the
analytics spine (T33/T35)**. T14 no longer blocks T44.

## Rationale
The profile is where the social and analytics layers meet. Under ADR-0003 it computes the taste
vector / cluster / compatibility per-user on read via the on-read inference core. Under ADR-0010 that
inference core is **Python in the FastAPI backend** (ADR-0003 keeps its on-read strategy; only the
language moves from TS to Python — see T33). The live listening-stats aggregation that used to live
here now ships in T44.

## Summary
Add the **cluster label** (T33 assignment) and **compatibility vs the viewer** (T35) to the profile —
computed per-user on read via the Python inference core — degrading gracefully to null when no
`ModelArtifact` exists. The live listening stats (top tracks/artists, streak, 30-day totals) and the
follower/following counts ship in **T44**; this ticket layers the analytics on top once the spine exists.
Whether these attach to the T44 server-rendered page directly or a small JSON endpoint is decided when
picked up (ADR-0013 makes the page and API one app).

## Source
- Spec reqs: **BE-8** (analytics portion); **AN-4** (cluster assignment), **AN-5** (compatibility).
  *(AN-7 live listening aggregation moved to [T44](044-profile-live-ui.md).)*
- ADRs: [ADR-0003](../../../decisions/adr/0003-analytics-runtime.md) (on-read inference) · [ADR-0007](../../../decisions/adr/0007-validation-and-data-integrity.md)

## ⚠ Absorbs T37
ADR-0003 drops the `UserStats` table; the AN-7 aggregation it implied now lives in **T44** as a
SQLModel/SQLAlchemy group-by. **There is no standalone T37.**

## Scope
### In Scope
- Cluster label (T33 assignment) + compatibility vs the authenticated viewer (T35), surfaced on the
  profile (top genres also land here — they need the T31 Kaggle genre join).
- Graceful empties: no `ModelArtifact`/genre data → null cluster/compat/genres. Always 200, never 500
  on missing analytics.

### Out of Scope
- The live listening stats + follower/following counts + now-playing (all in **T44**); the analytics
  page (T45).

## Validation & authz (ADR-0007 — required on this ticket)
- **Schema (Pydantic):** `{id}` param validated.
- **Authorization:** `require_user`; compatibility is computed relative to the authenticated viewer.
- **Business rule:** an empty/synthetic/handle user renders gracefully (nulls/zeros), not an error.
- **Integrity:** reads only; live aggregation reflects current `Play` rows.

## Current State (on `develop`)
- `Play`, `Post`, `Follow` tables; T33 inference core + T35 compatibility helpers; `Cluster`/`ModelArtifact` (T39/T34). No `UserStats` table (dropped).
- No `backend/app/routers/profile.py` yet.

## Files to Create/Modify
| File | Action | Purpose |
|------|--------|---------|
| `backend/app/routers/profile.py` | CREATE | profile assembly: live stats + inference |
| `backend/app/stats.py` | CREATE | live aggregation group-bys (absorbs T37 logic) |
| `backend/tests/test_profile.py` | CREATE | profile + empty-state tests |

## Testing Checklist
- [x] profile with no plays → zeroed stats, null cluster/compat, 200 (not 500) — `test_profile_page_ok_without_analytics`, `test_profile_data_null_analytics_without_model`
- [x] with seeded plays → correct top tracks, streak, 30-day total — covered by T44 (`test_stats.py`); genres N/A, see Outcome
- [x] cluster label present when `ModelArtifact` exists — `test_profile_data_surfaces_cluster_and_compatibility`, `test_profile_page_renders_taste_block`
- [x] compatibility computed vs the authenticated viewer (and hidden on your own profile) — `test_compatibility_hidden_on_own_profile`
- [x] follower/following counts correct — shipped in T44 (`_profile_data`)

## Outcome (as built, 2026-07-28)
The analytics half of the profile — **taste cluster label + compatibility vs the viewer** — now
renders on the existing `/u/{handle}` page (no new router or JSON endpoint; ADR-0013 makes the page
and API one app, so this reuses `_profile_data` + `profile.html` rather than adding a parallel
surface). Wiring only — the maths already existed:

- `backend/app/routers/pages.py` — `_profile_data` calls the T33 `assign_cluster` and T35
  `compatibility` inference helpers on read, exposing `taste_cluster` (`{id,label}` or `None`) and
  `compatibility` (`0..1` or `None`). **Compatibility is skipped on your own profile** (`is_self`) —
  comparing your taste to your own is trivially ~100% and meaningless.
- `backend/app/templates/profile.html` — a "Taste" card, shown only when there's something to show.
  **No new CSS** (reuses existing `.card`/`.section-title`; avoids a cache-version bump that would
  collide with in-flight PR #188). Visual polish is a Sebastian follow-up.
- `backend/tests/test_profile.py` — new; 5 tests covering the null path (never 500 without a model),
  the populated path via monkeypatched inference, and the own-profile compatibility guard.

**Deliberate scope call — genres dropped.** The In-Scope line mentioned "top genres," but there is
**no genre field anywhere** — no `genre` column on `Track`/`User`, and neither Kaggle CSV carries
one (the same gap documented in T32, T33's `taste_vector.py` header, and ADR-0004). Genres are not
buildable without a new data source, so they are omitted rather than faked. AN-6 (if it tracked
genres) stays unshipped for that reason.

**Graceful empties are free.** `assign_cluster`/`compatibility` already wrap everything in
try/except that returns null when the `gold` schema or `ModelArtifact` is absent (local dev, or
before the nightly job runs), so the "always 200, never 500" requirement holds by construction. Full
suite: 322 passing.

## Readiness Checklist
- [x] Summary is specific and actionable
- [x] Files to Create/Modify is populated
- [x] Testing Checklist has items
- [x] Dependencies identified (T13, T33, T35 → blocked_by 013, 033, 035)
- [x] Scope boundaries defined

## Notes
Branch off `develop` as `feat/T14-profile-api`; one PR back into `develop` (never `main`). The live-stats group-bys are the "real aggregation pipeline" the proposal promised — run on read (ADR-0003), now as SQLModel/SQLAlchemy queries. Owner: Andrea.
