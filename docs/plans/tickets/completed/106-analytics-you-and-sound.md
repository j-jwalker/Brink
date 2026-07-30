---
status: Completed
priority: Medium
complexity: Low
category: Feature
tags: [frontend, analytics]
blocked_by: [045, 033, 035]
blocks: []
parent_ticket: null
owner: Sebastian
---

# Feature: Finish the analytics page's two placeholder cards (T106)

## Rationale
The analytics page (T45) shipped with two permanent "coming soon 🔮" placeholders that never
filled in:
1. **"Which tribe are you in?"** — waited on per-listener matching, which actually landed with
   `T33`/`T35`/`T14` (the on-read `assign_cluster`). So the data to place the viewer already exists;
   the card just wasn't wired to it.
2. **"What makes a song popular?"** — waited on the second (popularity) model, which was **cut**
   ([ADR-0016](../../decisions/adr/0016-cut-second-regression-model.md)): no dataset supports a
   defensible popularity regression. That "coming soon" was therefore a promise that could never be
   kept, and it directly contradicted the presentation's own "we cut this and said so" honesty note.

## Summary
- **Tribe card → live.** `_viewer_tribe` (in `pages.py`) runs the same on-read `assign_cluster` (T33)
  the profile page uses, matches the result back to the community card `_analytics_data` already
  builds (added an `id` to each community for the join), and the template shows "You're in
  *<tribe>*", its rank/share, the viewer's coverage %, and that tribe's audio DNA. Three graceful
  states: placed / not-enough-listening-yet / no-model (the card only renders inside the clustering
  block, so a missing model shows the existing "communities aren't ready" state — never a crash).
- **Popularity card → "The sound of Brink".** Replaced with a real, finished insight built from the
  model we *do* have: the audio traits that define the whole listener base, computed in
  `_analytics_data` as the mean of every tribe's audio DNA (`a.sound`). It is a plain descriptive
  summary of the trained clusters, **not** a new prediction — no fabricated numbers.

## Outcome
Route/data (`_analytics_data` + new `_viewer_tribe`), template (`analytics.html`), and CSS
(`brink.css`: `.you-card`, `.sound-fill`, `.an-card-sub`; stylesheet bumped to `?v=87`). Tests in
`test_pages.py`: the rich-visuals test now asserts the populated "you" tribe card + the sound card;
the pending-state test asserts the model-less states. Full backend suite green. No new endpoint
(ADR-0013) and no model/schema change — this is a read-only surfacing of existing inference.
