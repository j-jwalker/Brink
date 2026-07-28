# Out-of-scope tickets

Tickets we have decided **not to build within the project's scope**. They are kept (not deleted) so
the reasoning stays on the record — each file's body explains why. This is distinct from
[`completed/`](../completed/) (done). With `T14` complete, the `backlog/` is empty, so these are the
only planned-but-unbuilt tickets left.

| Ticket | Why it's out of scope |
|--------|-----------------------|
| `036-popularity-regression` | **Cut** ([ADR-0016](../../../decisions/adr/0016-cut-second-regression-model.md)): no Kaggle dataset supports a defensible popularity regression (no popularity column in the ~1.2M-track training corpus; the one file that has it is frozen at April 2019; the real `brink-dev` overlap is 67 rows), and popularity is a live, constantly-recomputed metric — not a stable regression target. Satisfies-nothing; `AN-6` is marked Cut. |
| `075-token-capture-reliability` | **Obsolete**: every file it targeted lived in the `apps/web/` React SPA, retired in T60 ([ADR-0013](../../../decisions/adr/0013-python-frontend.md)). Token capture is now server-side in `/auth/callback` (T09); the browser capture path this ticket hardened no longer exists. |
| `076-auth-context-cleanup` | **Obsolete**: `AuthContext.tsx`/`CallbackPage.tsx`/`LoginPage.tsx`/`NavBar.tsx` were all deleted with the SPA in T60 (ADR-0013). Login is server-side (T09) with no browser auth listener at all. |
| `099-split-dev-prod-databases` | **Deferred out of scope**: production and local dev share the one `brink-dev` Supabase project. Splitting them is deliberately pushed **past the 2026-07-30 deadline** — the shared DB is a known, accepted risk for the course project (see CLAUDE.md Watch-outs), not something we'll build in-scope. The ticket stays here so the decision and the future work are on the record. |
