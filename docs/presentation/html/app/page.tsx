"use client";

/*
THESIS: Brink is a final-project story about ownership: three students used AI heavily, but kept
every decision and technical trade-off understandable. This refuses the startup-pitch deck.
OWN-WORLD: Near-black record sleeve, warm white type, lavender/pink cue lights, thin signal paths,
and a moving playhead. Screenshots and honest system diagrams are the content.
STORY: Why we built it → how AI changed the process → how the system actually works → honest limits
→ live demo → what we learned.
FIRST VIEWPORT: A large BRINK wordmark sits beside a slowly turning record groove; project context
and team roles stay quiet beneath it.
FORM: A speaker-led 16:9 browser deck staged like a record playing from start to finish, with one
continuous timeline, keyboard controls, notes, overview, and technical detail inside the recorded flow.
*/

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

type Slide = {
  id: string;
  title: string;
  kicker: string;
  presenter: string;
  time: string;
  notes: string;
};

const slides: Slide[] = [
  {
    id: "title",
    kicker: "Final project · McGill Desautels MMA",
    title: "Brink",
    presenter: "Andrea",
    time: "0:20",
    notes:
      "Hi everyone. This is Brink, our final project. Brink is a music-native social web app: a dedicated place where listeners can build an identity from what they actually play, and emerging artists can build an audience around their music and creative process. We will explain why we built it, how the system works, and what we learned, then show the live app.",
  },
  {
    id: "idea",
    kicker: "The problem",
    title: "Music is everywhere. Its social experience is scattered.",
    presenter: "Andrea",
    time: "1:00",
    notes:
      "The starting problem was fragmentation. A fan streams on Spotify, sees lifestyle content on Instagram, finds trends on TikTok, and watches videos on YouTube. Each platform does its own job well, but none of them treats music itself as the social experience. The relationship between a listener, an artist, and a song is split across four different places.",
  },
  {
    id: "product",
    kicker: "Who Brink is for",
    title: "Brink gives music its own social space.",
    presenter: "Andrea",
    time: "1:05",
    notes:
      "For listeners, Brink turns Spotify activity into a persistent social identity: what you are playing now, what you have loved, who listens like you, and a feed where music is the reason everyone is there. For emerging artists, Brink creates a place to share a track and the story or creative process behind it. The goal is that they can build an audience through the music without also having to become a lifestyle influencer or master unrelated viral trends.",
  },
  {
    id: "ai",
    kicker: "AI-assisted development",
    title: "We wanted to see how far three people could get with AI coding agents.",
    presenter: "Andrea",
    time: "1:20",
    notes:
      "A second goal was to see how much a team of three could build by leaning heavily on AI coding agents. The lesson came quickly: an agent is only as useful as the context and boundaries we give it. A vague request can still produce convincing code, but it drifts. So a major part of the project was creating enough context, scope, and proof for both the team and the agents to work from.",
  },
  {
    id: "scaffolding",
    kicker: "How we worked",
    title: "The planning was part of the build.",
    presenter: "Andrea",
    time: "1:15",
    notes:
      "We created four layers of scaffolding. ADRs preserve important decisions and why we made them. Tickets keep each piece of work narrow and linked to a requirement. Governance makes every change go through a pull request with tests, secret scanning, review, and matching documentation. We also created project skills that carried the workflow itself: start with the current context, shape and finish one ticket, validate the session, and leave a useful handoff. This structure helped us and it helped the agents continue from the same project memory.",
  },
  {
    id: "decisions",
    kicker: "Why the structure mattered",
    title: "Logged reasoning made major pivots easier—not harder.",
    presenter: "Andrea",
    time: "0:55",
    notes:
      "This became most valuable when we changed direction. We could remember why the original decisions had been made, and the agents could read that history too. The backend moved from TypeScript and Vercel to Python and FastAPI. The frontend moved from a separate React deployment into the same Python application. The technology changed, but the requirements, dependencies, and reasoning stayed available. That made each pivot easier to make without losing the project behind it.",
  },
  {
    id: "architecture",
    kicker: "System view",
    title: "Everything the user touches is one Python app.",
    presenter: "Andrea",
    time: "1:05",
    notes:
      "This is the full system. The browser and Spotify both communicate with one FastAPI service on Render. That service returns the pages, owns the JSON API, checks authentication, and reads or writes Supabase. GitHub Actions is the scheduler around the app: it triggers the Spotify snapshot every thirty minutes, runs the analytics pipeline nightly, and pings the health endpoint every ten minutes. The arrows show who initiates each call and where the result is stored.",
  },
  {
    id: "spotify-flow",
    kicker: "Backend data flow",
    title: "A Spotify play travels through three different jobs.",
    presenter: "Andrea",
    time: "0:55",
    notes:
      "There are three separate jobs here. First, we ask Spotify for a user's recent plays. We save the untouched response in the bronze layer so we can trace what arrived. Then we clean and de-duplicate it into Track and Play rows in silver. Finally, the profile reads those plays for streaks, top tracks, and the taste vector. Keeping ingestion separate from display means a Spotify problem does not have to break the page, and we never lose the original input.",
  },
  {
    id: "automation",
    kicker: "Scheduled automation",
    title: "GitHub Actions keeps the data moving.",
    presenter: "Andrea",
    time: "0:55",
    notes:
      "The scheduled snapshot runs every thirty minutes and gives us a reliable baseline for persistent listening history. Spotify only returns the latest fifty plays, so the tighter cadence reduces the chance of missing overflow. For freshness, your own profile also requests an immediate recent-plays refresh on load; that uses the same deduplicated ingest and appears on the next render. Now playing is a separate live path: Brink asks Spotify directly when your own profile renders or when you use Add what you're hearing. The nightly job refreshes the seven-cluster model at three UTC, and an equally important ten-minute health job keeps the free Render service awake.",
  },
  {
    id: "auth",
    kicker: "Account security",
    title: "We kept the security model simple enough to explain.",
    presenter: "Andrea",
    time: "0:45",
    notes:
      "At presentation level, the important security choices are straightforward. Supabase handles identity, but our server still checks who the user is before every protected action. Spotify tokens are encrypted before we store them. Sensitive credentials stay on the server, and we added rate limits plus automated secret scanning. We will show the exact login boundary later in the technical-detail section.",
  },
  {
    id: "medallion",
    kicker: "Data architecture",
    title: "Raw → usable → model output.",
    presenter: "Jonah",
    time: "1:00",
    notes:
      "We organised the data using a medallion pattern. Bronze holds raw inputs exactly as they arrived. Silver holds cleaned, usable entities like tracks and plays. Gold holds the trained model, its quality metrics, and the seven cluster descriptions. For a project our size, this is more structure than the app strictly needs. The benefit is traceability: we can move from what the model shows all the way back to the data that entered the system.",
  },
  {
    id: "model",
    kicker: "Analytics",
    title: "Training happens at night. Personalisation happens when you open a profile.",
    presenter: "Jonah",
    time: "1:20",
    notes:
      "The model has two parts. At night, the analytics pipeline trains K-means on about 1.2 million songs and ten audio features. It saves the centroids, scaler, feature order, and quality metrics as a self-contained model artifact. When a profile opens, the app builds that person's taste vector from the tracks they played or posted, standardises it using the same saved scaler, and assigns the nearest cluster. Compatibility is cosine similarity between two taste vectors. Those personal results are calculated on read, not saved, so new listening can affect the profile immediately.",
  },
  {
    id: "appendix-inference",
    kicker: "Technical detail · Inference",
    title: "How a profile becomes a point in music space.",
    presenter: "Jonah",
    time: "0:45",
    notes:
      "This is how the trained model reaches a profile. A user's vector averages ten audio features across the tracks they played or posted. We standardise it with the same scaler used in training, then use distance to find the nearest community. Compatibility uses cosine similarity between two taste vectors and is displayed on a zero-to-one-hundred percent scale.",
  },
  {
    id: "limits",
    kicker: "What the numbers do not say",
    title: "We kept the uncomfortable parts in the project.",
    presenter: "Jonah",
    time: "0:55",
    notes:
      "There are three limits we want to be direct about. The silhouette score preferred two clusters, but two communities were not useful for the product, so we deliberately fixed the model at seven and documented that choice. Only around a quarter of real tracks matched the Kaggle feature data, so unmatched songs fall back to the training-corpus mean. That can make compatibility scores look too high. And we cut a planned popularity regression because the available data could not support a defensible target. None of those are hidden.",
  },
  {
    id: "frontend",
    kicker: "Frontend",
    title: "Five pages, one visual language, no second application.",
    presenter: "Sebastian",
    time: "0:55",
    notes:
      "The frontend is server-rendered from the same FastAPI app. Jinja builds the pages and small JavaScript files handle the interactive parts. That gave us one consistent visual language across landing, feed, profile, artist studio, and analytics without maintaining a second application. It also kept the code approachable for the whole team.",
  },
  {
    id: "details",
    kicker: "Product details",
    title: "The small interactions are what made it feel complete.",
    presenter: "Sebastian",
    time: "0:45",
    notes:
      "The small pieces made a big difference. Album art opens a Spotify player inside the card. You can double-tap to like, see who else liked a post, and share what is playing with one action. The profile handles empty or missing analytics without crashing. Artist images use signed links from private storage. These were not headline features, but they are the difference between a feature list and an app that feels coherent.",
  },
  {
    id: "appendix-resilience",
    kicker: "Technical detail · Failure paths",
    title: "Missing data removes an enrichment. It does not remove the page.",
    presenter: "Andrea",
    time: "0:35",
    notes:
      "We also designed optional parts to fail softly. If the model is unavailable, the profile still loads without the taste block. If one private artist image cannot be signed, that image becomes a placeholder rather than breaking the feed. The listening snapshot commits one user at a time, so one Spotify failure does not undo everyone else's data.",
  },
  {
    id: "appendix-screens",
    kicker: "Product walkthrough",
    title: "The complete product, page by page.",
    presenter: "All",
    time: "0:30",
    notes:
      "These are the five connected surfaces in the finished product: landing, feed, profile, artist studio, and analytics. In the recording, this is a quick recap before the live walkthrough, and a clean backup if the live service does not cooperate.",
  },
  {
    id: "demo",
    kicker: "Live demo",
    title: "Let’s show the actual project.",
    presenter: "Sebastian · Andrea · Jonah",
    time: "2:30",
    notes:
      "Sebastian drives. Start on the feed: play a song, react, and add a comment. Share the current Spotify track. Then open another person's profile. Andrea explains the listening summary, taste community, and compatibility being calculated from current data. Finish on analytics with Jonah explaining the seven communities and the real quality metrics. The site should already be open and logged in before this slide.",
  },
  {
    id: "takeaways",
    kicker: "What we learned",
    title: "The technology mattered. The decisions around it mattered more.",
    presenter: "All",
    time: "0:45",
    notes:
      "Andrea: My main takeaway was that AI only moved quickly after we gave it enough context and a tight scope. Jonah: Being honest about the model's limits made our analysis stronger, not weaker. Sebastian: One codebase and one visual system made it possible for three people to keep moving without constantly breaking each other's work.",
  },
  {
    id: "close",
    kicker: "Brink · Final project",
    title: "That’s what we built.",
    presenter: "Andrea",
    time: "0:15",
    notes:
      "That is Brink: a dedicated social space for music, the model behind it, and the process we used to build it. Thanks. We are happy to take questions.",
  },
];

