"""
WHAT THIS FILE IS
-----------------
Generates the Brink final-presentation PowerPoint (brink-deck.pptx) from the
run-of-show in presentation-spec.md. Run it to (re)build the deck:

    python docs/presentation/build_deck.py

Every slide carries its speaker script in the PowerPoint "notes" pane, so each
presenter has their lines. Styling matches the product's palette (dark canvas,
lavender + hot-pink accents). Edit the SLIDES list below and re-run to change it.
"""

from pathlib import Path

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

# Brand palette (from backend/app/static/brink.css :root)
INK = RGBColor(0x0B, 0x0B, 0x12)      # page background
PANEL = RGBColor(0x15, 0x15, 0x1F)    # card background
LINE = RGBColor(0x26, 0x26, 0x3A)     # borders
MUTE = RGBColor(0x8A, 0x8A, 0xA3)     # secondary text
TEXT = RGBColor(0xED, 0xED, 0xF5)     # primary text
ACCENT = RGBColor(0x9D, 0x8D, 0xF1)   # lavender
HOT = RGBColor(0xF4, 0x72, 0xB6)      # hot pink

FONT = "Inter"  # PowerPoint gracefully substitutes if Inter isn't installed

EMU_W, EMU_H = Inches(13.333), Inches(7.5)  # 16:9


def _set_bg(slide, color=INK):
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = color


def _box(slide, left, top, width, height):
    tb = slide.shapes.add_textbox(left, top, width, height)
    tf = tb.text_frame
    tf.word_wrap = True
    return tb, tf


def _style(run, size, color=TEXT, bold=False, italic=False, font=FONT):
    run.font.size = Pt(size)
    run.font.color.rgb = color
    run.font.bold = bold
    run.font.italic = italic
    run.font.name = font


def _rule(slide, left, top, width, color=ACCENT, height=Pt(3)):
    from pptx.enum.shapes import MSO_SHAPE
    shp = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)
    shp.fill.solid()
    shp.fill.fore_color.rgb = color
    shp.line.fill.background()
    shp.shadow.inherit = False
    return shp


def _notes(slide, text):
    slide.notes_slide.notes_text_frame.text = text


def add_content(prs, kicker, title, bullets, notes, accent_title=True):
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank
    _set_bg(slide)
    # kicker (top small label: presenter + time)
    _, ktf = _box(slide, Inches(0.7), Inches(0.5), Inches(11.9), Inches(0.4))
    kr = ktf.paragraphs[0].add_run()
    kr.text = kicker
    _style(kr, 13, MUTE, bold=True)
    ktf.paragraphs[0].runs[0].font.name = FONT
    # title
    _, ttf = _box(slide, Inches(0.7), Inches(0.95), Inches(11.9), Inches(1.3))
    tr = ttf.paragraphs[0].add_run()
    tr.text = title
    _style(tr, 34, ACCENT if accent_title else TEXT, bold=True)
    _rule(slide, Inches(0.72), Inches(2.15), Inches(1.6))
    # bullets
    _, btf = _box(slide, Inches(0.7), Inches(2.55), Inches(11.9), Inches(4.4))
    for i, b in enumerate(bullets):
        p = btf.paragraphs[0] if i == 0 else btf.add_paragraph()
        p.space_after = Pt(12)
        lead = b.startswith("**")
        txt = b.replace("**", "")
        run = p.add_run()
        run.text = ("•  " if not lead else "") + txt
        _style(run, 20, TEXT if not lead else HOT, bold=lead)
    _notes(slide, notes)
    return slide


def add_bignum(prs, kicker, title, stats, subtitle, notes):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _set_bg(slide)
    _, ktf = _box(slide, Inches(0.7), Inches(0.5), Inches(11.9), Inches(0.4))
    kr = ktf.paragraphs[0].add_run(); kr.text = kicker; _style(kr, 13, MUTE, bold=True)
    _, ttf = _box(slide, Inches(0.7), Inches(0.95), Inches(11.9), Inches(1.0))
    tr = ttf.paragraphs[0].add_run(); tr.text = title; _style(tr, 30, TEXT, bold=True)
    # three big stats
    col_w = Inches(3.9)
    for i, (num, label) in enumerate(stats):
        left = Inches(0.7) + i * Inches(4.0)
        _, ntf = _box(slide, left, Inches(2.6), col_w, Inches(1.6))
        ntf.paragraphs[0].alignment = PP_ALIGN.CENTER
        nr = ntf.paragraphs[0].add_run(); nr.text = num
        _style(nr, 60, ACCENT if i % 2 == 0 else HOT, bold=True)
        _, ltf = _box(slide, left, Inches(4.2), col_w, Inches(1.0))
        ltf.paragraphs[0].alignment = PP_ALIGN.CENTER
        lr = ltf.paragraphs[0].add_run(); lr.text = label
        _style(lr, 18, MUTE)
    _, stf = _box(slide, Inches(0.7), Inches(5.7), Inches(11.9), Inches(1.0))
    stf.paragraphs[0].alignment = PP_ALIGN.CENTER
    sr = stf.paragraphs[0].add_run(); sr.text = subtitle; _style(sr, 20, TEXT, italic=True)
    _notes(slide, notes)
    return slide


