# Brink — Final Presentation Spec

A build-ready specification for the final course presentation. Hand this to a slide tool
(Canva / Gamma / "Claude PowerPoint") to generate the deck, and use it as the run-of-show.

- **Format:** ~15 minutes + a live demo of the deployed app (https://brink-xg7p.onrender.com).
- **Presenters (3):** **Andrea** (backend · API · auth · DB · process/governance),
  **Jonah** (analytics / ML), **Sebastian** (frontend / UX). Sebastian drives the live demo.
- **Slide count:** 17 (title → close). Timings below sum to ~15 min including the demo.
- **Design language (match the product):** near-black background `#0b0b12`, panels `#15151f`,
  primary text `#ededf5`, muted `#8a8aa3`, **lavender accent `#9d8df1`**, **hot-pink `#f472b6`**;
  Inter font, bold negative-tracked headings, rounded cards, one accent gradient
  (lavender→pink). Keep slides sparse — big statement + one visual; details are spoken, not written.

---

## Narrative arc (the story we're telling)

1. **The idea** — social media built on your *real* listening, not what you perform.
2. **How we built it** — the process is a feature: ADRs, tickets, PR discipline, CI that enforces it.
   This is what let a 3-person team ship and defend a real system.
3. **The system** — one Python app (backend + data model + auth) → the ML taste layer → the UI.
4. **See it live** — a demo that ties the three layers together on one screen.
5. **What we learned** — honest reflection: the pivots, the cut model, the disclosed limits.

Recurring thread to name out loud twice: **"we chose things we could own and defend"** — it explains
the stack pivots, the honest disclosures, and the governance.

---

## Run-of-show (timing + who leads)

| # | Slide | Lead | Time |
|---|---|---|---|
| 1 | Title | Andrea | 0:20 |
| 2 | The problem / the idea | Andrea | 1:00 |
| 3 | What Brink is (the 30-second product) | Andrea | 1:00 |
| 4 | How it was built — process is a feature | Andrea | 1:30 |
| 5 | Governance: ADRs, tickets, CI | Andrea | 1:30 |
| 6 | The two pivots | Andrea | 1:00 |
| 7 | Architecture at a glance | Andrea | 1:00 |
| 8 | The data model (tables) | Andrea | 1:00 |
| 9 | Auth & security | Andrea | 0:45 |
| 10 | Analytics: the data engineering (medallion) | Jonah | 1:15 |
| 11 | Analytics: the ML (K-means + inference) | Jonah | 1:30 |
| 12 | Analytics: honesty & the cut model | Jonah | 0:45 |
| 13 | The frontend: one theme, five pages | Sebastian | 1:00 |
| 14 | Frontend: the social details | Sebastian | 0:45 |
| 15 | **Live demo** | Sebastian (Jonah + Andrea narrate) | 2:30 |
| 16 | What we learned | All | 0:45 |
| 17 | Close / thank you | Andrea | 0:15 |

_Total ≈ 15:30. Trim slides 8/14 first if running long; the demo is protected time._

---

## Slide-by-slide

### Slide 1 — Title
- **On slide:** "Brink — Music, but social. 🎶" · the live URL · three names with role tags ·
  McGill MMA. Full-bleed dark background with the lavender→pink gradient.
- **Andrea (0:20):** "We're Brink — a social network built on the music you actually listen to.
  I'm Andrea on the backend, Jonah built our analytics, and Sebastian built the frontend. It's
  live right now at this URL, and we'll demo it at the end."

### Slide 2 — The problem / the idea
- **On slide:** One line: **"Your feed is what you perform. Your listening is who you are."** One
  supporting visual (e.g. a muted "manual post" vs a bright "real play" contrast).
- **Andrea (1:00):** "Social feeds show a curated performance. But your listening history is honest —
  it's who you actually are musically. Brink turns that into the social object: you share the tracks
  you're really playing, your friends react and comment, and underneath, machine learning finds the
  people whose taste genuinely matches yours. Two questions drove the whole build: *what do you
  actually listen to*, and *who else listens like you*."

### Slide 3 — What Brink is (the 30-second product)
- **On slide:** 4 icons/words: **Feed · Taste communities · Compatibility · Artist portal.** A single
  product screenshot behind them if available.
- **Andrea (1:00):** "Concretely, four things. A **feed** of songs that play in place, with reactions
  and comments. A **taste community** for every user — a cluster our model learns. A **compatibility
  score** between any two people. And a lightweight **artist portal**. Everything you'll see is one
  live app, fully built — the full requirement list is delivered and traced. Now the part we're
  proudest of: *how* three people built and defended this."

### Slide 4 — How it was built: process is a feature
- **On slide:** Big number trio: **16 ADRs · 82 tickets · ~320 tests.** Subhead: "A 3-person team,
  built to be owned and defended."
- **Andrea (1:30):** "This is a management program, so process matters as much as code — and we
  treated it as a feature. Three numbers: 16 architecture decision records, 82 completed tickets each
  tied to a requirement, and about 320 automated tests. The guiding principle behind all of it:
  *we only build things we can own and defend.* That one idea explains almost every decision, and
  it's why we made two big pivots you'll see in a moment."

### Slide 5 — Governance: ADRs, tickets, CI
- **On slide:** Three columns — **Decide (ADRs, append-only) → Scope (tickets → requirements) →
  Enforce (CI: tests, secret scan, docs-sync gate).** Small arrow flowing left to right.
- **Andrea (1:30):** "Our workflow has three gates. **Decide:** every architectural choice is a
  written ADR — and they're append-only, so to change our minds we supersede rather than edit, and
  the reasoning never goes stale. **Scope:** every change is one ticket, one pull request, traced to
  a requirement — no scope creep. **Enforce:** CI runs the tests and a secret scan on every PR, plus
  a custom **docs-sync gate** — if you change code but not its docs, the build fails. You literally
  cannot merge stale documentation. That's how the paper trail stayed honest with three people moving
  fast."

### Slide 6 — The two pivots
- **On slide:** Two before→after arrows:
  **TypeScript / Vercel / Prisma → FastAPI / Render (ADR-0010)** and
  **React SPA → server-rendered Jinja pages (ADR-0013).** Caption: "one Python codebase we can all
  read."
- **Andrea (1:00):** "Two pivots, both from the same principle. We started on a TypeScript backend
  and a separate React frontend. But security-critical code — auth, token encryption — in a language
  not everyone on the team could review is a liability for a graded project. So we moved the backend
  to Python/FastAPI, then retired the React app for server-rendered pages. The end state: one Python
  codebase every one of us can read, review, and defend. Both decisions are ADRs with the full
  reasoning."

### Slide 7 — Architecture at a glance
- **On slide:** The README architecture diagram, simplified: Browser → FastAPI (Render) →
  Supabase Postgres/Auth/Storage; a side branch for the analytics cron writing to the gold schema.
- **Andrea (1:00):** "The whole product is one FastAPI app on Render. It serves the JSON API *and*
  the HTML pages, same-origin — no CORS, no separate build. Supabase gives us Postgres, auth, and
  file storage. And a separate Python analytics job runs nightly on GitHub Actions, trains our model,
  and writes results back into the same database, which the app reads on the fly. Simple, cheap,
  entirely on free tiers."

### Slide 8 — The data model
- **On slide:** Grouped table list. **Social (`public`):** User, Post, Reaction, Comment, Follow,
  ArtistPost… **Analytics (medallion):** `silver.Track`, `silver.Play`, `gold.Cluster`,
  `gold.ModelMetrics`, `gold.ModelArtifact`, `bronze.*_raw`.
- **Andrea (1:00):** "About 14 tables. The social side is what you'd expect — users, posts,
  reactions, comments, the follow graph. The interesting part is that the analytics tables live in
  their own **medallion** schemas — bronze, silver, gold — right alongside the social data in one
  Postgres. Jonah will explain why that matters. One nice detail: a user's cluster and compatibility
  aren't *stored* — they're computed on read, so they're never stale."

### Slide 9 — Auth & security
- **On slide:** Three shields: **Server-side JWT validation (no secret held) · Spotify tokens
  AES-256-GCM at rest · Per-user rate limiting + secret-scanning CI.**
- **Andrea (0:45):** "Security was the reason for the Python pivot, so we take it seriously. We
  validate Supabase tokens server-side and never hold a JWT secret. We own long-term Spotify access
  by storing the refresh token **encrypted** with AES-256-GCM. Writes are rate-limited per user, and
  a secret scanner runs on every commit locally and in CI. Over to Jonah for the analytics."

### Slide 10 — Analytics: the data engineering (medallion)
- **On slide:** Three stacked layers — **bronze (raw landings) → silver (conformed: Track, Play) →
  gold (model output: Cluster, Metrics, Artifact).** Note: "all in free Supabase Postgres — no
  lakehouse."
- **Jonah (1:15):** "Our data is organized in a **medallion** architecture — a standard data-
  engineering pattern. **Bronze** is raw, immutable landings: every Spotify 'recently played' pull
  and the raw Kaggle rows. **Silver** is cleaned, conformed data the app actually uses — the tracks
  and the plays. **Gold** is model output — the clusters and the trained model itself. We did this on
  plain free Postgres, no Spark or lakehouse — right-sized for the scale, and it gives us clean,
  legible data lineage we can point to."

### Slide 11 — Analytics: the ML (K-means + on-read inference)
- **On slide:** Two boxes joined by an arrow labeled "ModelArtifact." Left: **Batch — K-means, 7
  taste communities, trained on ~1.2M tracks × 10 audio features.** Right: **On read — build a user's
  taste vector → nearest cluster → cosine compatibility.**
- **Jonah (1:30):** "The ML has two halves. **Offline**, a nightly job trains **K-means** on about
  1.2 million tracks across ten audio features — danceability, energy, valence, and so on — and
  produces seven **taste communities**. It exports a self-describing 'model artifact' — the centroids
  and the scaler — into the gold schema. **Online**, when you load a profile, the app builds that
  user's taste vector from the songs they've played, standardizes it with that same artifact, and
  finds their nearest community. **Compatibility** between two people is just the cosine similarity of
  their taste vectors. Nothing is hardcoded — the app reads whatever the last training run produced."

### Slide 12 — Analytics: honesty & the cut model
- **On slide:** Three honest notes: **Forced k=7 (silhouette preferred k=2) — disclosed ·
  ~24% Kaggle coverage — logged, not hidden · Second (popularity) model CUT — ADR-0016.**
- **Jonah (0:45):** "And we were honest about the limits. The math actually preferred just two
  clusters, but a persona feature needs more, so we forced seven — and we *disclose* that, we didn't
  bury it. We report our real data-coverage numbers. And we originally planned a second model to
  predict song popularity — we **cut it** with a written ADR, because no dataset we had could support
  it honestly, and popularity isn't a stable thing to predict anyway. Cutting it cleanly was the
  right engineering call. Sebastian will show how this surfaces in the product."

### Slide 13 — The frontend: one theme, five pages
- **On slide:** A filmstrip of the five pages (landing, feed, profile, artist, analytics). Caption:
  "Server-rendered · dark, music-native · lavender & pink."
- **Sebastian (1:00):** "The whole frontend is server-rendered pages with a single, consistent
  theme — dark, quiet, music-native, with a lavender-and-pink accent. Five pages: a landing page, the
  feed, profiles, an artist studio, and an analytics page. There's no separate JavaScript app to
  build — the interactivity is lightweight JavaScript talking to the same API, which keeps the whole
  thing simple and fast to load."

### Slide 14 — Frontend: the social details
- **On slide:** Zoom-ins of four touches: **Play-in-place (Spotify embed) · "Liked by X and N others"
  · Double-tap-to-heart · "Share what you're hearing" one-tap.**
- **Sebastian (0:45):** "The details are what make it feel social. Songs **play in place** — tap the
  album art and a Spotify player opens in the card. You get a 'Liked by' line, **double-tap to
  heart** like you'd expect, and a one-tap 'share what you're hearing' that reads your current track
  straight from Spotify. Every empty state has a friendly nudge instead of a blank screen. Let me show
  you the real thing."

### Slide 15 — LIVE DEMO
- **On slide:** Just the URL + "Live demo" (so the projector has something if you tab away).
- **Demo script (Sebastian drives; ~2:30). Have a logged-in account ready and a second profile to
  compare against. Pre-open the tab and warm the Render instance beforehand so there's no cold-start
  wait.**
  1. **Landing → feed (Sebastian):** "Here's the live app." Scroll the feed. Tap album art — "it
     plays right here." React and drop a comment.
  2. **Share (Sebastian):** Open the composer, use "share what you're hearing," post it. "That's a
     real track from my Spotify."
  3. **Profile + taste (Andrea narrates):** Open a profile. "Streak, top tracks — and here's the
     analytics tying in: this person's **taste community**, and because it's not me, a **compatibility
     score**. Both computed live, right now."
  4. **Analytics page (Jonah narrates):** "And here's the model itself — seven taste tribes, how
     distinct they are, and each tribe's audio DNA. These are real numbers from last night's training
     run, not mockups."
  5. **(Optional) Artist studio (Sebastian):** quick look at a behind-the-scenes post.
- **Fallback:** if the live app misbehaves, cut to pre-recorded screenshots on the next slides.
  **Always have screenshots embedded as a backup.**

### Slide 16 — What we learned
- **On slide:** Three takeaways: **Pivot early when you can't defend a choice · Disclose limits,
  don't hide them · Process discipline is what let 3 people ship.**
- **All (0:45) — one line each:**
  - **Andrea:** "The willingness to pivot the stack twice — early, while it was cheap — is what kept
    the project reviewable."
  - **Jonah:** "Being honest about the model's limits made the analytics *more* credible, not less."
  - **Sebastian:** "One codebase and one theme meant we moved fast without stepping on each other."

### Slide 17 — Close
- **On slide:** "Brink — Music, but social. 🎶" · live URL · "Thank you — questions?"
- **Andrea (0:15):** "That's Brink — live, built, and ours to defend. Thank you. Happy to take
  questions."

---

## Anticipated Q&A (prep, not slides)

- **"Why K-means and not something fancier?"** — It's interpretable, cheap, and fits the scale; we
  compared against GMM and it didn't do better. Interpretability mattered for a defensible demo.
- **"Only ~24% of tracks matched the dataset — isn't compatibility meaningless?"** — Yes, at low
  coverage most users share the corpus-mean fallback and score high; we disclose this as a data-
  sparsity artifact, not a bug. More listening data or a bigger feature source fixes it.
- **"Dev and prod share one database — isn't that risky?"** — Correct, and we logged it as an
  accepted risk (T99) deliberately deferred past the deadline rather than pretending it's solved.
- **"Is it really machine learning or just rules?"** — Real unsupervised K-means trained on 1.2M
  tracks; the cluster *labels* are rule-based descriptions of the learned centroids, which we're
  explicit about.
- **"Why retire the React app — isn't that a step back?"** — For a 3-person graded project, being
  able to review every line beat having a fancier SPA nobody but one person could defend.

---

## Build checklist for the deck

- [ ] Generate 17 slides from the sections above in the product's color palette (dark + lavender/pink).
- [ ] Embed screenshots (see `docs/screenshots/` — capture first) on slides 3, 13, 14, and as demo
      fallback after slide 15.
- [ ] Simplify the architecture diagram (slide 7) from the README's ASCII into a clean graphic.
- [ ] Add speaker notes = the scripts above, so each presenter has their lines in the deck.
- [ ] Rehearse the demo once end-to-end with the Render instance pre-warmed.
