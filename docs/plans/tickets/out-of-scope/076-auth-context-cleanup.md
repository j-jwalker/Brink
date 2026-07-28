---
status: Obsolete
priority: Medium
complexity: Medium
category: Fix
tags: [frontend, auth, react, review-remediation]
blocked_by: [075]
blocks: []
parent_ticket: null
owner: Sebastian
---

# Fix: AuthContext cleanup — refire guard, dedupe, deadlock footgun, dead code (T76)

> **OBSOLETE (2026-07-15, coherence sweep T79).** `AuthContext.tsx`, `CallbackPage.tsx`,
> `LoginPage.tsx`, `NavBar.tsx` were all deleted with the `apps/web/` SPA in T60 (ADR-0013).
> Login is now server-side (T09) with no browser auth listener at all.

## Rationale
Findings **MF1**, **MF2**, **MF3**, **MF5**, **L11** of the [2026-07-02 code review](../../reviews/2026-07-02-code-review-t00-t08.md).
The auth slice works but carries a cluster of listener-behavior issues that will multiply as T40+
pages consume it: capture-spotify can re-fire on every `SIGNED_IN` (tab focus, multi-tab,
StrictMode double-subscribe); `loadProfile()` hits Spotify `/me` on every auth event including
`TOKEN_REFRESHED`, with out-of-order resolution possible; the listener calls
`supabase.auth.getSession()` from inside `onAuthStateChange` (the supabase-js documented
navigator-lock deadlock footgun) when the session is already the callback argument; and the
session→state derivation now exists in three places (listener, `refresh`, CallbackPage).

## Summary
One `applySession(session)` derivation used everywhere; one-shot token-capture guard; profile
fetch only on genuine sign-in; pass the callback's session down instead of re-calling
`getSession`; delete dead surface and fix the small routing/handler inconsistencies.

## Source
- Review findings: **MF1**, **MF2**, **MF3**, **MF5**, **L11**
- Spec reqs: **AUTH-1**, **UI-1** (app shell)
- ADRs: [ADR-0005](../../../decisions/adr/0005-identity.md)

## Scope
### In Scope
- `AuthContext.tsx`: single `applySession` helper; capture guard (compare last-captured refresh
  token); `loadProfile` only when profile is null or on genuine sign-in; use the callback's
  `session.provider_token` (or defer with `setTimeout(0)`) instead of `getSession()` inside the
  listener; remove the unconsumed `refresh` from `AuthValue` (or wire it to `applySession` if a
  consumer is imminent — pick one, say which); `logout` drops the redundant state-setting the
  `SIGNED_OUT` handler already does, and handles the `signOut` error like `login` does.
- `CallbackPage.tsx`: consume `useAuth().status` instead of its own listener+`getSession` race;
  timeout fallback (redirect `/` if neither error nor session arrives); stop listening once an
  error is set so a late session can't clobber it.
- `LoginPage.tsx:28`: drop the dead `status === "loading"` disable (App renders Loading for that
  status); add a local in-flight flag so double-clicks can't fire `signInWithOAuth` twice.
- `main.tsx`: catch-all route (`path="*"` → redirect) so typo'd URLs don't render a blank page.
- `NavBar.tsx:65`: standardize handler convention to `() => void asyncFn()` (matching LoginPage).

### Out of Scope
- `apiFetch` and the capture error-handling (T75 — this builds on it, hence blocked_by).
- Swapping profile identity from client-side Spotify `/me` to a backend `/api/me` — that's a T10+
  design decision (see review "patterns" §; the durable identity should come from FastAPI once
  the real API lands).

## Validation & authz (ADR-0007)
Client-side only; no authz surface changes.

## Current State (on `develop`)
- As described per finding; `refresh` verified unconsumed repo-wide; session derivation
  triplicated across `AuthContext.tsx:61-71`, its listener, and `CallbackPage.tsx:17-23`.

## Files to Create/Modify
| File | Action | Purpose |
|------|--------|---------|
| `apps/web/src/context/AuthContext.tsx` | MODIFY | applySession, guards, listener hygiene |
| `apps/web/src/pages/CallbackPage.tsx` | MODIFY | consume context; timeout; error precedence |
| `apps/web/src/pages/LoginPage.tsx` | MODIFY | real double-click protection |
| `apps/web/src/main.tsx` | MODIFY | catch-all route |
| `apps/web/src/components/NavBar.tsx` | MODIFY | handler convention |

## Testing Checklist
- [ ] fresh login: capture-spotify fires exactly once (network tab; StrictMode dev double-mount)
- [ ] tab refocus / token refresh does not re-POST capture or re-fetch `/me`
- [ ] OAuth error in callback URL shows the error and stays shown
- [ ] direct navigation to `/callback` with no session redirects after the timeout
- [ ] unknown URL redirects instead of blank page; logout works with error handled
- [ ] `npm run build` + `npm run lint` pass

## Readiness Checklist
- [x] Summary is specific and actionable
- [x] Files to Create/Modify is populated
- [x] Testing Checklist has items
- [x] Dependencies identified (075)
- [x] Scope boundaries defined

## Notes
Branch `fix/T76-auth-context-cleanup`. Manual verification against local dev (no frontend test
harness yet); note that in the PR.