def add_image(prs, img_path, caption, notes):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _set_bg(slide)
    # caption strip at top
    _, ctf = _box(slide, Inches(0.7), Inches(0.35), Inches(11.9), Inches(0.6))
    cr = ctf.paragraphs[0].add_run(); cr.text = caption; _style(cr, 18, ACCENT, bold=True)
    # image scaled to fit under the caption, centered
    from PIL import Image  # optional; fall back to fixed width if unavailable
    max_w, max_h = Inches(11.9), Inches(5.9)
    try:
        with Image.open(img_path) as im:
            iw, ih = im.size
        ratio = min(max_w / iw, max_h / ih)
        w, h = Emu(int(iw * ratio)), Emu(int(ih * ratio))
    except Exception:
        w, h = max_w, None
    left = Emu(int((prs.slide_width - (w if isinstance(w, Emu) else max_w)) / 2))
    slide.shapes.add_picture(str(img_path), left, Inches(1.1), width=w, height=h)
    _notes(slide, notes)
    return slide


def add_title(prs, title, subtitle, footer, notes):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _set_bg(slide)
    _rule(slide, Inches(0.9), Inches(2.55), Inches(2.4), HOT, Pt(5))
    _, ttf = _box(slide, Inches(0.9), Inches(2.7), Inches(11.5), Inches(1.6))
    tr = ttf.paragraphs[0].add_run(); tr.text = title; _style(tr, 52, TEXT, bold=True)
    _, stf = _box(slide, Inches(0.9), Inches(4.15), Inches(11.5), Inches(1.0))
    sr = stf.paragraphs[0].add_run(); sr.text = subtitle; _style(sr, 24, ACCENT, bold=True)
    _, ftf = _box(slide, Inches(0.9), Inches(5.2), Inches(11.5), Inches(1.4))
    for i, line in enumerate(footer):
        p = ftf.paragraphs[0] if i == 0 else ftf.add_paragraph()
        r = p.add_run(); r.text = line; _style(r, 16, MUTE)
    _notes(slide, notes)
    return slide


