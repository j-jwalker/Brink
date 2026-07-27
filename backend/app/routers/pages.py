# WHAT THIS FILE IS
# Serves Brink's actual web PAGES — the HTML a person sees in their browser — as
# opposed to the JSON API in the other routers (health, auth, posts). WHY this
# exists: per ADR-0013 we build the frontend in Python. Instead of a separate
# React/TypeScript app, FastAPI fills in HTML templates (in app/templates/) and
# sends whole pages to the browser. One language, one codebase.
#
# Pages so far:
#   GET /      -> the public landing page (what a visitor sees before signing in)
#   GET /feed  -> the feed page. Reuses the shared build_feed() (app/routers/feed.py) so it
#                 shows the SAME posts as GET /api/feed (people you follow + your own), each
#                 with live reaction counts. Login-gated (T09); the reaction buttons call the
#                 T11 reactions API from the browser (T41).

import logging
from datetime import datetime, timezone
from typing import Optional
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlmodel import Session, select

from app import spotify
from app.db import get_session
from app.deps import AuthError, require_user
from app.models import (
    ArtistComment,
    ArtistPost,
    ArtistReaction,
    Cluster,
    Follow,
    ModelMetrics,
    Post,
    ReactionType,
    Track,
    User,
)
from app.routers.artist import UPLOAD_BUCKET
from app.routers.feed import build_feed
from app.routers.users import FOLLOW_LIST_LIMIT
from app.security.supabase import create_signed_read_url_or_blank
from app.stats import listening_summary

logger = logging.getLogger(__name__)

# Where the HTML templates live (backend/app/templates/). We build the path relative
# to THIS file (parent.parent = app/), so it works no matter which folder the server
# was started from.
_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

# Jinja2 is the templating tool: it takes an .html file with placeholders and fills
# them in with values we pass. `templates` is the thing we call to render a page.
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

# A router groups related routes; app/main.py plugs it into the app.
router = APIRouter()


# Figure out who (if anyone) is logged in, WITHOUT forcing a login. The gated pages call
# require_user, which redirects anonymous visitors to Spotify — but the landing page ("/") is
# public, so it must still render for a signed-out visitor. This helper reuses the SAME session
# check (require_user) but swallows the "not logged in" error and returns None instead, so the
# nav (T47) can show the logged-in links to a signed-in user who lands on "/" and the public nav
# to everyone else. It never raises: any auth problem just means "treat as logged out".
def _optional_viewer(request: Request, session: Session) -> User | None:
    try:
        # A scratch Response absorbs any refreshed-session cookie require_user might set; the
        # landing page doesn't need to persist it (the next gated page will), so we discard it.
        return require_user(request, session=session, response=Response())
    except Exception:  # noqa: BLE001 — an unauthenticated / undecodable session is simply "logged out"
        return None


# When someone opens the site root ("/") in a browser, run this and return a web page.
# response_class=HTMLResponse tells FastAPI "this returns HTML, not JSON".
@router.get("/", response_class=HTMLResponse)
def home(request: Request, session: Session = Depends(get_session)):
    # Render templates/home.html. Jinja2Templates needs the incoming `request`, and
    # we hand it a small dictionary of values the template can drop in (here, the
    # browser-tab title). The template itself decides where each value goes.
    # `viewer` lets the shared nav (base.html, T47) show the in-app links to a signed-in
    # visitor while staying public for everyone else.
    return templates.TemplateResponse(
        request,
        "home.html",
        {"page_title": "Brink", "viewer": _optional_viewer(request, session)},
    )


