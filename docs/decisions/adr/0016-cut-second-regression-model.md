# ADR-0016: Cut the second (regression) model

**Status:** Accepted
**Date:** 2026-07-28
**Supersedes:** the **C5** bullet of [ADR-0004](0004-analytics-data-strategy.md) (popularity
regression) only; C1–C4 (snapshotting, K-means unit, synthetic personas, audio-feature fallback)
remain in force.
**Relates to:** requirement `AN-6`; tickets T36, T38.

## Context

ADR-0004 C5 called for a linear regression predicting `Track.popularity` from audio features, as a
cheap second real model. Scoping T36 surfaced that no dataset actually supports this:

- The ~1.2M-track corpus T34 trains K-means on (`analytics/data/tracks_features.csv`) has **no
  `popularity` column at all**. The only Kaggle file that has one is a ~130k-row interim set with
  values frozen at **April 2019**.
- The DB-native overlap (`kaggleMatched=true` + a live `popularity` value) is only **67 rows** as
  of 2026-07-23 — too thin for a defensible train/test split.
- More fundamentally: Spotify popularity **isn't a stable target at all**. It's a live,
  continuously-recomputed metric, not a fixed property of a track the way its audio features are —
  so even a hypothetically larger, fresher sample wouldn't fit the same kind of regression the
  clustering model does. A frozen popularity value is a snapshot of a moving number, not ground
  truth.

A retarget (predict `valence` from the other 9 audio features instead, trained directly on the
full local Kaggle CSV the same way T34 trains K-means) was drafted and would have sidestepped the
data problem entirely — valence, unlike popularity, is a fixed audio-feature value with no
staleness or thin-N issue.

## Decision

**Cut the second model entirely.** No regression ticket is built, on popularity or valence. The
second model was always framed as a cheap, optional addition to the analytics story (ADR-0004 C5:
"a cheap second real model that strengthens the analytics story"), not a functional requirement
anything else in the app depends on — with the 2026-07-30 deadline close, that scope is being
dropped rather than spent on optional narrative polish.

- **T36** is marked **Obsolete** (kept in `backlog/` for history, not built).
- **T38**'s pipeline drops the regression-export step and its dependency on T36 — it now
  orchestrates ingest + cluster only.
- **T45**'s analytics page needs no change: it was already built to show a permanent, graceful
  "not tracked" state for the popularity/second-model slot when no such `ModelMetrics` row exists,
  so this decision just means that state is now permanent rather than temporary.
- **`requirements.md` AN-6** is marked cut, not satisfied — disclosed, not hidden.

## Alternatives considered

- **Ship T36 as originally scoped, on the 67-row DB overlap.** Rejected — far too small to be a
  defensible regression result.
- **Retarget to a valence regression** (the drafted approach — see Context). Rejected not because
  it wouldn't work technically, but because the team chose to simplify remaining scope given how
  close the deadline is, rather than spend the (admittedly low) remaining engineering cost on an
  always-optional second model.
- **Train on the 2019 interim CSV for scale.** Real N (~130k), but 6+ years stale for a "current
  popularity" claim, and reuses a dataset ADR-0004 already said to replace.

## Consequences

- **No schema change** — `Track.popularity` is untouched and keeps working exactly as it does
  today for live display (feed/search/posts); this ADR only cuts an analytics *training* target
  that was never built.
- `AN-6` stays permanently unsatisfied, disclosed in `requirements.md` rather than left looking
  like an oversight.
- `docs/qa-checklist.md`'s "Real ML" line no longer waits on T36.
- ADR-0004 stays the record for C1–C4; only C5 is superseded here (append-only: 0004 is not edited
  beyond a status pointer to this ADR).