def build():
    prs = Presentation()
    prs.slide_width, prs.slide_height = EMU_W, EMU_H

    # 1 — Title
    add_title(
        prs,
        "Brink — Music, but social. 🎶",
        "A social network built on your real listening.",
        ["brink-xg7p.onrender.com",
         "Andrea Vreugdenhil (backend) · Jonah Walker (analytics) · Sebastian Arguedas Soley (frontend)",
         "McGill Desautels — MMA"],
        "ANDREA (0:20): We're Brink — a social network built on the music you actually listen to. "
        "I'm Andrea on the backend, Jonah built our analytics, and Sebastian built the frontend. "
        "It's live right now at this URL, and we'll demo it at the end.",
    )

    # 2 — Problem / idea
    add_content(
        prs, "ANDREA · 1:00", "Your feed is what you perform.\nYour listening is who you are.",
        ["Social feeds show a curated performance.",
         "Your listening history is honest — it's who you actually are musically.",
         "Brink makes that the social object: share what you're really playing; friends react.",
         "**Two questions drive everything: what do you listen to, and who listens like you?"],
        "ANDREA (1:00): Social feeds show a curated performance. But your listening history is honest — "
        "it's who you actually are musically. Brink turns that into the social object: you share the "
        "tracks you're really playing, your friends react and comment, and underneath, machine learning "
        "finds the people whose taste genuinely matches yours. Two questions drove the whole build: what "
        "do you actually listen to, and who else listens like you.",
    )

    # 3 — What Brink is
    add_content(
        prs, "ANDREA · 1:00", "What Brink is",
        ["**Feed  —  songs that play in place, with reactions & comments",
         "**Taste communities  —  a cluster our model learns for every user",
         "**Compatibility  —  a score between any two people",
         "**Artist portal  —  behind-the-scenes posts to fans",
         "One live app, fully built — the full requirement list is delivered and traced."],
        "ANDREA (1:00): Concretely, four things. A feed of songs that play in place, with reactions and "
        "comments. A taste community for every user — a cluster our model learns. A compatibility score "
        "between any two people. And a lightweight artist portal. Everything you'll see is one live app, "
        "fully built. Now the part we're proudest of: HOW three people built and defended this.",
    )

    # 4 — Process is a feature (big numbers)
    add_bignum(
        prs, "ANDREA · 1:30", "How it was built: process is a feature",
        [("16", "Architecture\nDecision Records"), ("82", "tickets, each\ntied to a requirement"),
         ("~320", "automated\ntests")],
        "A 3-person team, built to be owned and defended.",
        "ANDREA (1:30): This is a management program, so process matters as much as code — and we treated "
        "it as a feature. Three numbers: 16 architecture decision records, 82 completed tickets each tied "
        "to a requirement, and about 320 automated tests. The guiding principle behind all of it: we only "
        "build things we can own and defend. That one idea explains almost every decision, and it's why "
        "we made two big pivots you'll see in a moment.",
    )

    # 5 — Governance
    add_content(
        prs, "ANDREA · 1:30", "Decide → Scope → Enforce",
        ["**Decide  —  every choice is an append-only ADR; we supersede, never edit",
         "**Scope  —  one ticket = one PR, traced to a requirement; no scope creep",
         "**Enforce  —  CI runs tests + a secret scan on every PR",
         "**+ a custom docs-sync gate: change code but not its docs and the build fails",
         "You literally cannot merge stale documentation."],
        "ANDREA (1:30): Our workflow has three gates. Decide: every architectural choice is a written ADR — "
        "append-only, so to change our minds we supersede rather than edit, and the reasoning never goes "
        "stale. Scope: every change is one ticket, one pull request, traced to a requirement — no scope "
        "creep. Enforce: CI runs the tests and a secret scan on every PR, plus a custom docs-sync gate — "
        "if you change code but not its docs, the build fails. You cannot merge stale documentation. "
        "That's how the paper trail stayed honest with three people moving fast.",
    )

    # 6 — The two pivots
    add_content(
        prs, "ANDREA · 1:00", "Two pivots, one principle",
        ["TypeScript / Vercel / Prisma  →  FastAPI / Render   (ADR-0010)",
         "React / Vite SPA  →  server-rendered Jinja pages   (ADR-0013)",
         "**Why: security-critical code in a language not all of us could review is a liability",
         "End state: one Python codebase every one of us can read, review, and defend."],
        "ANDREA (1:00): Two pivots, both from the same principle. We started on a TypeScript backend and a "
        "separate React frontend. But security-critical code — auth, token encryption — in a language not "
        "everyone could review is a liability for a graded project. So we moved the backend to "
        "Python/FastAPI, then retired the React app for server-rendered pages. The end state: one Python "
        "codebase every one of us can read, review, and defend. Both decisions are ADRs.",
    )

    # 7 — Architecture
    add_content(
        prs, "ANDREA · 1:00", "Architecture at a glance",
        ["One FastAPI app on Render serves the JSON API AND the HTML pages — same-origin, no CORS",
         "Supabase provides Postgres, Auth, and Storage",
         "We own long-term Spotify access via an encrypted stored refresh token",
         "A nightly Python analytics job trains the model and writes results the app reads live",
         "Simple, cheap, entirely on free tiers."],
        "ANDREA (1:00): The whole product is one FastAPI app on Render. It serves the JSON API and the "
        "HTML pages, same-origin — no CORS, no separate build. Supabase gives us Postgres, auth, and file "
        "storage. And a separate Python analytics job runs nightly on GitHub Actions, trains our model, "
        "and writes results back into the same database, which the app reads on the fly. Simple, cheap, "
        "entirely on free tiers.",
    )

    # 8 — Data model
    add_content(
        prs, "ANDREA · 1:00", "The data model  (~14 tables)",
        ["**Social (public):  User · Post · Reaction · Comment · Follow · ArtistPost",
         "**Analytics (medallion):  silver.Track · silver.Play · gold.Cluster · gold.ModelArtifact · bronze.*_raw",
         "A user's cluster & compatibility aren't stored — they're computed on read, so never stale."],
        "ANDREA (1:00): About 14 tables. The social side is what you'd expect — users, posts, reactions, "
        "comments, the follow graph. The interesting part is that the analytics tables live in their own "
        "medallion schemas — bronze, silver, gold — right alongside the social data in one Postgres. Jonah "
        "will explain why. One nice detail: a user's cluster and compatibility aren't stored — they're "
        "computed on read, so they're never stale.",
    )

    # 9 — Auth & security
    add_content(
        prs, "ANDREA · 0:45", "Auth & security",
        ["**Server-side JWT validation — we never hold a JWT secret",
         "**Spotify tokens encrypted at rest — AES-256-GCM",
         "**Per-user rate limiting + secret-scanning in CI and pre-commit",
         "Security was the reason for the Python pivot — so we take it seriously."],
        "ANDREA (0:45): Security was the reason for the Python pivot, so we take it seriously. We validate "
        "Supabase tokens server-side and never hold a JWT secret. We own long-term Spotify access by "
        "storing the refresh token encrypted with AES-256-GCM. Writes are rate-limited per user, and a "
        "secret scanner runs on every commit locally and in CI. Over to Jonah for the analytics.",
    )

    # 10 — Analytics: medallion
    add_content(
        prs, "JONAH · 1:15", "The data engineering: a medallion",
        ["**Bronze  —  raw, immutable landings (Spotify pulls, raw Kaggle rows)",
         "**Silver  —  cleaned, conformed data the app uses (Track, Play)",
         "**Gold  —  model output (clusters, metrics, the trained model itself)",
         "All on free Postgres — no Spark, no lakehouse. Right-sized, with legible lineage."],
        "JONAH (1:15): Our data is organized in a medallion architecture — a standard data-engineering "
        "pattern. Bronze is raw, immutable landings: every Spotify 'recently played' pull and the raw "
        "Kaggle rows. Silver is cleaned, conformed data the app actually uses — the tracks and the plays. "
        "Gold is model output — the clusters and the trained model. We did this on plain free Postgres, no "
        "Spark or lakehouse — right-sized for the scale, and it gives us clean lineage we can point to.",
    )

    # 11 — Analytics: the ML
    add_content(
        prs, "JONAH · 1:30", "The ML: K-means + on-read inference",
        ["**Offline:  K-means on ~1.2M tracks × 10 audio features → 7 taste communities",
         "It exports a self-describing model artifact (centroids + scaler) into gold",
         "**On read:  build a user's taste vector → nearest community → cosine compatibility",
         "Nothing is hardcoded — the app reads whatever the last training run produced."],
        "JONAH (1:30): The ML has two halves. Offline, a nightly job trains K-means on about 1.2 million "
        "tracks across ten audio features — danceability, energy, valence, and so on — and produces seven "
        "taste communities. It exports a self-describing model artifact — the centroids and the scaler — "
        "into gold. Online, when you load a profile, the app builds that user's taste vector from the songs "
        "they've played, standardizes it with that same artifact, and finds their nearest community. "
        "Compatibility between two people is just the cosine similarity of their taste vectors. Nothing is "
        "hardcoded — the app reads whatever the last training run produced.",
    )

    # 12 — Analytics: honesty
    add_content(
        prs, "JONAH · 0:45", "Honesty about the limits",
        ["**Forced k=7  —  the math preferred k=2; a persona feature needs more, so we disclose it",
         "**~24% dataset coverage  —  logged, not hidden",
         "**Second model (popularity) CUT  —  ADR-0016: no dataset supported it honestly",
         "Cutting it cleanly was the right engineering call."],
        "JONAH (0:45): And we were honest about the limits. The math actually preferred just two clusters, "
        "but a persona feature needs more, so we forced seven — and we disclose that, we didn't bury it. We "
        "report our real data-coverage numbers. And we originally planned a second model to predict song "
        "popularity — we cut it with a written ADR, because no dataset we had could support it honestly, "
        "and popularity isn't a stable thing to predict anyway. Cutting it cleanly was the right call. "
        "Sebastian will show how this surfaces in the product.",
    )

    # 13 — Frontend: theme + pages
    add_content(
        prs, "SEBASTIAN · 1:00", "One theme, five pages",
        ["Server-rendered pages — no separate JS app to build; lightweight JS calls the same API",
         "Dark, quiet, music-native — a lavender & hot-pink accent throughout",
         "**Landing · Feed · Profile · Artist studio · Analytics",
         "Fast to load, consistent, and simple for a small team to maintain."],
        "SEBASTIAN (1:00): The whole frontend is server-rendered pages with a single, consistent theme — "
        "dark, quiet, music-native, with a lavender-and-pink accent. Five pages: a landing page, the feed, "
        "profiles, an artist studio, and an analytics page. There's no separate JavaScript app to build — "
        "the interactivity is lightweight JavaScript talking to the same API, which keeps the whole thing "
        "simple and fast to load.",
    )

    # 14 — Frontend: social details
    add_content(
        prs, "SEBASTIAN · 0:45", "The social details",
        ["**Play-in-place  —  tap album art, a Spotify player opens in the card",
         "**Liked by X and N others  ·  double-tap-to-heart",
         "**One-tap 'share what you're hearing'  —  reads your current track from Spotify",
         "Every empty state has a friendly nudge, not a blank screen."],
        "SEBASTIAN (0:45): The details are what make it feel social. Songs play in place — tap the album "
        "art and a Spotify player opens in the card. You get a 'Liked by' line, double-tap to heart like "
        "you'd expect, and a one-tap 'share what you're hearing' that reads your current track straight "
        "from Spotify. Every empty state has a friendly nudge instead of a blank screen. Let me show you "
        "the real thing.",
    )

    # 15 — Live demo
    demo = add_content(
        prs, "SEBASTIAN drives · Jonah + Andrea narrate · 2:30", "Live demo",
        ["brink-xg7p.onrender.com",
         "1.  Feed — scroll, tap art to play in place, react + comment",
         "2.  Share — 'share what you're hearing', post a real track",
         "3.  Profile — taste community + % compatible (Andrea narrates)",
         "4.  Analytics — 7 tribes, distinctness, audio DNA (Jonah narrates)",
         "5.  (Optional) Artist studio — a behind-the-scenes post",
         "**Warm the Render instance first. Screenshots on next slides are the fallback."],
        "SEBASTIAN drives (~2:30). Pre-warm the Render instance so there's no cold-start wait. "
        "1) Landing -> feed: 'here's the live app', scroll, tap album art ('it plays right here'), react "
        "and comment. 2) Share: open the composer, use 'share what you're hearing', post it. "
        "3) Profile (Andrea narrates): open another user's profile — streak, top tracks, the taste "
        "community, and because it's not me, a compatibility score — both computed live. "
        "4) Analytics (Jonah narrates): seven taste tribes, how distinct they are, each tribe's audio DNA — "
        "real numbers from last night's training run. 5) Optional: artist studio. "
        "FALLBACK: if the live app misbehaves, cut to the screenshots on the next slides.",
    )

    # Fallback screenshots (used live if the demo misbehaves; also nice static reference)
    shots = Path(__file__).parent.parent / "screenshots"
    for img, cap in [
        ("Landing-brink.png", "Landing — sign in; your listening becomes the feed"),
        ("Feed-brink.png", "Feed — songs play in place, with reactions & comments"),
        ("Profile-brink.png", "Profile — taste community + % compatible"),
        ("artist-brink.png", "Artist studio — behind-the-scenes posts"),
        ("analytics-brink.png", "Analytics — real model output: tribes & audio DNA"),
    ]:
        p = shots / img
        if p.exists():
            add_image(prs, p, cap, "Demo fallback / static reference: " + cap)

    # 16 — What we learned
    add_content(
        prs, "ALL · 0:45", "What we learned",
        ["**Pivot early when you can't defend a choice  (Andrea)",
         "**Disclose limits, don't hide them — it made the analytics more credible  (Jonah)",
         "**One codebase + one theme let 3 people move fast without collisions  (Sebastian)"],
        "ALL (0:45), one line each. ANDREA: the willingness to pivot the stack twice — early, while it was "
        "cheap — is what kept the project reviewable. JONAH: being honest about the model's limits made "
        "the analytics more credible, not less. SEBASTIAN: one codebase and one theme meant we moved fast "
        "without stepping on each other.",
    )

    # 17 — Close
    add_title(
        prs,
        "Brink — Music, but social. 🎶",
        "Thank you — questions?",
        ["brink-xg7p.onrender.com"],
        "ANDREA (0:15): That's Brink — live, built, and ours to defend. Thank you. Happy to take questions.",
    )

    out = Path(__file__).with_name("brink-deck.pptx")
    prs.save(out)
    print(f"Wrote {out}  ({len(prs.slides.__iter__.__self__._sldIdLst)} slides)")


if __name__ == "__main__":
    build()