# Turn a timestamp into a friendly "3m ago" style label for the feed. WHY here (not
# in the template): Jinja has no built-in "time ago", so we compute the words in
# Python and pass a ready-to-show string.
# Turn an ArtistPost's stored image path into what the template needs (T104), TRI-STATE:
#   - None  -> the post is TEXT-ONLY (no photo) → the template renders a note card.
#   - ""    -> the post HAS a photo but signing it failed (T103) → the template shows a placeholder.
#   - a URL -> a valid signed read URL → the template shows the image.
# Centralised so the profile page and the artist page sign the same way.
def _artist_image_url(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    return create_signed_read_url_or_blank(UPLOAD_BUCKET, path)


def _ago(when: datetime) -> str:
    now = datetime.now(timezone.utc)
    # Posts are stored in UTC; if the value has no timezone attached, treat it as UTC
    # so the subtraction below doesn't error on mixing naive/aware datetimes.
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    minutes = int((now - when).total_seconds() // 60)
    if minutes < 1:
        return "just now"
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    return f"{hours // 24}d ago"


# Build the list of feed items for the template. We REUSE the shared feed builder
# (app/routers/feed.build_feed) so the page shows EXACTLY the same feed as GET /api/feed
# (song posts from people you follow plus your own, AND the behind-the-scenes posts of the artists
# you follow — T049, interleaved newest-first) — no duplicated query logic. Then we reshape each
# item for the template. The feed mixes two "kinds": a "song" item flattens the nested track fields;
# an "artist" item carries the (already signed) image URL and caption. Both turn the ISO timestamp
# into a friendly "3m ago" and collect the reaction types the viewer already tapped into a set the
# template can test with `in`. The "kind" is passed straight through so the template branches on it.
def _feed_items(session: Session, user) -> list[dict]:
    try:
        raw = build_feed(session, user)
    except Exception as e:  # noqa: BLE001 — any DB problem shows an empty feed, never a crash
        # No database reachable (e.g. running locally without credentials) or a transient
        # outage: log it and show an empty feed rather than crashing the whole page.
        logger.warning("feed build failed, showing empty feed: %s", e)
        return []

    items = []
    for it in raw:
        # viewerReactions is {type: True/False}; keep just the types set to True.
        mine = {kind for kind, on in it["viewerReactions"].items() if on}
        # Fields common to both kinds (id, author, engagement, "kind", "when").
        common = {
            "kind": it["kind"],
            "id": it["id"],
            "author": it["author"]["displayName"],
            "author_handle": it["author"]["handle"],  # for linking to their profile (T43)
            "caption": it["caption"],
            "when": _ago(datetime.fromisoformat(it["createdAt"])),
            "counts": it["reactionCounts"],
            "mine": mine,
            "comment_count": it["commentCount"],
            # The post's newest comments, pre-shaped for the template (T95): just the pieces
            # the card renders — who said it (name + handle for the profile link) and what.
            "latest_comments": [
                {
                    "author": c["author"]["displayName"],
                    "author_handle": c["author"]["handle"],
                    "body": c["body"],
                }
                for c in it["latestComments"]
            ],
        }
        if it["kind"] == "artist":
            # An artist behind-the-scenes post: an image + caption (imageUrl is already a signed
            # read URL from build_feed, T53), no track.
            common["image_url"] = it["imageUrl"]
        else:
            # A regular user post: flatten the nested track fields. `track` is None for a TEXT-ONLY
            # post (T104) — leave the song fields None so the template renders a note card instead
            # of a song row (no title/artist/art/play button).
            track = it["track"]
            common["title"] = track["title"] if track else None
            common["artist"] = track["artistName"] if track else None
            common["album_art"] = track["albumArtUrl"] if track else None
            # The Spotify track id, so the card can open the in-place embed player (T94). None
            # for a text-only post, which the template uses to decide song-row vs note.
            common["spotify_id"] = track["spotifyId"] if track else None
            # The most recent reactor (or None) for the "Liked by X and N others" line (T96).
            common["liked_by"] = it["likedBy"]
            # How many times the author has played this track (T102) — the card shows the
            # "played N times by {author}" line only from 2 up (see the template threshold).
            common["author_play_count"] = it["authorPlayCount"]
        items.append(common)
    return items


# The feed page: a list of the songs people have shared. Read-only, so no login is
# required (matching the T10 GET /api/posts endpoint, which is also public).
@router.get("/feed", response_class=HTMLResponse)
def feed(request: Request, session: Session = Depends(get_session)):
    # Gate the feed on login (T09): a visitor who isn't signed in is sent to Spotify login.
    # We authenticate against a scratch Response so that if require_user REFRESHES the
    # session (Supabase rotates refresh tokens on refresh), we can carry its refreshed
    # session cookie onto the page response below — otherwise the browser would keep an
    # old, now-rotated token and eventually be logged out.
    refreshed = Response()
    try:
        user = require_user(request, session=session, response=refreshed)
    except AuthError:
        return RedirectResponse("/auth/login", status_code=303)

    # Reuse the shared feed builder so the page matches GET /api/feed exactly (T41).
    posts = _feed_items(session, user)
    page = templates.TemplateResponse(
        request,
        "feed.html",
        {"page_title": "Feed · Brink", "posts": posts, "viewer": user},
    )
    for key, value in refreshed.raw_headers:
        if key == b"set-cookie":
            page.raw_headers.append((key, value))
    return page


# Gather everything a profile page needs: the person, their follower/following counts, whether the
# viewer already follows them, and their own posts (newest-first). This is the minimal profile that
# gives the Follow button (T43) a home; the full "Wrapped"-style stats/cluster/compatibility come
# with T44 (which needs the profile API, T14). Returns None if there's no user with that handle.
def _follow_list_items(session: Session, person_id: str, list_kind: str | None) -> dict | None:
    if list_kind not in {"followers", "following"}:
        return None

    if list_kind == "followers":
        # People whose Follow.following_id points at this profile.
        rows = session.exec(
            select(User)
            .join(Follow, Follow.follower_id == User.id)
            .where(Follow.following_id == person_id)
            .order_by(User.handle)
            .limit(FOLLOW_LIST_LIMIT)
        ).all()
        title = "Followers"
        empty = "No followers yet."
    else:
        # People this profile follows.
        rows = session.exec(
            select(User)
            .join(Follow, Follow.following_id == User.id)
            .where(Follow.follower_id == person_id)
            .order_by(User.handle)
            .limit(FOLLOW_LIST_LIMIT)
        ).all()
        title = "Following"
        empty = "Not following anyone yet."

    return {
        "kind": list_kind,
        "title": title,
        "empty": empty,
        "users": [
            {
                "handle": user.handle,
                "display_name": user.display_name,
                "is_artist": user.is_artist,
                "avatar_url": user.avatar_url,
            }
            for user in rows
        ],
    }


def _profile_data(
    session: Session,
    handle: str,
    viewer_id: str,
    list_kind: str | None = None,
) -> dict | None:
    person = session.exec(select(User).where(User.handle == handle)).first()
    if person is None:
        return None

    # follower_count = people who follow THEM; following_count = people THEY follow.
    follower_count = session.exec(
        select(func.count()).select_from(Follow).where(Follow.following_id == person.id)
    ).one()
    following_count = session.exec(
        select(func.count()).select_from(Follow).where(Follow.follower_id == person.id)
    ).one()
    # Does the viewer already follow this person? (Follow's PK is (follower_id, following_id).)
    is_following = session.get(Follow, (viewer_id, person.id)) is not None

    # Their posts, newest-first, joined to each track (simple read-only cards on the profile).
    rows = session.exec(
        select(Post, Track)
        .join(Track, Track.spotify_id == Post.track_id)
        .where(Post.user_id == person.id)
        .order_by(Post.created_at.desc())
    ).all()
    posts = [
        {
            "title": track.title,
            "artist": track.artist_name,
            "album_art": track.album_art_url,
            "caption": post.caption,
            "when": _ago(post.created_at),
        }
        for post, track in rows
    ]

    # Artist BTS posts (T54): if this profile belongs to an artist, show their promo posts here
    # too. WHY on /u/{handle}: user search and feed author links already land on profiles, so this
    # makes artist content discoverable without inventing a second artist URL. Images are stored as
    # private bucket paths, so each one gets a signed read URL before the browser sees it.
    artist_posts = []
    if person.is_artist:
        try:
            artist_rows = session.exec(
                select(ArtistPost)
                .where(ArtistPost.artist_user_id == person.id)
                .order_by(ArtistPost.created_at.desc())
            ).all()
        except Exception as e:  # noqa: BLE001 - optional artist content must not break profiles
            logger.warning("artist posts unavailable for profile %s: %s", person.id, e)
            session.rollback()
            artist_rows = []
        artist_post_ids = [post.id for post in artist_rows]

        # Start every post with zeroes so templates can render a stable HEART/FIRE/SPARKLE set even
        # when there is no engagement yet.
        reaction_counts = {
            post_id: {kind.value: 0 for kind in ReactionType}
            for post_id in artist_post_ids
        }
        comment_counts = {post_id: 0 for post_id in artist_post_ids}
        viewer_reactions = {
            post_id: {kind.value: False for kind in ReactionType}
            for post_id in artist_post_ids
        }

        if artist_post_ids:
            try:
                reaction_rows = session.exec(
                    select(ArtistReaction.artist_post_id, ArtistReaction.type, func.count())
                    .where(ArtistReaction.artist_post_id.in_(artist_post_ids))
                    .group_by(ArtistReaction.artist_post_id, ArtistReaction.type)
                ).all()
                for post_id, rtype, count in reaction_rows:
                    reaction_counts[post_id][ReactionType(rtype).value] = count

                comment_rows = session.exec(
                    select(ArtistComment.artist_post_id, func.count())
                    .where(ArtistComment.artist_post_id.in_(artist_post_ids))
                    .group_by(ArtistComment.artist_post_id)
                ).all()
                for post_id, count in comment_rows:
                    comment_counts[post_id] = count

                mine_rows = session.exec(
                    select(ArtistReaction.artist_post_id, ArtistReaction.type).where(
                        ArtistReaction.artist_post_id.in_(artist_post_ids),
                        ArtistReaction.user_id == viewer_id,
                    )
                ).all()
                for post_id, rtype in mine_rows:
                    viewer_reactions[post_id][ReactionType(rtype).value] = True
            except Exception as e:  # noqa: BLE001 - engagement is an optional profile enrichment
                logger.warning("artist engagement unavailable for profile %s: %s", person.id, e)
                session.rollback()

        artist_posts = [
            {
                "id": post.id,
                "image_url": _artist_image_url(post.image_url),
                "caption": post.caption,
                "when": _ago(post.created_at),
                "reaction_counts": reaction_counts[post.id],
                "mine": {
                    kind for kind, on in viewer_reactions[post.id].items() if on
                },
                "comment_count": comment_counts[post.id],
                "show_owner_engagement": person.id == viewer_id,
            }
            for post in artist_rows
        ]

    # The listening summary (T44): what this person actually plays, computed live from their Play
    # history (app/stats.py). The "recent" rows carry a raw played_at datetime; format it to a
    # friendly "3h ago" here, the same way posts do, so the template just prints a string.
    summary = listening_summary(session, person.id)
    recent = [
        {"title": r["title"], "artist": r["artist"], "album_art": r["album_art"],
         "when": _ago(r["played_at"])}
        for r in summary["recent"]
    ]

    return {
        "id": person.id,
        "display_name": person.display_name,
        "handle": person.handle,
        "avatar_url": person.avatar_url,
        "bio": person.bio,  # shown under the header (both own + others'); autoescaped as user text
        "follower_count": follower_count,
        "following_count": following_count,
        "follow_list": _follow_list_items(session, person.id, list_kind),
        "is_following": is_following,
        "is_self": person.id == viewer_id,  # hide the Follow button on your own profile
        # Does THIS person have a linked Spotify? Drives the "link Spotify" prompt on your own
        # profile when you haven't connected an account (a handle-only user has no plays to show).
        "has_spotify": person.spotify_id is not None,
        "top_tracks": summary["top_tracks"],
        "top_artists": summary["top_artists"],
        "recent": recent,
        "plays_30d": summary["plays_30d"],
        "streak": summary["streak"],
        "posts": posts,
        "is_artist": person.is_artist,
        "artist_posts": artist_posts,
    }


# A user's profile page: their header, a Follow/Unfollow button + follower counts (T43), and their
# posts. Login-gated like the rest of the app. `handle` comes from the URL, e.g. /u/andrea-ab12cd.
@router.get("/u/{handle}", response_class=HTMLResponse)
def profile(
    handle: str,
    request: Request,
    list_kind: str | None = Query(default=None, alias="list"),
    session: Session = Depends(get_session),
):
    refreshed = Response()
    try:
        viewer = require_user(request, session=session, response=refreshed)
    except AuthError:
        return RedirectResponse("/auth/login", status_code=303)

    data = _profile_data(session, handle, viewer_id=viewer.id, list_kind=list_kind)
    if data is None:
        # No such handle — render a friendly 404 page rather than a raw error.
        page = templates.TemplateResponse(
            request,
            "profile_missing.html",
            {"page_title": "Not found · Brink", "viewer": viewer},
            status_code=404,
        )
    else:
        # Now-playing badge (T44/UI-10): only on your OWN profile. The now-playing lookup (T20) is
        # "me"-scoped — it uses the logged-in user's own Spotify token — so we can show the viewer
        # their own current track, but not someone else's. get_currently_playing returns None (never
        # raises) when nothing is playing / Spotify isn't linked, so the badge simply hides.
        now_playing = None
        if data["is_self"]:
            try:
                playing = spotify.get_currently_playing(session, viewer.id)
            except Exception as e:  # noqa: BLE001 - Spotify is optional profile enrichment
                logger.warning("now-playing unavailable for profile %s: %s", viewer.id, e)
                playing = None
            if playing and playing.get("is_playing") and playing.get("track"):
                now_playing = playing["track"]
        page = templates.TemplateResponse(
            request,
            "profile.html",
            {"page_title": f"{data['display_name']} · Brink", "p": data,
             "now_playing": now_playing, "viewer": viewer},
        )
    for key, value in refreshed.raw_headers:
        if key == b"set-cookie":
            page.raw_headers.append((key, value))
    return page


# The artist "behind-the-scenes" page (T51): an artist account's promo posts, plus (for the artist
# themselves) an upload box to add a new one. Login-gated; the upload UI only shows for artist
# accounts (User.is_artist) — the T50 API is the real gate (403 for non-artists), this just hides
# the box for everyone else. The actual file upload goes browser -> Supabase Storage via a signed
# URL (see static/artist-upload.js).
@router.get("/artist", response_class=HTMLResponse)
def artist_page(request: Request, session: Session = Depends(get_session)):
    refreshed = Response()
    try:
        user = require_user(request, session=session, response=refreshed)
    except AuthError:
        return RedirectResponse("/auth/login", status_code=303)

    # This artist's existing promo posts, newest-first.
    rows = session.exec(
        select(ArtistPost)
        .where(ArtistPost.artist_user_id == user.id)
        .order_by(ArtistPost.created_at.desc())
    ).all()
    # T50 stores each post's image as a bare storage PATH (e.g. "user-id/pic.jpg") in the PRIVATE
    # artist-images bucket, which the browser cannot fetch directly. Sign a short-lived read URL
    # for each one here (T53), so the template gets an <img src> that actually displays.
    posts = [
        {
            # Tri-state via _artist_image_url (T104): None (text-only → note), "" (signing failed
            # → placeholder, T103, so one un-signable image can no longer 500 the page), or a URL.
            "image_url": _artist_image_url(post.image_url),
            "caption": post.caption,
            "when": _ago(post.created_at),
        }
        for post in rows
    ]

    page = templates.TemplateResponse(
        request,
        "artist.html",
        {"page_title": "Artist · Brink", "is_artist": user.is_artist, "posts": posts,
         "viewer": user},
    )
    for key, value in refreshed.raw_headers:
        if key == b"set-cookie":
            page.raw_headers.append((key, value))
    return page


# Read the analytics the app already computed: the K-means clustering quality + the taste
# communities (T34), and the popularity-model quality once it's trained (T36). All reads are
# wrapped so that if the analytics tables aren't there yet (e.g. local dev without the gold
# schema) or a model hasn't run, the page shows a friendly "not ready yet" instead of crashing.
# WHY read by model name: T36 writes ModelMetrics("popularity_regression") into the SAME store,
# so its numbers appear here automatically the moment it lands — no code change (T45).
# The 0-1 Spotify audio features shown as a community's "audio DNA" bars — the recognizable ones.
# (tempo/loudness/mode are on different scales, so they're left out of the 0-100% bar visual.)
_DNA_FEATURES = [
    "danceability", "energy", "valence", "acousticness",
    "instrumentalness", "liveness", "speechiness",
]

# A vibrant, distinct colour per community (cycled if there are ever more communities than colours).
_COMMUNITY_COLORS = [
    "#9d8df1", "#f472b6", "#5eead4", "#fbbf24",
    "#60a5fa", "#34d399", "#fb923c", "#c084fc",
]


# Turn a silhouette score into a plain-English "how distinct are the communities" reading. The score
# runs ~0 (heavy overlap) to 1 (cleanly separated); Brink's k was forced to 7 so some overlap is
# expected — we say that honestly rather than dress it up.
def _silhouette_reading(score) -> tuple[int, str]:
    if score is None:
        return (0, "not measured yet")
    pct = max(0, min(100, round(score * 100)))
    if score < 0.25:
        return (pct, "the tribes share a lot of taste — the lines between them are soft")
    if score < 0.5:
        return (pct, "the tribes are moderately distinct")
    return (pct, "the tribes are sharply separated")


def _analytics_data(session: Session) -> dict:
    # Shape everything the analytics page's visuals need, from the REAL gold tables. All reads are
    # wrapped so a missing model store (e.g. local dev) shows the friendly "not ready" states.
    data = {"kmeans": None, "communities": [], "total_listeners": 0, "popularity": None}
    try:
        km = session.get(ModelMetrics, "kmeans")
        if km is not None:
            pct, reading = _silhouette_reading(km.silhouette)
            data["kmeans"] = {
                "silhouette": km.silhouette,
                "k": km.k,
                "silhouette_pct": pct,
                "silhouette_reading": reading,
            }

        # Communities largest-first. We compute each one's share of all listeners (for the % label)
        # and a bar width relative to the BIGGEST community (so the leaderboard's top bar is full).
        clusters = list(session.exec(select(Cluster).order_by(Cluster.size.desc())).all())
        total = sum(c.size for c in clusters)
        biggest = clusters[0].size if clusters else 0
        data["total_listeners"] = total
        data["total_listeners_display"] = f"{total:,}"  # e.g. "1,203,025" for the hero
        for rank, c in enumerate(clusters):
            centroid = c.centroid if isinstance(c.centroid, dict) else {}
            # Each community's "audio DNA": the 0-1 features from its real centroid, as 0-100% bars.
            features = [
                {"name": f, "pct": max(0, min(100, round(float(centroid[f]) * 100)))}
                for f in _DNA_FEATURES
                if centroid.get(f) is not None
            ]
            data["communities"].append({
                "rank": rank + 1,
                "label": c.label,
                "size": c.size,
                "size_display": f"{c.size:,}",
                "share_pct": round(c.size / total * 100, 1) if total else 0,
                "bar_pct": round(c.size / biggest * 100) if biggest else 0,
                "color": _COMMUNITY_COLORS[rank % len(_COMMUNITY_COLORS)],
                "features": features,
            })

        # Popularity model quality — present only after T36 trains it (fills in automatically).
        pop = session.get(ModelMetrics, "popularity_regression")
        if pop is not None:
            data["popularity"] = {
                "r2": pop.r2,
                "rmse": pop.rmse,
                "feature_importances": pop.feature_importances or {},
            }
    except Exception as e:  # noqa: BLE001 — no analytics store yet -> show the "not ready" state
        logger.warning("analytics read failed (model store unavailable): %s", e)
    return data


# The analytics page (T45): shows Brink's real model output — the taste communities and model
# quality — reading the gold ModelMetrics/Cluster tables (no hardcoded numbers). Login-gated.
@router.get("/analytics", response_class=HTMLResponse)
def analytics_page(request: Request, session: Session = Depends(get_session)):
    refreshed = Response()
    try:
        viewer = require_user(request, session=session, response=refreshed)
    except AuthError:
        return RedirectResponse("/auth/login", status_code=303)

    # Pass `viewer` so base.html renders the signed-in nav (Feed / My profile / Analytics /
    # Log out). Without it the shared nav falls back to its logged-out header even though the
    # visitor is signed in — the whole reason this page looked "logged out" (the analytics
    # content only renders because require_user succeeded above).
    page = templates.TemplateResponse(
        request,
        "analytics.html",
        {"page_title": "Analytics · Brink", "a": _analytics_data(session), "viewer": viewer},
    )
    for key, value in refreshed.raw_headers:
        if key == b"set-cookie":
            page.raw_headers.append((key, value))
    return page
