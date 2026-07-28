# Brink — Requirements & Traceability

The catalog of requirement IDs (`AUTH-*`, `BE-*`, …) and the **requirement → ticket** map. This replaces the old `brink-spec-design.md`: decisions now live in [`docs/decisions/`](../decisions/), the data model in [`backend/app/models.py`](../../backend/app/models.py) (SQLModel), and the implementation plan in [`tickets/`](tickets/). This file is the glue that proves the proposal's scope is covered.

**Status:** ✅ done · ◧ partially done (remainder tracked in the noted ticket) · ◻ backlog · **†** = original spec text superseded by a later decision (see [Superseded](#superseded-spec-text)).

## Layer 1 — Identity & Auth (AUTH)
| ID | Acceptance | Ticket(s) | Status |
|----|------------|-----------|--------|
| AUTH-1 | Spotify login via Supabase provider; first login creates/links a `public.User`. | T02 (browser), T09 (server-side) | ✅ |
| AUTH-2 | Capture + encrypt the Spotify refresh token server-side in `SpotifyToken`. | T02 (browser), T09 (server-side callback) | ✅ |
| AUTH-3 † | Email signup for handle accounts — now **email + password** server-side (was magic-link/OTP), per [ADR-0015](../decisions/adr/0015-email-password-auth.md): `/auth/signup` + `/auth/login-email`, confirmations ON, IP+email rate-limited. | T03 | ✅ |
| AUTH-4 | Every `/api/*` mutation verifies the Supabase JWT. | T02 + every API ticket (ADR-0007); T09 (session cookie) | ✅ base |
| AUTH-5 | Server owns Spotify token refresh for the snapshot job. | T22 | ✅ |
| AUTH-6 | Handle accounts work fully except Spotify-derived stats ("link Spotify"). | T03, T44 | ✅ (T03 gives the email/password front door; a handle user can post/react/comment/follow, and every Spotify surface degrades to empty states + a "link Spotify" prompt on the profile from T44. *Linking* Spotify to an existing email account is a stated follow-up.) |

## Layer 2 — Backend API + Data Model (BE)
| ID | Acceptance | Ticket(s) | Status |
|----|------------|-----------|--------|
| BE-1 | Supabase Postgres + schema (SQLModel/Alembic); pooled URLs in env. | T01, T05 | ✅ |
| BE-2 | Remove `apps/web/src/lib/backend.ts` (`/api/state`) + dead front-end stubs. *(satisfied by retiring the whole SPA — the entire `apps/web/` was deleted in T60, ADR-0013)* | T60 | ✅ |
| BE-3 | `POST /api/posts` — create post (manual/Spotify); upsert track. | T10, T101, T104 | ✅ (T101 exercises the `SPOTIFY`-source create path from the one-tap share button; T104 makes the track **optional** — a text-only post has `trackId = NULL` — with a 400 guard against a post that has neither a song nor text) |
| BE-4 | `GET /api/feed` — followees+self, newest, counts + viewer reaction. User search and follower/following lists make the graph discoverable. | T13, T15, T16 | ✅ |
| BE-5 | `POST/DELETE /api/posts/:id/reactions` — server-deduped toggle. | T11 | ✅ |
| BE-6 | `POST/GET /api/posts/:id/comments`. | T12 | ✅ |
| BE-7 | `POST/DELETE /api/follow/:userId` — feed respects the graph. | T13 | ✅ |
| BE-8 | `GET /api/users/:id/profile` — stats + cluster + compatibility. | T14 | ◻ |
| BE-9 | `POST /api/artist/posts` — create BTS post + optional track. | T50 | ✅ |
| BE-10 | All mutations: session-gated, validated, consistent error JSON. | every API ticket (ADR-0007) | ◻ |
| BE-11 | Connection pooling (Supabase pooler) configured. | T01, T05 | ✅ |

## Layer 3 — Spotify Integration (SP)
| ID | Acceptance | Ticket(s) | Status |
|----|------------|-----------|--------|
| SP-1 | Currently-playing endpoint + "now playing" surface. | T20 | ◻ |
| SP-2 † | Scheduled snapshot: refresh token, pull recently-played, upsert `Track`/`Play` (dedup). | T21, T100 | ✅ (T100 tightened the cron to every 30 min and added `POST /api/me/plays/refresh` for a visit-triggered self-sync, reusing the same dedup ingest) |
| SP-3 | Upsert `Track` rows whenever tracks are seen. | T10 | ✅ |
| SP-4 | Graceful degradation: Spotify outage / unlinked user never breaks the app. | T20, T21 | ✅ |
| SP-5 | Respect rate limits; back off on 429; never block a request path. | T21, T100 | ✅ (T100's self-refresh is throttled 2/600s via `enforce_rate_limit`) |

## Layer 4 — Analytics & Data Science (AN)
| ID | Acceptance | Ticket(s) | Status |
|----|------------|-----------|--------|
| AN-1 | Ingest Kaggle audio features into a `Track`-joinable form; record coverage. | T31 | ✅ |
| AN-2 † | Per-user taste vector (standardized) + C4 genre fallback. *(now computed on read, no table)* | T33 | ✅ fallback is a corpus-mean vector, not literally "genre" (disclosed — neither Kaggle file has a genre field; see T33 Outcome) |
| AN-3 | K-means on Kaggle tracks; k via elbow+silhouette; persist `Cluster` + metrics. | T34 | ✅ k forced to 7 (disclosed — silhouette preferred k=2; see T34 Outcome) |
| AN-4 † | Assign each user to nearest cluster. *(computed on read in the Python API; `User.clusterId` dropped)* | T33, T14 | ◧ (T33: on-read nearest-`Cluster` assignment is live and tested; surfacing it to a user is T14, still open) |
| AN-5 † | Compatibility = cosine of full taste vectors. *(computed on read in the Python API; no pairwise table)* | T35, T14 | ◧ (T35: `cosine()`/`compatibility()` live and tested, reusing T33's taste vectors; surfacing it to a user is T14, still open) |
| AN-6 † | Popularity regression; persist R²/RMSE/feature-importances. | T36 | **Cut** — no dataset supports a defensible popularity regression, and popularity itself isn't a stable regression target (see [ADR-0016](../decisions/adr/0016-cut-second-regression-model.md)); the second/regression model is not being built |
| AN-7 † | Aggregations: top tracks/genres/artists, streak, 30-day totals. *(computed live in the Python API, no `UserStats` table)* | T44, T14, T102 | ◧ (T44: top **tracks/artists**, streak, 30-day totals done live over `Play` in `app/stats.py`; T102 adds a batched per-(author, track) play count on feed cards over the same `Play` data; top **genres** still deferred to T14, needs the T31 Kaggle genre join) |
| AN-8 | Pipeline idempotent + re-runnable; logs coverage/k/silhouette/R²/RMSE. | T30, T38 | ◻ |
| AN-9 † | Analytics UI on real model data; no hardcoded constants. *(reads metrics/clusters + on-read values)* | T45 | ◧ (T45: analytics page reads real `ModelMetrics`/`Cluster` with **no** hardcoded numbers; the K-means/community half is live, and the popularity half fills in automatically when **T36** writes `ModelMetrics("popularity_regression")`) |

## Layer 5 — Frontend / UX-UI (UI)
| ID | Acceptance | Ticket(s) | Status |
|----|------------|-----------|--------|
| UI-1 | Post composer with Spotify catalog search → publish. | T40, T81, T101, T104 | ✅ (T81 follow-up hardens keyboard interaction and labels; T101 adds a one-tap "share what you're hearing" button that reuses the same selected-track → publish path; T104 makes the song **optional** — the text box + Share are always shown and a song is an optional removable chip, so a user can post "just writing".) |
| UI-2 | Feed reads `/api/feed`; manually shared song cards, plus the behind-the-scenes posts of the artists you follow (interleaved newest-first, with like/comment controls). *(feed is manual-only — auto Spotify cards dropped per [ADR-0014](../decisions/adr/0014-feed-manual-posts-listening-summary.md); listening surfaces on the profile, not the feed; T47 added the app-shell nav — feed/profile/artist/logout links; T049 added followed artists' posts; T102 added the "played N times by {author}" endorsement line on song cards; T103 hardened artist-image signing so one un-signable image degrades to a placeholder instead of blanking the feed / 500ing the artist page)* | T41, T47, T049, T102, T103 | ✅ |
| UI-3 | Reactions call BE-5; counts reflect server truth. | T41, T96, T97 | ✅ (T96 adds the "Liked by X and N others" line + a `GET /api/posts/{id}/reactions` reactors list, backed by a new additive `Reaction.createdAt` migration. T97 adds the double-tap-to-heart gesture on song cards — add-only, reuses the same `react()` path; no API change.) |
| UI-4 | Comments become real input + list. | T42, T81, T95 | ✅ (T81 follow-up hardens expanded/loading/error states. T95 renders each card's newest comments inline, Instagram-style; no API endpoint change.) |
| UI-5 | Follow/unfollow buttons + follower counts/lists + searchable profiles, including artist profile content. | T43, T46, T54, T16, T80, T82 | ✅ (T80/T82 are UI hardening follow-ups for profile actions and responsive layout.) |
| UI-6 | Profile renders stats + cluster + compatibility; link-Spotify prompt. | T44, T14, T82 | ◧ (T44: live listening **stats** + link-Spotify prompt done; **cluster + compatibility** deferred to T14, blocked on analytics. T82 hardens responsive listening layouts.) |
| UI-7 | Analytics page renders real metrics/clusters; remove `CLUSTER_POINTS`. | T45 | ◧ (T45: `/analytics` page reads real `ModelMetrics`/`Cluster`, no hardcoded constants — `CLUSTER_POINTS` was in the React SPA, already gone in T60. Clustering half live; popularity metrics fill in at T36.) |
| UI-8 | Predict folded into Analytics; delete fabricated page/route. | T45 | ◧ (the fabricated `PredictPage`/`/predict` route was removed with the SPA in T60; the client-side popularity-predict widget is deferred until T36 exports the regression coefficients — the analytics page already surfaces the popularity model's quality once T36 lands.) |
| UI-9 | Loading/empty/error states; no silent mock fallback. | T41, T44, T60, T80, T81, T83, T84, T85, T86 | ✅ (the live Jinja pages render real empty/error states — feed, profile — and the mock-fallback SPA was deleted in T60. T80/T81/T83 are polish follow-ups for visible failure, loading, and empty-state quality. T84 keeps optional profile enrichments from turning `/u/{handle}` into a 500. T85 prevents stale static assets from hiding those shipped UI states. T86 restores the edit form's collapsed initial state.) |
| UI-10 | "Now playing" indicator on profile + feed. | T20, T44, T82 | ◧ (T44: own-profile badge done via me-scoped T20; **feed** badge + **other users'** now-playing need a new per-user endpoint — follow-up. T82 hardens the existing profile layout.) |
| UI-11 | Editable profile: user bio + profile-picture upload. | T048, T83, T85, T86 | ✅ (T83 polishes the edit-profile controls, T85 ensures browsers load that design, and T86 keeps the form hidden until Edit profile is activated. No API behavior change.) |
| UI-12 | Feed song cards are playable in place via the Spotify embed player (no auth needed; lazy-loaded on tap, one open player at a time). | T94 | ✅ |

## Layer 6 — Artist BTS Portal & Media (MEDIA)
| ID | Acceptance | Ticket(s) | Status |
|----|------------|-----------|--------|
| MEDIA-1 | Supabase Storage private bucket + signed upload URL (service role). | T50 | ✅ |
| MEDIA-2 | Upload UI: ≤10 MB + JPEG/PNG validation (client+server); progress/error. *(T53 made the uploaded images actually display — signed read URLs for the private bucket; T104 makes the photo **optional** and reverts T57's caption-hide, since an artist post can now be text-only)* | T51, T53, T57, T83, T104 | ✅ (T83 follow-up polishes the existing upload controls; T104 makes the caption always-visible and the photo optional — no change to the ≤10 MB/JPEG/PNG validation, which still runs when a photo IS attached.) |
| MEDIA-3 | Create `ArtistPost` with Storage URL + optional linked track. | T50, T104 | ✅ (T104 makes the Storage URL **optional** too — a text-only `ArtistPost` has `imageUrl = NULL` — with a 400 guard against a post that has neither a photo nor text) |
| MEDIA-4 | Per-post engagement analytics shown to the artist. | T52, T54 | ✅ (reaction + comment counts, owner-only on artist profiles; view count deferred) |
| MEDIA-5 | ≥98% upload success across 5 file types up to 10 MB. | T51, T53 | ◧ (T53 verified the storage round-trip live on brink-dev: service-role upload → signed read URL → 200 with matching bytes, unsigned GET 400; the browser-upload half + the 5-file-type success-rate measurement remain) |
| MEDIA-6 | Self-serve artist designation in-app (no DB edit) — become an artist from your own profile. | T55, T56, T80 | ✅ (`POST /api/me/become-artist` sets `isArtist` on the authenticated caller; own-profile "Become an artist" button; one-way, self-serve per ADR-0008. T56 polished the button: readable ghost buttons, top-right placement, "cannot be undone" confirmation. T80 follow-up makes the action more discoverable/responsive and adds visible failure feedback.) |

## Layer 7 — Infrastructure & Scheduling (INFRA)
| ID | Acceptance | Ticket(s) | Status |
|----|------------|-----------|--------|
| INFRA-1 † | Vercel project: SPA + `/api/*` rewrite to Render; env vars set, no secrets in repo. | T01, T07 | ✅ |
| INFRA-2 | Supabase provisioned; pooled URLs; migrations in CI; Data API disabled. | T01 | ✅ |
| INFRA-3 † | Snapshot trigger on a fixed cadence. *(GitHub Actions, not Vercel Cron)* | T21 | ✅ |
| INFRA-4 | GitHub Actions runs the Python pipeline against Supabase. | T30, T38 | ◻ |
| INFRA-5 | Secret hygiene: `.gitignore` enforced; secrets in env only. | T00 | ✅ |

## Layer 8 — Data Sources & Seeding (DATA)
| ID | Acceptance | Ticket(s) | Status |
|----|------------|-----------|--------|
| DATA-1 | Load Kaggle audio-feature set; document source; join on `track_id`. | T31 | ✅ |
| DATA-2 † | Seed ~100–200 synthetic users (genre-coherent personas). *(scoped to ~50 — see T32's Outcome; personas are T34's 7 trained clusters, since neither Kaggle CSV has a genre column)* | T32 | ✅ 50 users across 7 personas |
| DATA-3 | Synthetic users disclosed; never inflate real-user metrics. | T32 | ✅ every seeded user is `isSynthetic=true` and its `bio` names it as synthetic demo data + its persona |
| DATA-4 | Retire `mocks/*` from production paths once live. *(the whole SPA — mocks included — was deleted in T60)* | T60 | ✅ |

## Tickets without a legacy requirement ID
- **T39** — analytics schema migration (`ModelArtifact` + medallion bronze/silver/gold). Decision-driven (ADR-0003 / ADR-0009), no original spec req.
- **T37** — Alembic schema reflection (`include_schemas` + guards) so autogenerate sees the medallion schemas. Tooling follow-up to T39 (ADR-0009), no spec req.
- **T23** — snapshot-500 remediation: flush each upserted Track before its Play (FK insert-ordering) + guard token decryption so an unreadable token degrades to None. Production bug fix on T21/T22, no spec req.
- **T62** — FK-ordering hardening: enforce foreign keys in the shared test fixture, fix the posts endpoint's parent-before-child insert, correct the Render deploy-branch doc. Follow-up to T23, no spec req.
- **T61** — test sweep + k6 + cross-browser E2E. Completed the repeatable QA gate: backend API surface inventory, analytics pytest in CI-safe mode, k6 script, and `docs/qa-checklist.md` for manual browser/load/success-metric evidence. Maps to proposal §6/§11 below.

## Success-metric traceability (proposal §11)
| Proposal metric | Met by |
|-----------------|--------|
| Spotify OAuth ≥ 95% | AUTH-1, SP-* |
| Upload success ≥ 98% | MEDIA-5 (T51) |
| 6/6 core features working | BE-3..8, UI-1..6 |
| Real ML (clustering + regression) | AN-3, AN-5, AN-6 |
| Load test 5 concurrent users | T61 — k6 script and thresholds ready; live run is an owner-run release gate |

## Superseded spec text
The old `brink-spec-design.md` is **retired**; these acceptance criteria (flagged † above) evolved after it was written — defer to the ADRs:
- **INFRA-1** — original spec assumed Vercel serverless (`api/`) as the backend. ADR-0010 moved the API to FastAPI on Render; then **T60 retired the Vercel SPA entirely** ([ADR-0013](../decisions/adr/0013-python-frontend.md)), so **Render now serves both the API and the Jinja frontend** — Vercel is no longer used ([ADR-0010](../decisions/adr/0010-fastapi-render-backend.md)).
- **AN-2/4/5/7/9** — per-user analytics are computed **on read in the API** (written when the backend was TypeScript; since ADR-0010 that means the FastAPI/Python app), not materialized; `UserStats`/`TasteVector`/`Compatibility` tables and `User.clusterId` are dropped, `ModelArtifact` added ([ADR-0003](../decisions/adr/0003-analytics-runtime.md), [ADR-0009](../decisions/adr/0009-medallion-layering.md)).
- **AN-6** — the second/regression model is **cut**, not built: no Kaggle dataset supports a defensible popularity regression (the training corpus has no popularity column; the only file that does is frozen at April 2019; the real DB overlap is 67 rows), and popularity itself isn't a stable regression target ([ADR-0016](../decisions/adr/0016-cut-second-regression-model.md)).
- **SP-2 / INFRA-3** — snapshot is triggered by **GitHub Actions**, not Vercel Cron ([ADR-0006](../decisions/adr/0006-scheduling.md)).
- **AUTH-3** — the front door is **email + password** (not the spec's magic-link/OTP), server-side per [ADR-0015](../decisions/adr/0015-email-password-auth.md); the handle stays **auto-derived** (no custom-handle field on the signup form).
- Storage is **Supabase Storage** (not Cloudinary); Kaggle set is a genuine ~1M-track source (not `maharshipandya`) ([ADR-0002](../decisions/adr/0002-api-and-persistence.md), [ADR-0004](../decisions/adr/0004-analytics-data-strategy.md)).
- **DATA-2** — scoped to **~50** synthetic users, not the original ~100–200: population is now a demo/UX need rather than a modeling one (T34 already trains K-means on the full Kaggle corpus, independent of synthetic user count), and `Play.trackId`'s FK to `Track` meant genre-coherent sampling at 100–200 users wasn't achievable with the existing Kaggle-matched `Track` pool. Disclosed on T32's ticket, same as T31's dataset-size call — not an ADR change.
