# ADR-0004: Analytics data strategy

**Status:** Accepted — *C5 (popularity regression) superseded by
[ADR-0016](0016-cut-second-regression-model.md) (cut, not built); C1–C4 remain in force.*
**Date:** 2026-06-22
**First captured as:** spec decision-log rows C1–C5

## Context

The analytics layer (see [ADR-0003](0003-analytics-runtime.md)) needs enough real data to produce genuine, defensible ML results despite two limits: Spotify returns only the last 50 plays, and the live user population is tiny. Audio features come from a Kaggle dataset whose coverage of real-world tracks is imperfect.

## Decision

Five linked choices on how data feeds the models:

- **C1 — Listening history:** snapshot recently-played into Postgres on a schedule. Spotify only returns the last 50 plays, so snapshots make 30-day stats, streaks, and the **live UserStats aggregation** ([ADR-0003](0003-analytics-runtime.md)) genuinely real — `Play` is the table all of those read.
- **C2 — K-means unit:** **train** K-means on the Kaggle track audio-space (real elbow/silhouette on ~1M tracks), then represent each user by their taste vector in that same feature space and **assign** them to the nearest centroid by on-demand inference ([ADR-0003](0003-analytics-runtime.md)). A listener "segment" is the audio region a user's taste sits in — **one model trained on tracks**, not a second K-means over users (which would be weak at our user scale).
- **C3 — Synthetic users:** seed ~100–200 synthetic listeners as **genre-coherent personas** — each built from 1–3 genres / audio-profiles (e.g. "mellow indie," "high-energy mainstream") sampled from real Kaggle tracks, **disclosed as demo data**. Personas (rather than random track sampling) make clusters actually separate and compatibility scores meaningful on screen. Feed, compatibility, and cluster assignment need population; disclosure keeps it honest. *(Resolves the open DATA "synthetic-user generation method.")*
- **C4 — Audio-feature gaps:** use a genre-only fallback vector when a track isn't in the Kaggle set, and report coverage %. Coverage will be imperfect for emerging artists; an honest fallback is defensible.
- **C5 — Popularity regression:** build it, scoped small; report R²/RMSE + feature importances, labeled exploratory. A cheap second real model that strengthens the analytics story.

The Kaggle source is an **actually ≈1M+ track audio-features set** for real `track_id` join coverage — honoring the scale the proposal stated ("~1M+") rather than its named set (`maharshipandya`, which is really ~114k).

## Alternatives considered

- **Live Spotify data only** — capped at 50 plays and a tiny user base; can't support real clustering or 30-day stats.
- **User-only K-means** — too few users for meaningful clusters or silhouette scores.
- **Drop tracks missing audio features** — silently shrinks the dataset; the genre-only fallback with a reported coverage % is more honest.

## Consequences

- Synthetic users and the chosen Kaggle set must be **disclosed** in the final report; coverage % is reported, not hidden.
- Snapshotting requires a scheduled job and server-side Spotify token refresh (see [ADR-0005](0005-identity.md), [ADR-0006](0006-scheduling.md)).
- **C4's genre-only fallback runs in two runtimes:** the Python training data-prep (track corpus) *and* the **TS on-demand inference** path, because taste vectors are built on read ([ADR-0003](0003-analytics-runtime.md)). Both read `Track.audioFeatures`/`kaggleMatched`, so the fallback + coverage logic must exist in each.
- **Deviation from the proposal's named dataset** — the proposal named `maharshipandya` (~114k) but labeled it "~1M+"; we adopt a genuinely ~1M+ set to honor that stated scale. Correct the dataset name in the final report and defend the larger set as a deliberate coverage choice.
