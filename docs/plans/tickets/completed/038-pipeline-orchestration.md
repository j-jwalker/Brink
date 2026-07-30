---
status: Completed
priority: Medium
complexity: Medium
category: Feature
tags: [analytics, python, ci, github-actions, scheduling]
blocked_by: [031, 034]
blocks: []
parent_ticket: null
owner: Jonah
---

# Feature: Pipeline orchestration + GitHub Actions nightly (T38)

## Rationale
The Python training steps need to run as one idempotent job on a schedule, with a manual trigger before demos. Per ADR-0006 this runs on GitHub Actions (managed-cron cadence is too coarse, and GitHub Actions keeps the scheduler in-repo).

## Summary
An idempotent `run_pipeline.py` structured as explicit **bronze → silver → gold** stages (land raw → conform `Track`/`Play` → train + export `Cluster`/`ModelMetrics`/`ModelArtifact`), each idempotent and logged, plus a GitHub Actions workflow that runs it nightly + on `workflow_dispatch`.

## Source
- Spec reqs: **AN-8**, **INFRA-4**
- ADRs: [ADR-0006](../../../decisions/adr/0006-scheduling.md) (GitHub Actions, nightly + dispatch) · [ADR-0009](../../../decisions/adr/0009-medallion-layering.md) (staged bronze/silver/gold) · [ADR-0003](../../../decisions/adr/0003-analytics-runtime.md)

## ⚠ Changed from draft
The draft pipeline also ran **compat + aggregate (UserStats)**. Under option A those are TS on-read (T35/T14), so the pipeline is **train-and-export only** — ingest, cluster, write `Cluster`/`ModelMetrics`/`ModelArtifact`. No per-user steps.

**⚠ Also changed (2026-07-28):** the draft had a gold-stage regression step (T36). [ADR-0016](../../../decisions/adr/0016-cut-second-regression-model.md) cut T36 entirely — no dataset supports a defensible popularity regression, and popularity isn't a stable regression target anyway. This pipeline now orchestrates **cluster export only**; there is no regression step to run.

## Scope
### In Scope
- `analytics/run_pipeline.py` — idempotent, **staged** (ADR-0009):
  - **bronze** — land raw Kaggle (T31) into `bronze.kaggle_tracks_raw` (snapshots land via T21).
  - **silver** — conform into `Track`/`Play` (join audio features, coverage, dedup).
  - **gold** — cluster+export (T34); write `Cluster`/`ModelMetrics`/`ModelArtifact`.
  - structured per-stage logging of coverage/k/silhouette; each stage independently re-runnable/backfillable.
- `.github/workflows/analytics.yml` — `astral-sh/setup-uv`, `uv sync` + `uv run python run_pipeline.py`; `schedule` (nightly) + `workflow_dispatch`; `DATABASE_URL` secret.

### Out of Scope
- Synthetic seeding (T32 — a setup step, not nightly), per-user inference (TS), the Spotify snapshot job (T21).

## Validation & authz (ADR-0007)
- **Integrity:** idempotent — a re-run reproduces consistent artifacts/metrics; failures don't leave half-written model state.

## Current State (on `develop`)
- `analytics/` with `db.py`, `ingest_kaggle.py`, `cluster.py` (T30/T31/T34). No `regression.py` —
  T36 was cut ([ADR-0016](../../../decisions/adr/0016-cut-second-regression-model.md)).
- No `run_pipeline.py` or `.github/workflows/analytics.yml` yet.

## Files to Create/Modify
| File | Action | Purpose |
|------|--------|---------|
| `analytics/run_pipeline.py` | CREATE | idempotent orchestration |
| `.github/workflows/analytics.yml` | CREATE | nightly + manual dispatch |
| `analytics/tests/test_run_pipeline.py` | CREATE | dry-run / idempotency test |

## Testing Checklist
- [x] end-to-end dry run on a test DB completes
- [x] re-run produces consistent artifacts/metrics (idempotent)
- [x] logs coverage %, k, silhouette
- [x] workflow valid; nightly schedule + `workflow_dispatch`; uses `DATABASE_URL` secret