const TOTAL_SLIDES = slides.length;

function Arrow({ direction = "right" }: { direction?: "right" | "down" }) {
  return <span className={`flow-arrow flow-arrow-${direction}`} aria-hidden="true">→</span>;
}

function Node({
  title,
  detail,
  tone = "plain",
}: {
  title: string;
  detail: string;
  tone?: "plain" | "lavender" | "pink";
}) {
  return (
    <div className={`system-node tone-${tone}`}>
      <strong>{title}</strong>
      <span>{detail}</span>
    </div>
  );
}

function SlideContent({ slide }: { slide: Slide }) {
  switch (slide.id) {
    case "title":
      return (
        <div className="title-layout">
          <div className="title-copy">
            <p className="display-label">Brink / final project</p>
            <h1>BRINK</h1>
            <p className="title-subtitle">A dedicated social space for listeners, artists, and the music between them.</p>
            <div className="team-line">
              <span><b>Andrea</b> backend + process</span>
              <span><b>Jonah</b> analytics</span>
              <span><b>Sebastian</b> frontend</span>
            </div>
          </div>
          <div className="record" aria-hidden="true">
            <div className="record-label">
              <span>BRINK</span>
              <small>FINAL<br />PROJECT</small>
            </div>
          </div>
        </div>
      );
    case "idea":
      return (
        <div className="fragment-map">
          <div className="fragment-platforms">
            <section><b>Spotify</b><span>streaming</span></section>
            <section><b>Instagram</b><span>lifestyle</span></section>
            <section><b>TikTok</b><span>entertainment</span></section>
            <section><b>YouTube</b><span>video</span></section>
          </div>
          <p><span>Four strong platforms.</span> No persistent social home where music itself is the relationship.</p>
        </div>
      );
    case "product":
      return (
        <div className="image-split">
          <div className="screen-frame feed-frame">
            <img src="screenshots/Feed-brink.png" alt="Brink social feed with song posts, reactions, and comments" />
          </div>
          <div className="feature-list">
            <p><b>For listeners</b><span>What you play becomes a lasting identity, a social feed, and a way to find people with similar taste.</span></p>
            <p><b>For emerging artists</b><span>Share the music and creative process without first becoming a lifestyle influencer.</span></p>
            <p><b>One music-native hub</b><span>Listening, discovery, fan connection, and artist stories live together.</span></p>
          </div>
        </div>
      );
    case "ai":
      return (
        <div className="ai-composition">
          <p className="huge-quote">“AI is only as useful as the context and boundaries we give it.”</p>
          <div className="context-track">
            <span>Vague prompt</span>
            <i />
            <strong>Reasoning + scope + proof</strong>
          </div>
          <p className="quiet-note">The first weeks were planning, not code.</p>
        </div>
      );
    case "scaffolding":
      return (
        <div className="scaffold-grid">
          <section><span className="artifact-mark">ADR</span><h3>Decisions keep their reasoning.</h3><p>New choices supersede old ones without erasing why we started there.</p></section>
          <section><span className="artifact-mark">TKT</span><h3>Tickets keep the work narrow.</h3><p>One requirement-linked outcome with a visible definition of done.</p></section>
          <section><span className="artifact-mark">PR</span><h3>Governance keeps claims testable.</h3><p>Tests, secret scans, review, and matching documentation on every change.</p></section>
          <section><span className="artifact-mark">SKL</span><h3>Skills keep sessions repeatable.</h3><p>Start with context, finish one ticket, validate the work, and leave a useful handoff.</p></section>
        </div>
      );
    case "decisions":
      return (
        <div className="pivot-layout">
          <p className="pivot-caption">The decision changed. The project memory stayed intact—for us and for the agents.</p>
          <div className="pivot-row"><span>Backend</span><s>TypeScript · Vercel</s><Arrow /><b>Python · FastAPI · Render</b></div>
          <div className="pivot-row"><span>Frontend</span><s>React · separate deploy</s><Arrow /><b>Jinja pages · same server</b></div>
        </div>
      );
    case "architecture":
      return (
        <div className="architecture">
          <div className="arch-core">
            <Node title="Your browser" detail="Pages · light JavaScript" />
            <div className="arch-connector"><b>→</b><span>requests · pages return</span></div>
            <div className="app-boundary">
              <div className="boundary-title"><b>FastAPI app</b><span>Render · one service</span></div>
              <div className="boundary-parts">
                <span>Jinja pages</span><span>JSON API</span><span>Auth</span><span>Inference</span>
              </div>
            </div>
            <div className="arch-connector"><b>→</b><span>API calls · music data returns</span></div>
            <Node title="Spotify" detail="Login · catalogue · listening" tone="pink" />
          </div>
          <div className="arch-support">
            <div className="data-store">
              <span className="store-origin">FastAPI</span>
              <div className="arch-connector"><b>→</b><span>SQLModel + Auth calls · rows return</span></div>
              <Node title="Supabase" detail="Postgres · Auth · Storage" tone="lavender" />
            </div>
            <div className="jobs-panel">
              <div className="jobs-heading"><strong>GitHub Actions</strong><span>scheduled jobs</span></div>
              <div><b>30 min</b><span>Spotify snapshot</span><em>→ FastAPI</em></div>
              <div><b>03:00 UTC</b><span>Analytics pipeline</span><em>→ Supabase gold</em></div>
              <div><b>10 min</b><span>Health ping</span><em>→ FastAPI</em></div>
            </div>
          </div>
          <p className="diagram-caption">Each arrow points from caller to destination; response data returns over the same connection.</p>
        </div>
      );
    case "spotify-flow":
      return (
        <div className="pipeline">
          <div className="pipeline-step">
            <span className="step-tag">1 · FETCH</span>
            <h3>Spotify recently played</h3>
            <p>Server refreshes the user’s token, then requests their latest plays.</p>
          </div>
          <Arrow />
          <div className="pipeline-step bronze">
            <span className="step-tag">2 · BRONZE</span>
            <h3>Keep the raw response</h3>
            <p>An append-only copy lets us trace exactly what arrived.</p>
          </div>
          <Arrow />
          <div className="pipeline-step silver">
            <span className="step-tag">3 · SILVER</span>
            <h3>Upsert tracks + dedupe plays</h3>
            <p>Clean rows become the app’s listening history.</p>
          </div>
          <Arrow />
          <div className="pipeline-step gold">
            <span className="step-tag">4 · READ</span>
            <h3>Profile + taste vector</h3>
            <p>Stats and inference use the latest stored history.</p>
          </div>
        </div>
      );
    case "auth":
      return (
        <div className="security-principles">
          <section><span>01</span><h3>Check identity on the server</h3><p>Supabase handles login; every protected action still verifies the user.</p></section>
          <section><span>02</span><h3>Encrypt what we must keep</h3><p>Spotify tokens are encrypted before they reach the database.</p></section>
          <section><span>03</span><h3>Keep secrets out of the browser</h3><p>Server-only credentials, rate limits, and secret scanning reduce avoidable risk.</p></section>
        </div>
      );
    case "automation":
      return (
        <div className="automation-board">
          <div className="automation-job snapshot-job">
            <div className="job-clock"><strong>30</strong><span>minutes</span></div>
            <div className="job-copy">
              <span>SPOTIFY SNAPSHOT</span>
              <h3>Reduce gaps in persistent history</h3>
              <p>GitHub Actions → Render → Spotify recent plays → bronze raw data → silver Track + Play rows.</p>
            </div>
            <div className="job-result"><b>Spotify returns 50</b><span>latest plays only; your own profile also requests a recent-plays refresh on load.</span></div>
          </div>
          <div className="automation-job analytics-job">
            <div className="job-clock"><strong>03:00</strong><span>UTC nightly</span></div>
            <div className="job-copy">
              <span>ANALYTICS PIPELINE</span>
              <h3>Refresh the shared music model</h3>
              <p>Download ~1.2M track features → join + clean → train seven clusters → write gold output to Supabase.</p>
            </div>
            <div className="job-result"><b>Also manual</b><span>Both workflows can be run on demand.</span></div>
          </div>
          <div className="automation-job keepalive-job">
            <div className="job-clock"><strong>10</strong><span>minutes</span></div>
            <div className="job-copy">
              <span>RENDER KEEPALIVE</span>
              <h3>Keep the app ready for a visitor</h3>
              <p>A lightweight GitHub Actions job pings the public health endpoint before the free service can sleep.</p>
            </div>
            <div className="job-result"><b>Live state stays live</b><span>“Now playing” asks Spotify directly; it is separate from persistent listening history.</span></div>
          </div>
        </div>
      );
    case "medallion":
      return (
        <div className="medallion">
          <div className="medal bronze"><span>BRONZE</span><h3>What arrived</h3><p>Raw Spotify pulls<br />Raw dataset rows</p></div>
          <div className="medal silver"><span>SILVER</span><h3>What the app uses</h3><p>Tracks with audio features<br />De-duplicated plays</p></div>
          <div className="medal gold"><span>GOLD</span><h3>What the model produced</h3><p>Clusters · metrics<br />Self-describing model artifact</p></div>
          <p className="trace-line">Traceable in one direction. Rebuildable in the other.</p>
        </div>
      );
    case "model":
      return (
        <div className="model-layout">
          <div className="model-steps">
            <section><span>NIGHTLY</span><h3>Train once</h3><p>~1.2M songs · 10 audio features · K-means</p><small>Writes centroids + scaler + metrics to gold</small></section>
            <div className="model-divider"><Arrow direction="down" /></div>
            <section><span>ON PROFILE LOAD</span><h3>Apply the saved model</h3><p>Current plays + posts → taste vector → nearest community</p><small>Two vectors → cosine similarity → compatibility</small></section>
          </div>
          <div className="screen-frame analytics-frame">
            <img src="screenshots/analytics-brink.png" alt="Brink analytics page showing seven taste communities and model quality" />
          </div>
        </div>
      );
    case "appendix-inference":
      return (
        <div className="inference-map">
          <div className="feature-cloud">
            {["danceability", "energy", "valence", "tempo", "acousticness", "instrumentalness", "liveness", "speechiness", "loudness", "duration"].map((item) => <span key={item}>{item}</span>)}
          </div>
          <Arrow />
          <div className="vector-block"><span>USER A</span><b>average taste vector</b><small>fallback = corpus mean when a track has no feature match</small></div>
          <div className="math-branch">
            <div><b>Euclidean distance</b><span>nearest standardised centroid</span><strong>Taste community</strong></div>
            <div><b>Cosine similarity</b><span>compare A with user B</span><strong>Compatibility</strong></div>
          </div>
        </div>
      );
    case "limits":
      return (
        <div className="limits-list">
          <div><strong>2 → 7</strong><p>The cleanest mathematical split was two. We chose seven because communities needed useful variety.</p></div>
          <div><strong>~24%</strong><p>Only about a quarter of live tracks matched the feature dataset. The fallback can inflate similarity.</p></div>
          <div><strong>CUT</strong><p>We removed popularity regression when the data could not support a defensible target.</p></div>
        </div>
      );
    case "frontend":
      return (
        <div className="frontend-collage">
          <div className="collage-main screen-frame"><img src="screenshots/Landing-brink.png" alt="Brink landing page" /></div>
          <div className="page-index">
            <span>Landing</span><span>Feed</span><span>Profile</span><span>Artist studio</span><span>Analytics</span>
          </div>
          <div className="frontend-code"><b>Same FastAPI server</b><span>Jinja templates</span><span>Plain CSS</span><span>Small JavaScript modules</span></div>
        </div>
      );
    case "details":
      return (
        <div className="detail-layout">
          <div className="screen-frame profile-frame"><img src="screenshots/Profile-brink.png" alt="Brink profile with listening history and compatibility" /></div>
          <div className="detail-copy">
            <p><b>Play in place</b><span>Spotify player opens inside a feed card.</span></p>
            <p><b>Share what is playing</b><span>One action fills the existing composer.</span></p>
            <p><b>Fail soft</b><span>Missing analytics hides one block, not the whole profile.</span></p>
            <p><b>Private media</b><span>Artist images are read through short-lived signed links.</span></p>
          </div>
        </div>
      );
    case "demo":
      return (
        <div className="demo-layout">
          <ol>
            <li><span>01</span><b>Feed</b><small>play · react · comment</small></li>
            <li><span>02</span><b>Share</b><small>post what is playing now</small></li>
            <li><span>03</span><b>Profile</b><small>history · community · compatibility</small></li>
            <li><span>04</span><b>Analytics</b><small>seven communities · real metrics</small></li>
          </ol>
          <a className="demo-link" href="https://brink-xg7p.onrender.com" target="_blank" rel="noreferrer">Open the live app <span>↗</span></a>
        </div>
      );
    case "takeaways":
      return (
        <div className="takeaway-lines">
          <p><span>Andrea</span>AI moved quickly only after we made the context and scope precise.</p>
          <p><span>Jonah</span>Being honest about the model’s limits made the analysis stronger.</p>
          <p><span>Sebastian</span>One codebase and one visual system kept three people moving together.</p>
        </div>
      );
    case "close":
      return (
        <div className="close-layout">
          <div className="mini-record" aria-hidden="true"><i /></div>
          <div><p className="display-label">Brink · final project</p><h2>That’s what<br />we built.</h2><p>Questions?</p></div>
        </div>
      );
    case "appendix-resilience":
      return (
        <div className="resilience-grid">
          <section><span>MODEL ABSENT</span><b>Cluster block disappears.</b><p>The profile still returns normally.</p></section>
          <section><span>IMAGE SIGNING FAILS</span><b>One image becomes a placeholder.</b><p>The feed continues to load.</p></section>
          <section><span>ONE SPOTIFY USER FAILS</span><b>That user is skipped.</b><p>Other users’ snapshots stay committed.</p></section>
          <section><span>REQUIRED SECRET MISSING</span><b>The app refuses to boot.</b><p>Misconfiguration is visible immediately.</p></section>
        </div>
      );
    case "appendix-screens":
      return <ScreenshotBackup />;
    default:
      return null;
  }
}

