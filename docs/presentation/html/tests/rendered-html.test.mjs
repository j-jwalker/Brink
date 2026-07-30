import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import test from "node:test";

async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request("http://localhost/", {
      headers: { accept: "text/html", host: "localhost" },
    }),
    {
      ASSETS: {
        fetch: async () => new Response("Not found", { status: 404 }),
      },
    },
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );
}

test("server-renders the Brink presentation shell and social metadata", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /<title>Brink — Final Project Presentation<\/title>/i);
  assert.match(html, /What we built, how it works, and what we learned\./);
  assert.match(html, /Brink \/ final project/);
  assert.match(html, /Andrea/);
  assert.match(html, /Jonah/);
  assert.match(html, /Sebastian/);
  assert.match(html, /og:image/);
  assert.match(html, /\/og\.png/);
  assert.match(html, /aria-label="Next slide"/);
  assert.doesNotMatch(html, /codex-preview|Your site is taking shape|react-loading-skeleton/);
});

test("keeps presentation controls, notes, and fallbacks in the shipped source", async () => {
  const [page, layout, css, packageJson] = await Promise.all([
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/layout.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/globals.css", import.meta.url), "utf8"),
    readFile(new URL("../package.json", import.meta.url), "utf8"),
  ]);

  assert.match(page, /const TOTAL_SLIDES = slides\.length/);
  assert.match(page, /GitHub Actions keeps the data moving\./);
  assert.match(page, /Spotify returns 50/);
  assert.match(page, /03:00/);
  assert.match(page, /Skills keep sessions repeatable\./);
  assert.match(page, /The project memory stayed intact/);
  assert.match(page, /your own profile also requests a recent-plays refresh on load/);
  assert.match(page, /“Now playing” asks Spotify directly; it is separate from persistent listening history/);
  assert.doesNotMatch(page, /Open technical appendix/);
  assert.match(page, /Speaker notes/);
  assert.match(page, /requestFullscreen/);
  assert.match(page, /trapFocus/);
  assert.match(page, /aria-modal="true"/);
  assert.match(css, /prefers-reduced-motion/);
  assert.match(layout, /generateMetadata/);
  assert.match(layout, /summary_large_image/);
  assert.match(css, /@media \(max-width: 900px\)/);
  assert.doesNotMatch(packageJson, /react-loading-skeleton/);

  await access(new URL("../public/og.png", import.meta.url));
  await access(new URL("../public/screenshots/Feed-brink.png", import.meta.url));
  await assert.rejects(access(new URL("../app/_sites-preview/SkeletonPreview.tsx", import.meta.url)));
});

test("builds a static GitHub Pages presentation with its screenshots", async () => {
  const html = await readFile(new URL("../pages-dist/index.html", import.meta.url), "utf8");

  assert.match(html, /<title>Brink — Final Project Presentation<\/title>/i);
  assert.match(html, /https:\/\/brinkmusic\.github\.io\/Brink\/og\.png/);
  assert.match(html, /\/Brink\/assets\/[^"]+\.js/);

  await access(new URL("../pages-dist/og.png", import.meta.url));
  await access(new URL("../pages-dist/screenshots/Feed-brink.png", import.meta.url));
});