## Readiness Checklist
- [x] Summary is specific and actionable
- [x] Files to Create/Modify is populated
- [x] Testing Checklist has items
- [x] Dependencies identified (T31, T34 → blocked_by 031, 034)
- [x] Scope boundaries defined

## Notes
Branch off `develop` as `feat/T38-pipeline-cron`; one PR back into `develop` (never `main`). Owner: Jonah. `workflow_dispatch` is the pre-demo refresh.

## Outcome (as built)

**`analytics/run_pipeline.py`** — a thin orchestrator: `run_pipeline(kaggle_csv_path, engine=None,
cluster_kwargs=None)` calls T31/T33's `ingest_kaggle.run_ingest` (bronze landing + silver `Track`
conform) then T34's `cluster.run_cluster` (gold train + export), returning both summaries. No new
state to coordinate — both underlying functions were already independently idempotent (each
replaces its own results rather than accumulating them), so orchestration really is just "call one,
then the other." T36's regression step is absent entirely (ADR-0016).

**Bug caught before merge:** the first version of the `__main__` CLI entrypoint called
`run_pipeline()` with no `cluster_kwargs`, so `run_cluster` would default to letting silhouette
pick `k` — which prefers **k=2**, not the **k=7** T34 deliberately forced for the T32
synthetic-persona system. Since `cluster.py` always replaces the whole model on every run, the
first real nightly run would have silently regressed the live model and broken every
persona-dependent feature with no error. Fixed: `run_pipeline()` itself stays a neutral,
parameterizable function (so tests can pass their own `cluster_kwargs`); the `forced_k=7` default
now lives only in the CLI entrypoint that production (the workflow) actually invokes.

**`.github/workflows/analytics.yml`** — nightly (03:00 UTC) + `workflow_dispatch`. The real
environmental blocker here: `run_pipeline.py` needs the ~1.2M-row Kaggle CSV
(`analytics/data/tracks_features.csv`, 346MB, gitignored, "sourced manually, never committed"), and
a fresh GitHub Actions runner starts with nothing on disk — there was no existing mechanism to get
that file there. Resolved by hosting it as a GitHub Release asset (`analytics-data-v1`, uploaded
this session) and adding a download step to the workflow. Added the `DATABASE_URL` repo secret the
workflow needs (previously only `CRON_SECRET`/`SNAPSHOT_URL` existed).

**Tests (`analytics/tests/test_run_pipeline.py`):** a fast monkeypatched unit test verifies
orchestration order and that `cluster_kwargs` pass through untouched; the live end-to-end test
(gated behind `RUN_ANALYTICS_DB_TESTS`, like every other analytics DB test) runs the real pipeline
against a disposable `Track` row + a small fixture CSV, confirms the join landed, and confirms
re-running the whole pipeline is idempotent — following `test_cluster.py`'s snapshot/restore
pattern for the gold tables, which have no per-run scoping column. Full suite: **24 analytics
passed, 317 backend unaffected.**

**Known flake, not fixed here:** one full-suite run (1 of 4) hit an unrelated failure in
`test_seed_users.py`'s idempotency test when run alongside this new file; isolated and pairwise
reruns all passed cleanly every time, including this file's own tests. Looks like a pre-existing,
rare interaction from multiple test files sharing one cached DB engine while each
snapshots/restores the same global gold tables — not something this change deterministically
causes, but worth a follow-up if it recurs.

**Verification note (corrected 2026-07-28):** GitHub's repo-configured **default branch is `main`**,
not `develop` — Brink only reaches `main` via a release PR. Both `workflow_dispatch` and the
`schedule` cron only ever fire for a workflow file that exists on the default branch, so merging
this into `develop` was **not** enough to make it runnable; a live Actions run can't be triggered or
verified until a `develop → main` release ships it (the same reason `T64`'s `keepalive.yml` needed
a release before it started working — already noted in `CLAUDE.md`'s Deployment topology section).
The PR body's claim that this would be "triggered and verified immediately after merging" was
wrong — corrected here rather than left standing.