function ScreenshotBackup() {
  const items = useMemo(() => [
    ["Landing", "screenshots/Landing-brink.png"],
    ["Feed", "screenshots/Feed-brink.png"],
    ["Profile", "screenshots/Profile-brink.png"],
    ["Artist studio", "screenshots/artist-brink.png"],
    ["Analytics", "screenshots/analytics-brink.png"],
  ], []);
  const [active, setActive] = useState(0);
  return (
    <div className="backup-layout">
      <div className="backup-tabs" role="tablist" aria-label="Backup screenshots">
        {items.map(([name], index) => (
          <button key={name} role="tab" aria-selected={active === index} onClick={() => setActive(index)}>{name}</button>
        ))}
      </div>
      <div className="screen-frame backup-frame">
        <img src={items[active][1]} alt={`${items[active][0]} page of Brink`} />
      </div>
    </div>
  );
}

export default function Home() {
  const [index, setIndex] = useState(0);
  const [notesOpen, setNotesOpen] = useState(false);
  const [overviewOpen, setOverviewOpen] = useState(false);
  const overviewRef = useRef<HTMLDivElement>(null);

  const slide = slides[index];
  const displayNumber = `${index + 1} / ${TOTAL_SLIDES}`;

  const go = useCallback((delta: number) => {
    setIndex((current) => Math.max(0, Math.min(TOTAL_SLIDES - 1, current + delta)));
  }, []);

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.key === "ArrowRight" || event.key === "PageDown" || event.key === " ") {
        if ((event.target as HTMLElement)?.tagName !== "BUTTON") {
          event.preventDefault();
          go(1);
        }
      } else if (event.key === "ArrowLeft" || event.key === "PageUp") {
        event.preventDefault();
        go(-1);
      } else if (event.key === "Home") {
        setIndex(0);
      } else if (event.key === "End") {
        setIndex(TOTAL_SLIDES - 1);
      } else if (event.key.toLowerCase() === "n") {
        setNotesOpen((open) => !open);
      } else if (event.key.toLowerCase() === "o") {
        setOverviewOpen((open) => !open);
      } else if (event.key.toLowerCase() === "f") {
        if (!document.fullscreenElement) document.documentElement.requestFullscreen?.();
        else document.exitFullscreen?.();
      } else if (event.key === "Escape") {
        setOverviewOpen(false);
        setNotesOpen(false);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [go]);

  useEffect(() => {
    if (!overviewOpen || !overviewRef.current) return;

    const dialog = overviewRef.current;
    const previouslyFocused = document.activeElement as HTMLElement | null;
    const focusable = Array.from(dialog.querySelectorAll<HTMLElement>("button, a[href], [tabindex]:not([tabindex='-1'])"));
    focusable[0]?.focus();

    const trapFocus = (event: KeyboardEvent) => {
      if (event.key !== "Tab" || focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    dialog.addEventListener("keydown", trapFocus);
    return () => {
      dialog.removeEventListener("keydown", trapFocus);
      previouslyFocused?.focus();
    };
  }, [overviewOpen]);

  return (
    <main className="deck">
      <div className="ambient-record" aria-hidden="true" />
      <header className="deck-header">
        <button className="wordmark" onClick={() => setIndex(0)} aria-label="Go to first slide">BRINK<span>●</span></button>
        <div className="track-progress" aria-label={`Slide ${displayNumber}`}>
          <span style={{ transform: `scaleX(${(index + 1) / TOTAL_SLIDES})` }} />
          <i style={{ left: `${(index / (TOTAL_SLIDES - 1)) * 100}%` }} />
        </div>
      </header>

      <section className="slide-shell" aria-live="polite">
        <div className="slide-meta">
          <span>{slide.kicker}</span>
        </div>
        <div className={`slide-content slide-${slide.id}`}>
          {slide.id !== "title" && slide.id !== "close" && <h2 className="slide-title">{slide.title}</h2>}
          <SlideContent slide={slide} />
        </div>
      </section>

      <footer className="deck-footer">
        <div className="utility">
          <button onClick={() => setOverviewOpen(true)}><kbd>O</kbd> Overview</button>
          <button onClick={() => setNotesOpen((open) => !open)} aria-pressed={notesOpen}><kbd>N</kbd> Notes</button>
          <button onClick={() => document.documentElement.requestFullscreen?.()}><kbd>F</kbd> Fullscreen</button>
        </div>
        <div className="navigation">
          <button onClick={() => go(-1)} disabled={index === 0} aria-label="Previous slide">←</button>
          <span>{displayNumber}</span>
          <button onClick={() => go(1)} disabled={index === TOTAL_SLIDES - 1} aria-label="Next slide">→</button>
        </div>
      </footer>

      {notesOpen && (
        <aside className="notes-panel" aria-label="Speaker notes">
          <div><span>Speaker notes · {slide.presenter}</span><button onClick={() => setNotesOpen(false)} aria-label="Close speaker notes">×</button></div>
          <p>{slide.notes}</p>
        </aside>
      )}

      {overviewOpen && (
        <div ref={overviewRef} className="overview" role="dialog" aria-modal="true" aria-labelledby="overview-title">
          <div className="overview-header"><div><span>BRINK</span><p id="overview-title">Choose a slide</p></div><button onClick={() => setOverviewOpen(false)}>Close ×</button></div>
          <div className="overview-grid">
            {slides.map((item, itemIndex) => (
              <button
                key={item.id}
                className={itemIndex === index ? "active" : ""}
                onClick={() => { setIndex(itemIndex); setOverviewOpen(false); }}
              >
                <span>{String(itemIndex + 1).padStart(2, "0")} · {item.kicker}</span>
                <b>{item.title}</b>
              </button>
            ))}
          </div>
        </div>
      )}
    </main>
  );
}
