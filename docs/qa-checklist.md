# Brink QA Checklist (T61)

WHAT THIS FILE IS: the release verification checklist for the proposal success metrics. It is not a feature spec; it records the repeatable checks for backend tests, analytics tests, load, browser E2E, and owner-only manual gates.

## Automated Checks

Run these from the repo root before release:

```powershell
cd backend
uv run pytest -q

cd ..\analytics
uv run pytest -q
```

The default analytics pytest run is hermetic: live Supabase integration tests are skipped unless explicitly enabled. To run the live database checks:

```powershell
cd analytics
$env:RUN_ANALYTICS_DB_TESTS = "1"
uv run pytest -q
```

CI now runs both suites on every PR:

- `api`: `cd backend && uv run pytest -q`
- `analytics`: `cd analytics && uv run pytest -q`
- `secrets`: gitleaks scan
- `docs-sync`: source changes must carry docs in the same PR

## API Surface

The backend suite includes `backend/tests/test_api_surface.py`, which locks the expected `/api/*` route inventory. Endpoint behavior remains covered in the route-specific files:

- Auth/session and email auth: `backend/tests/test_auth*.py`
- Posts, feed, follow, users, search: `backend/tests/test_posts.py`, `test_feed.py`, `test_follow.py`, `test_users_*.py`, `test_search.py`
- Reactions/comments: `backend/tests/test_reactions.py`, `test_comments.py`
- Spotify snapshot/now-playing: `backend/tests/test_snapshot.py`, `test_now_playing.py`, `test_spotify.py`
- Artist upload/posts/engagement: `backend/tests/test_artist.py`, `test_artist_engagement.py`
- Pages and app shell: `backend/tests/test_pages.py`

## Load Test

Install k6 locally, then run:

```powershell
k6 run -e BASE_URL=https://brink-xg7p.onrender.com load/k6-script.js
```

Default target: 5 virtual users for 1 minute.

Pass thresholds:

- `http_req_failed < 1%`
- `p95 http_req_duration < 1000ms`
- `checks > 99%`

Optional authenticated run:

```powershell
k6 run -e BASE_URL=https://brink-xg7p.onrender.com -e AUTH_TOKEN=<supabase-jwt> load/k6-script.js
```

Optional snapshot cron run:

```powershell
k6 run -e BASE_URL=https://brink-xg7p.onrender.com -e CRON_SECRET=<render-cron-secret> load/k6-script.js
```

Do not commit tokens or cron secrets. Record the run date, target URL, and k6 summary in the release notes.

## Manual Browser E2E

Run these in Chrome, Firefox, and Safari or Edge if Safari is not available on the tester's machine:

- Anonymous landing page loads and login/signup links are visible.
- Email signup shows the confirmation flow; confirmed email login reaches the signed-in app shell.
- Spotify login reaches `/feed` after callback.
- Feed composer can search Spotify, publish a post, react, comment, and show server counts.
- User search finds a profile; follow/unfollow changes the profile count and feed membership.
- Artist account can open `/artist`, upload an allowed image, create a post, and view it on `/u/{handle}`.
- Non-artist account can react/comment on an artist post but cannot see owner-only engagement totals.
- Profile shows listening empty states for unlinked users and listening stats for linked users.

## Success Metrics

Record evidence before the final course/demo release:

| Metric | How to verify | Status |
|---|---|---|
| Spotify OAuth >= 95% | Repeat real Spotify login attempts against Render; count successful callbacks to `/feed`. | Manual owner run required |
| Upload success >= 98% | Upload 5 valid JPEG/PNG files up to 10 MB through `/artist`; count successful signed upload + rendered image reads. | Manual owner run required |
| 6/6 core features working | Complete the browser E2E list above. | Manual owner run required |
| Real ML | Jonah-owned analytics spine: T32/T34/T33/T35 landed; T36 (popularity regression) cut entirely (ADR-0016 — no dataset supports it); T38 (pipeline orchestration) still to land. | Blocked on T38 |
| Load test at 5 users | Run `load/k6-script.js`; thresholds above must pass. | Ready to run |
| Analytics DB integration | Run `RUN_ANALYTICS_DB_TESTS=1 uv run pytest -q` from `analytics/` against brink-dev. | Manual owner run required |

## Known Limits

- T14 (profile cluster + compatibility) is unblocked (T33/T35 landed) but not yet built, so cluster and compatibility cannot be verified yet.
- The analytics report has one real model fewer than originally scoped: T36 (popularity regression) was cut entirely (ADR-0016) — no Kaggle dataset supports a defensible popularity regression, and popularity isn't a stable regression target anyway.
- The k6 script intentionally uses public-safe paths by default; authenticated and cron paths require local secrets passed through environment variables.
- Browser E2E requires real Supabase/Spotify/Storage configuration and cannot be proven by CI alone.
