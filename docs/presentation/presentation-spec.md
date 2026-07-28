# Brink — Final Presentation Spec

Source content for the final course presentation. Two ways to use it:
- **Gamma (or similar):** paste this file in — each "Slide N" heading becomes a slide; the bullets are
  on-slide content and the *Speaker notes* are the spoken script.
- **Run-of-show:** the table and scripts below are the rehearsal guide.

A generated PowerPoint version lives alongside this file at `brink-deck.pptx` (rebuild it with
`python build_deck.py`).

---

## For the slide generator (style guide)

- **Tone:** human, plain, honest — like three students explaining what they actually built. **Not** a
  sales pitch. Short lines on screen; the detail is spoken.
- **Format:** ~15 minutes, 3 presenters (**Andrea** = backend + process, **Jonah** = analytics,
  **Sebastian** = frontend), ending in a **live demo** of the deployed app
  (https://brink-xg7p.onrender.com). ~17 slides.
- **Look:** dark background (near-black `#0b0b12`), off-white text (`#ededf5`), a **lavender accent
  `#9d8df1`** and a **hot-pink accent `#f472b6`**, Inter font, rounded cards. Music-native, calm,
  "quietly premium."
- **Visuals:** favor images and simple diagrams over bullet walls. Screenshots of the app live in
  `docs/screenshots/` (landing, feed, profile, artist, analytics). Slide 7 is a real labeled
  architecture diagram, not a bullet list.
- **The thread:** everything ties back to one idea — *we built things we could actually own and
  defend, and we leaned on AI by giving it strong context and clear scope.*

---

## Run-of-show

| # | Slide | Lead | Time | Visual |
|---|---|---|---|---|
| 1 | Title | Andrea | 0:20 | Gradient title |
| 2 | The idea | Andrea | 1:00 | — |
| 3 | What Brink is | Andrea | 1:00 | Feed screenshot |
| 4 | What we really set out to do (AI) | Andrea | 1:30 | — |
| 5 | The scaffolding that let AI build | Andrea | 1:30 | 3 cards |
| 6 | Two times we changed our minds | Andrea | 1:00 | — |
| 7 | How it fits together | Andrea | 1:00 | **Architecture diagram** |
| 8 | The data behind it | Andrea | 0:50 | — |
| 9 | Keeping accounts safe | Andrea | 0:45 | — |
| 10 | How the data is organised | Jonah | 1:15 | — |
| 11 | The model, in two parts | Jonah | 1:30 | Analytics screenshot |
| 12 | Being honest about the limits | Jonah | 0:45 | — |
| 13 | One look, five pages | Sebastian | 1:00 | Landing screenshot |
| 14 | The small touches | Sebastian | 0:45 | Profile screenshot |
| 15 | **Live demo** | Sebastian (+ Jonah, Andrea) | 2:30 | The live app |
| 16 | What we took away | All | 0:45 | — |
| 17 | Close | Andrea | 0:15 | Gradient title |

_≈ 15:30 including the demo. If running long, trim slides 8 and 14 first; protect the demo._

---

## Slides

### Slide 1 — Title
- **On slide:** "Brink — Music, but social. 🎶" · "A social app built on what you actually listen to." ·
  the live URL · three names with role tags · McGill Desautels — MMA.
- **Speaker notes (Andrea, 0:20):** "Hi everyone — this is Brink. It's a social app built around the
  music you actually listen to on Spotify. I worked on the backend, Jonah did the analytics, and
  Sebastian did the frontend. It's deployed and running, so we'll show you the real thing at the end."

### Slide 2 — The idea
- **On slide:**
  - On most apps, what you post is the highlight reel — a version of yourself.
  - What you listen to is more honest: it's just what you played.
  - So we built the feed on that — and used it to find who listens like you.
- **Speaker notes (Andrea, 1:00):** "The starting point was simple. On most social apps, what you post
  is a choice — you show the version of yourself you want people to see. Your listening history is
  different: it's just what you actually played. We thought that was a more honest thing to build a
  feed around. So on Brink you share the songs you're really listening to, people react and comment,
  and then we use that listening data to figure out whose taste actually lines up with yours."

### Slide 3 — What Brink is
- **Visual:** feed screenshot (`docs/screenshots/Feed-brink.png`) beside the text.
- **On slide:**
  - **Feed** — songs that play right in the card, with reactions & comments
  - **Taste communities** — a group our model puts you in
  - **Compatibility** — how close two people's taste is
  - **Artist portal** — behind-the-scenes posts to fans
  - It's all one live app — everything we planned is built.
- **Speaker notes (Andrea, 1:00):** "Concretely, Brink is four things. A feed of songs that play right
  there in the card, with reactions and comments. A taste community for each person — a group our
  model puts you in. A compatibility score between any two people. And a small artist portal. It's all
  one live app, and everything we set out to build is built. But the part we actually want to talk
  about is *how* three of us built it."

### Slide 4 — What we really set out to do
- **On slide:**
  - A big goal was to see how far we could get by leaning on AI coding agents.
  - We learned fast: **AI is only as good as the context you give it.**
  - So the job was two things — give the agents rich context, and be exact about what to build.
  - Our first couple of weeks were planning, not code: **ADRs, tickets, and project governance.**
- **Speaker notes (Andrea, 1:30):** "Honestly, one of our real goals on this project was to see how
  far we could get by leaning on AI coding agents — to build as much as we possibly could as a team of
  three. And what we learned early is that AI is only as good as the context you give it. If you're
  vague, you get vague. So the whole job became two things: give the agents as much context as
  possible, and be really precise about exactly what we wanted built. That's why our first couple of
  weeks weren't spent writing app code at all — we were setting up what we call our ADRs, our tickets,
  and our project governance. That planning is what made everything afterwards move fast."

### Slide 5 — The scaffolding that let AI build
- **Visual:** three cards side by side.
  - **ADRs** — Every real decision, written down with the reasoning. So an agent or a teammate knows
    *why* things are the way they are. Append-only: we supersede, never quietly edit.
  - **Tickets** — One clear piece of work at a time. The agent builds exactly that — nothing more.
    Each one traces back to a requirement.
  - **Governance** — Guardrails around every change: one PR at a time. Tests + a secret scan run
    automatically. A check fails if you change code but not its docs.
- **Speaker notes (Andrea, 1:30):** "So what does that scaffolding actually look like. ADRs are
  architecture decision records — every real decision written down with the reasoning behind it, so
  anyone picking up the work, an agent or one of us, knows why things are the way they are. Tickets
  break the work into one clear piece at a time, so the agent builds exactly that and nothing else.
  And governance is the guardrails — every change is a pull request, tests and a secret-scanner run
  automatically, and we even have a check that fails if you change code without updating its docs. All
  of that is context and clarity — which is exactly what the agents needed to be useful."

### Slide 6 — Two times we changed our minds
- **On slide:**
  - Backend: TypeScript / Vercel → Python / FastAPI (ADR-0010)
  - Frontend: React app → simpler server-rendered pages (ADR-0013)
  - **Why both times:** the security-sensitive parts were in a stack we couldn't all read.
  - Now it's one Python codebase all three of us can actually read and defend.
- **Speaker notes (Andrea, 1:00):** "There were two moments where we changed our minds, and they're
  worth sharing because the reasoning was the same both times. We started the backend in TypeScript and
  the frontend as a separate React app. But the security-sensitive parts — logins, encrypting people's
  tokens — were in a stack not all three of us could confidently read. For a graded project, that's a
  real risk. So we moved the backend to Python, and later replaced the React app with simpler
  server-rendered pages. Now it's one Python codebase all of us can read and defend. Both of those are
  written up as ADRs, so you can see the reasoning."

### Slide 7 — How it fits together  (architecture diagram)
- **Visual — a labeled diagram, not bullets:**
  - Top: **Your browser** (web pages + light JS) and **Spotify** (logins · listening · catalog).
  - Center: one container box **"FastAPI app · Render"** holding four components — **Web pages
    (Jinja)**, **JSON API**, **Auth (JWT · AES-256)**, **Inference (on read)**.
  - Bottom: **Supabase** (Postgres with public + bronze/silver/gold, Auth, Storage) and the
    **Analytics pipeline** (GitHub Actions, nightly — trains K-means → writes gold).
  - Arrows: browser →(HTTPS, same-origin)→ app; Spotify ↔(OAuth · now playing)↔ app; app →(SQLModel
    ORM)→ Supabase; Analytics →(writes gold)→ Postgres.
  - Caption: "One app is everything the user touches. A nightly job trains the model on the side; the
    app just reads the results."
- **Speaker notes (Andrea, 1:00):** "Here's how it all fits together. Everything the user touches is
  one app — a FastAPI service on Render that serves both the web pages and the API, so there's no
  separate frontend to deploy. It talks to Supabase for the database, logins, and file storage. Off to
  the side, a Python job runs every night on GitHub Actions, trains our model, and writes the results
  into the database — and the app just reads those results when someone loads a page. And Spotify is
  where the logins and the listening data come from."

### Slide 8 — The data behind it  (~14 tables)
- **On slide:**
  - **Social:** users, posts, reactions, comments, the follow graph.
  - **Music & model:** tracks, plays, and the taste communities the model produces.
  - A person's community and compatibility aren't stored — we work them out on the spot, so they're
    never stale.
- **Speaker notes (Andrea, 0:50):** "Behind it is about 14 tables. The social side is what you'd
  expect — users, posts, reactions, comments, who follows whom. The music side holds the tracks,
  everyone's plays, and the taste communities the model produces. One thing we're a little proud of: a
  person's community and their compatibility with you aren't saved anywhere — we work them out on the
  spot when you load the page, so they're never out of date."

### Slide 9 — Keeping accounts safe
- **On slide:**
  - We check every login on our server — we never hold a master key.
  - Spotify tokens are encrypted before they're stored (AES-256-GCM).
  - Limits on how fast anyone can post, and a secret-scanner on every commit.
  - Security was the reason we moved to Python — so we took it seriously.
- **Speaker notes (Andrea, 0:45):** "On security — we validate every login on our own server and never
  hold a master secret. The tokens we keep for Spotify are encrypted before they ever touch the
  database. There are limits on how fast anyone can post, and a scanner runs on every single commit to
  make sure we never accidentally check in a password or key. Security was the reason we moved to
  Python in the first place, so we didn't cut corners here. I'll hand over to Jonah for the analytics."

### Slide 10 — How the data is organised
- **On slide:**
  - **Raw** — everything exactly as it arrives (Spotify pulls, dataset rows).
  - **Cleaned** — tidied into the tables the app actually uses.
  - **Model output** — the communities and the trained model itself.
  - A standard "medallion" pattern — a bit more structure than we strictly needed, but everything
    stays traceable.
- **Speaker notes (Jonah, 1:15):** "The data side is organised in three layers — people call it a
  medallion. The first layer is raw: everything exactly as it arrives, the Spotify listening pulls and
  the raw dataset rows. The second is that data cleaned up into the tables the app actually uses. And
  the third is the output of our model — the communities and the model itself. It's a common
  data-engineering pattern, and honestly at our scale it's a little more structure than we strictly
  needed — but it keeps everything traceable, and it's the right way to do it."

### Slide 11 — The model, in two parts
- **Visual:** analytics screenshot (`docs/screenshots/analytics-brink.png`) beside the text.
- **On slide:**
  - **Once a night:** we cluster ~1.2M songs by their sound (danceable, energetic, upbeat…) into 7
    taste communities.
  - **When you open a profile:** we place that person's songs against the communities and find where
    they fit.
  - Compatibility = how close two people's taste profiles are.
  - Nothing's hard-coded — retrain tonight, the app updates tomorrow.
- **Speaker notes (Jonah, 1:30):** "The model is in two parts. Once a night, we train a clustering
  model on about 1.2 million songs, using audio features like how danceable or energetic or upbeat a
  track is — that sorts songs into seven taste communities. Then, when you actually open someone's
  profile, we take the songs they've played, place them against those communities, and find where they
  fit. Compatibility between two people is just how close their two taste profiles are. And nothing is
  hard-coded — if we retrain the model tonight, the app picks up the new version tomorrow. This page is
  that model's output, live."

### Slide 12 — Being honest about the limits
- **On slide:**
  - The math actually liked just 2 groups — we chose 7 on purpose, and we say so.
  - Only ~a quarter of songs matched our dataset — we report that, we don't hide it.
  - We planned a second model (song popularity) and cut it — the data couldn't support it. We wrote
    down why.
- **Speaker notes (Jonah, 0:45):** "We also want to be upfront about the limits, because we think that
  matters. The math actually suggested only two groups was cleanest — but two isn't very interesting as
  'communities,' so we chose seven on purpose, and we say that openly. Only about a quarter of songs
  matched our dataset, and we report that honestly rather than hiding it. And we'd planned a second
  model to predict song popularity, but the data just couldn't support it honestly, so we cut it — and
  wrote down why. We'd rather show you the real picture than a polished one. Sebastian will show where
  all this shows up in the app."

### Slide 13 — One look, five pages
- **Visual:** landing screenshot (`docs/screenshots/Landing-brink.png`) beside the text.
- **On slide:**
  - Dark, calm, music-first — a lavender & pink accent throughout.
  - **Landing · Feed · Profile · Artist studio · Analytics**
  - No separate app to build — the pages come from the same server, with light JavaScript for the
    interactive bits.
  - That kept it fast, and simple for a small team to maintain.
- **Speaker notes (Sebastian, 1:00):** "The whole frontend has one consistent look — dark, calm,
  music-first, with a lavender-and-pink accent. There are five pages: the landing page, the feed,
  profiles, an artist studio, and the analytics page. There's no separate app to build — the pages come
  straight from the same server, with just a bit of JavaScript for the interactive parts. That kept
  everything fast to load and simple for a small team to keep up with."

### Slide 14 — The small touches
- **Visual:** profile screenshot (`docs/screenshots/Profile-brink.png`) beside the text.
- **On slide:**
  - Tap the album art — a Spotify player opens right in the card.
  - A "liked by" line, and double-tap to heart, like you'd expect.
  - One tap to share whatever you're playing right now.
  - Every empty screen has a friendly nudge, not a blank space.
- **Speaker notes (Sebastian, 0:45):** "The small touches are what make it feel like a real social app.
  Tap the album art and a Spotify player opens right there in the card. There's a 'liked by' line, and
  you can double-tap to heart a song like you'd expect. There's a one-tap button to share whatever
  you're playing right now. And every empty screen — no posts yet, nothing playing — has a friendly
  nudge instead of a blank space. Let me just show you the real thing."

### Slide 15 — Live demo
- **On slide:** the live URL + "Let's look at the real thing" + the 4 demo steps.
- **Demo script (Sebastian drives; ~2:30). Pre-warm the site so there's no cold-start wait. Have a
  logged-in account with real data and a second profile to compare against.**
  1. **Feed (Sebastian):** "This is the live app." Scroll; tap album art so a song plays in the card;
     react and drop a comment.
  2. **Share (Sebastian):** use the one-tap "share what you're playing" and post it.
  3. **Profile (Andrea narrates):** open someone else's profile — their streak, top tracks, their taste
     community, and since it's not me, a compatibility score — all worked out live.
  4. **Analytics (Jonah narrates):** the seven communities, how distinct they are, each one's audio
     DNA — real numbers from last night's run.
- **Fallback:** if anything breaks, switch to the screenshots (they're the following slides / an
  appendix in the deck). Always have them on hand.

### Slide 16 — What we took away
- **On slide (one line each):**
  - The AI was only as good as the context and structure we gave it. — Andrea
  - Being honest about the model's limits made it more convincing, not less. — Jonah
  - One codebase and one look let three people move without stepping on each other. — Sebastian
- **Speaker notes (all, 0:45):** each presenter says their own line. "The biggest lesson for me was
  that the AI was only ever as good as the context and structure we gave it — the planning up front was
  the whole game." / "Being honest about the model's limits made it more convincing, not less." /
  "Keeping it to one codebase and one consistent look is what let three of us move fast without
  stepping on each other."

### Slide 17 — Close
- **On slide:** "Brink — Music, but social. 🎶" · "Thanks — happy to take questions." · the live URL.
- **Speaker notes (Andrea, 0:15):** "That's Brink — live, and built by the three of us. Thanks for
  listening — we're happy to take any questions."

---

## Appendix — screenshot slides (demo fallback)

The generated `.pptx` includes five full-bleed screenshot slides right after the demo, as a backup if
the live app misbehaves: landing, feed, profile, artist studio, analytics. In Gamma, add these as an
appendix from `docs/screenshots/` if you want the same safety net.

## Anticipated Q&A (prep, not slides)

- **"Why K-means and not something fancier?"** — It's interpretable, cheap, and fits our scale; we
  compared it against another method and it didn't do better. Being able to explain it mattered.
- **"Only ~a quarter of songs matched — isn't compatibility meaningless?"** — At low coverage a lot of
  people share the same fallback and score high; we call that out as a data-sparsity artifact, not a
  bug. More listening data or a bigger song dataset fixes it.
- **"Dev and prod share one database — isn't that risky?"** — Yes, and we logged it as an accepted risk
  we deliberately chose not to fix before the deadline, rather than pretending it's solved.
- **"Is it really machine learning or just rules?"** — It's real unsupervised clustering on 1.2M
  songs; only the community *names* are simple rule-based descriptions of what each group sounds like,
  and we're clear about that.
- **"Why retire the React app — isn't that a step back?"** — For three people on a graded project,
  being able to read and defend every line beat a fancier app only one of us could maintain.
