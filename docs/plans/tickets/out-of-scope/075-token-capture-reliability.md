---
status: Obsolete
priority: High
complexity: Medium
category: Fix
tags: [frontend, auth, spotify, review-remediation]
blocked_by: []
blocks: [076]
parent_ticket: null
owner: Sebastian
---

# Fix: Spotify token-capture reliability + Supabase client guard + `apiFetch` (T75)

> **OBSOLETE (2026-07-15, coherence sweep T79).** Every file this ticket targets lived in the
> `apps/web/` React SPA, which was retired in T60 (ADR-0013). Token capture now happens
> server-side in `/auth/callback` (T09), so the browser capture path this ticket hardened no
> longer exists. The legacy `POST /api/auth/capture-spotify` endpoint's removal is tracked as T63.

## Rationale
Findings **H3**, **H4**, **MF4** of the [2026-07-02 code review](../../reviews/2026-07-02-code-review-t00-t08.md).
(1) `captureSpotifyTokens` never checks `res.ok` and swallows every error in an empty `catch`.
This POST is the *only* moment the Spotify refresh token can reach the server (ADR-0005) — if the
backend returns 401/500 the token is silently lost and the T21 snapshot job breaks for that user
with zero signal. A stale comment ("the /api functions aren't served under plain vite dev" —
pre-T07 world; Vite now proxies `/api` → uvicorn) actively justifies the swallow. (2) Missing
`VITE_SUPABASE_*` env vars make `createClient(undefined, undefined)` throw at module load — the
app white-screens before React mounts, so the entire "misconfigured" UX (LoginPage's "Setup
needed" panel) is unreachable dead code.

## Summary
Build a small shared `apiFetch` helper (attaches the Supabase access token, checks `res.ok`,
throws typed errors), use it for capture-spotify with failure logging + one retry; guard Supabase
client creation so missing config renders the intended "Setup needed" UX instead of crashing.

## Source
- Review findings: **H3**, **H4**, **MF4**
- Spec reqs: **AUTH-1** (Spotify login e2e), **AUTH-3** (server-side token capture)
- ADRs: [ADR-0005](../../../decisions/adr/0005-identity.md) (we own token capture/refresh) · [ADR-0010](../../../decisions/adr/0010-fastapi-render-backend.md) (same-origin `/api/*`)

## Scope
### In Scope
- `apps/web/src/lib/api.ts` (CREATE): `apiFetch(path, opts)` — attach `Authorization: Bearer
  <supabase access token>`, check `res.ok`, throw a typed error with status + message. This is
  the helper every T40–T52 wiring ticket reuses; three review streams independently converged on
  it ("reuse before reinventing").
- `AuthContext.tsx`: `captureSpotifyTokens` via `apiFetch`; on failure log (`console.warn` at
  minimum) and retry once; delete the stale vite-dev comment.
- `lib/supabase.ts`: export a `configured` flag; only call `createClient` when configured (or use
  a lazy/null-object pattern) so `AuthContext`'s existing `misconfigured` status and LoginPage's
  "Setup needed" panel actually render.

### Out of Scope
- The other AuthContext issues (refire guard, loadProfile, deadlock, dedupe) — T76, which builds
  on this. Any backend change. Surfacing capture failure in UI beyond a console signal (note as
  follow-up if wanted).

## Validation & authz (ADR-0007)
Client-side only; the server still validates the JWT on capture. `apiFetch` centralizes the
token-attach so future endpoints can't forget the auth header (the POC's `backend.ts` sends none).

## Current State (on `develop`)
- Inline `fetch` in `AuthContext.tsx:30-45` with empty catch; eager `createClient` at module
  scope in `lib/supabase.ts:3-8`; unreachable `misconfigured` branch in `AuthContext.tsx:9-11`
  and `LoginPage.tsx:34-40`.

## Files to Create/Modify
| File | Action | Purpose |
|------|--------|---------|
| `apps/web/src/lib/api.ts` | CREATE | shared authorized fetch helper |
| `apps/web/src/context/AuthContext.tsx` | MODIFY | reliable capture + comment fix |
| `apps/web/src/lib/supabase.ts` | MODIFY | guarded client creation + `configured` export |

## Testing Checklist
- [ ] with env vars absent, the app renders LoginPage's "Setup needed" panel (no white screen)
- [ ] capture-spotify 500 → visible console warning + one retry (verify via devtools/network)
- [ ] happy path unchanged: login on local dev stores the encrypted token (backend log/DB)
- [ ] `cd apps/web && npm run build` and `npm run lint` pass

## Readiness Checklist
- [x] Summary is specific and actionable
- [x] Files to Create/Modify is populated
- [x] Testing Checklist has items
- [x] Dependencies identified (none; blocks 076)
- [x] Scope boundaries defined

## Notes
Branch `fix/T75-token-capture-reliability`. No automated frontend test harness exists yet —
verification is manual against local dev (two-terminal setup per CLAUDE.md); state that in the PR.
