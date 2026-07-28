# Final deliverable — repo cleanup checklist

Scope chosen: **Moderate.** Remove dead artifacts and fix presentation-facing wording, but
**keep** the ADRs, review write-ups, ticket history, and honest risk disclosures — those
demonstrate engineering rigor and a course grader rewards them.

Live app: **https://brink-xg7p.onrender.com**

## Do

- [ ] **Remove the last trace of the retired SPA.** `apps/web/tsconfig.tsbuildinfo` is the only
      tracked file under `apps/` and contradicts the "SPA retired in T60" story.
      ```bash
      git rm apps/web/tsconfig.tsbuildinfo
      ```
      Then delete the untracked leftovers on disk (safe — none are tracked):
      `apps/web/dist/`, `apps/web/node_modules/`, `apps/web/.env`. Removing the whole `apps/`
      tree is fine.

- [x] **Fix the README status line.** Was "in active development" → now "feature-complete for the
      course scope," with the live URL front and centre. (Done in this pass — see `README.md`.)

- [ ] **If submitting as a zip/folder rather than a git clone, strip `.remember/`.** It is
      git-ignored (so it will NOT appear in a `git clone` or GitHub view) but it sits on disk and
      contains internal session logs, hours notes, and progress-report residue. In a clone-based
      submission: nothing to do. In a zip: delete `.remember/` before zipping.
      Also consider stripping (all git-ignored, clone-safe, zip-only concern): `.tdd/`,
      `node_modules/`, `knowledge/`, `.claude/`, `.codex/`.

- [ ] **Add screenshots.** No screenshots exist under `docs/` yet. Capture 4–5 of the deployed app
      (landing, feed, a profile with the Taste card, artist studio, analytics/"Wrapped" page) into
      `docs/screenshots/` and wire them into the README "Pages" section + the presentation.

## Keep (deliberately — these are strengths to showcase, not clutter)

- **`docs/decisions/adr/` (16 ADRs)** — the decision paper trail, including the two stack pivots.
- **`docs/plans/` (82 completed tickets, requirements traceability)** — proof of disciplined scope.
- **`docs/plans/reviews/`** — internal audit/incident write-ups; they demonstrate rigor.
- **The shared dev/prod DB disclosure** (`T99`, in `CLAUDE.md`/`requirements.md`) — it is an
      honestly-logged accepted risk. Moderate scope keeps it; only "Aggressive" would soften it.
- **`.agents/` skill library (129 files)** — internal AI tooling; harmless, part of the "how we
      worked" story. Moderate scope keeps it; only "Aggressive" would strip it.

## Verify (already clean — no action)

- **Secrets:** `.env` is git-ignored and untracked; a grep of all tracked files found zero real
      secret values (only variable *names* and `render.yaml` keys with `sync: false`). Repo has a
      pre-commit secret guard + a gitleaks CI job. Nothing to fix.
- No `TODO`/`FIXME`/`HACK` comments in `backend/app/` or `analytics/`; no profanity in source.

## Note / decide

- `load/k6-script.js` hardcodes the production host `https://brink-xg7p.onrender.com`. That's a
  public URL, not a secret — fine to leave, and it doubles as documentation of the live app.
- **Doc accuracy nit worth a one-line fix:** `CLAUDE.md`/ADR-0013 describe the frontend as
  "Jinja2 + HTMX," but there is **no HTMX** in the templates — interactivity is vanilla JS
  (`fetch`) against `/api/*`. Not deliverable-blocking, but if you want the docs airtight before a
  grader reads them, soften "HTMX" to "progressive-enhancement JavaScript" (HTMX stays as a stated
  future direction). Left as-is for now.
