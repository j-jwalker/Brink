# Out-of-scope tickets

Tickets we have decided **not to build**. They are kept (not deleted) so the reasoning stays on the
record — each file's body explains why. This is distinct from [`backlog/`](../backlog/) (planned,
not yet done) and [`completed/`](../completed/) (done).

**Not out of scope:** deferred-but-planned work stays in `backlog/` — e.g. `T99` (split the shared
dev/prod database) is deliberately pushed past the 2026-07-30 deadline but is still intended.

| Ticket | Why it's out of scope |
|--------|-----------------------|
| `036-popularity-regression` | **Cut** ([ADR-0016](../../../decisions/adr/0016-cut-second-regression-model.md)): no Kaggle dataset supports a defensible popularity regression (no popularity column in the ~1.2M-track training corpus; the one file that has it is frozen at April 2019; the real `brink-dev` overlap is 67 rows), and popularity is a live, constantly-recomputed metric — not a stable regression target. Satisfies-nothing; `AN-6` is marked Cut. |
| `075-token-capture-reliability` | **Obsolete**: every file it targeted lived in the `apps/web/` React SPA, retired in T60 ([ADR-0013](../../../decisions/adr/0013-python-frontend.md)). Token capture is now server-side in `/auth/callback` (T09); the browser capture path this ticket hardened no longer exists. |
| `076-auth-context-cleanup` | **Obsolete**: `AuthContext.tsx`/`CallbackPage.tsx`/`LoginPage.tsx`/`NavBar.tsx` were all deleted with the SPA in T60 (ADR-0013). Login is server-side (T09) with no browser auth listener at all. |
