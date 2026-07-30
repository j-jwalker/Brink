# WHAT THIS FILE IS
# Automated checks for the browser-facing web pages (the HTML people see), as
# opposed to the JSON API. WHY: ADR-0013 serves the frontend from FastAPI via
# Jinja templates, so we want a test that confirms the landing page actually
# renders — returns a 200, is HTML (not JSON), and contains the real Brink copy —
# so a future change can't silently break the page without CI catching it.

# The `client` fixture (a fake HTTP client) comes from conftest.py.


# Since T47 the home route asks for a database session (to resolve the optional signed-in
# viewer for the nav), so like every other page test we hand it a stand-in — an anonymous
# visitor never actually queries it (require_user rejects the request before any lookup).
# The imports live lower in this file (module-level, so they're loaded before tests run).


# The landing page loads and comes back as an HTML document.
def test_home_page_renders_html(client):
    app.dependency_overrides[get_session] = lambda: MagicMock()
    res = client.get("/")
    assert res.status_code == 200  # 200 = OK
    # It must be a web page, not the JSON envelope the API returns.
    assert res.headers["content-type"].startswith("text/html")


# The page actually contains Brink's landing content (not an empty shell). We
# check for the brand, the headline, and the sign-in call to action — the three
# things a visitor must see.
def test_home_page_shows_landing_content(client):
    app.dependency_overrides[get_session] = lambda: MagicMock()
    body = client.get("/").text
    assert "brink" in body
    assert "Your listening, made social." in body
    assert "Continue with Spotify" in body


# The stylesheet the pages depend on is served (a broken link here would leave
# the page unstyled). We only assert it loads and is CSS.
def test_stylesheet_is_served(client):
    res = client.get("/static/brink.css")
    assert res.status_code == 200
    assert "text/css" in res.headers["content-type"]


# T86: the edit form uses grid when open, so the author stylesheet must explicitly preserve the
# HTML `hidden` state. Otherwise `display: grid` overrides the browser default and shows it early.
def test_stylesheet_keeps_edit_profile_form_hidden(client):
    css = client.get("/static/brink.css").text
    assert ".edit-profile-form[hidden] { display: none; }" in css


# The disclosure script must announce the same open/closed state that it renders visually.
def test_edit_profile_script_syncs_expanded_state(client):
    script = client.get("/static/edit-profile.js").text
    assert 'btn.setAttribute("aria-expanded", opening ? "true" : "false")' in script


# T85: a release can update HTML and CSS at the same time. The version query forces browsers
# holding the pre-T80/T83 stylesheet to fetch the corrected button and edit-profile styles.
def test_home_page_uses_versioned_stylesheet(client):
    app.dependency_overrides[get_session] = lambda: MagicMock()
    body = client.get("/").text
    assert 'href="/static/brink.css?v=87"' in body


# After that one-time cache bust, every static response asks the browser to revalidate before
# reuse. This prevents later releases from pairing fresh HTML with stale CSS or JavaScript.
def test_static_assets_require_revalidation(client):
    res = client.get("/static/brink.css")
    assert res.headers["cache-control"] == "no-cache"


# ---- Feed page (reuses build_feed: posts from people you follow + your own) ----

from types import SimpleNamespace
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from app.db import get_session
from app.main import app
from app.models import (
    ArtistComment,
    ArtistPost,
    ArtistReaction,
    Comment,
    Follow,
    Play,
    Post,
    PostSource,
    Reaction,
    ReactionType,
    Track,
    User,
)
from app.security import session as login_session
from app.security import supabase

# The Supabase user id _login signs in as. The feed only shows a viewer's own posts (plus the
# people they follow), so tests author their posts under the viewer that require_user returns —
# which is looked up by supabase_user_id, not the primary key.
_VIEWER_ID = "abcdef12-3456-7890-abcd-ef1234567890"


def _login(client, monkeypatch):
    # Sign a fake user in for feed tests: the feed is login-gated (T09), so we plant a
    # valid session cookie and fake the Supabase token check the same way the auth unit
    # tests do — no real Spotify/Supabase.
    su = SimpleNamespace(id=_VIEWER_ID, email=None, user_metadata={}, app_metadata={})
    monkeypatch.setattr(login_session, "decode", lambda raw: {"access_token": "AT", "refresh_token": "RT"})
    monkeypatch.setattr(supabase, "get_user_from_token", lambda t: su if t == "AT" else None)
    client.cookies.set(login_session.SESSION_COOKIE, "x")


def _seed_viewer(db_session):
    # Create the viewer's Brink user, keyed by supabase_user_id so require_user returns THIS
    # row (its .id then matches the posts/reactions we attribute to the viewer). Returns it.
    viewer = User(supabase_user_id=_VIEWER_ID, handle="viewer", display_name="Viewer",
                  created_at=datetime.now(timezone.utc))
    db_session.add(viewer)
    db_session.commit()
    db_session.refresh(viewer)
    return viewer


# An anonymous visitor is redirected to Spotify login instead of seeing the feed (T09).
def test_feed_redirects_anonymous_to_login(client):
    app.dependency_overrides[get_session] = lambda: MagicMock()
    res = client.get("/feed", follow_redirects=False)
    assert res.status_code == 303
    assert res.headers["location"] == "/auth/login"


# With a real post by the viewer, their feed renders it — proving the page is wired to the
# real feed data (not hardcoded). We seed a throwaway in-memory database and point the app
# at it.
def test_feed_shows_real_posts(client, db_session, monkeypatch):
    # Parents before children — the test DB enforces foreign keys. The post is the viewer's
    # own so it shows in their feed (which is follow + own).
    viewer = _seed_viewer(db_session)
    db_session.add(Track(spotify_id="t_redbone", title="Redbone", artist_name="Childish Gambino"))
    db_session.commit()
    db_session.add(Post(user_id=viewer.id, track_id="t_redbone", caption="a whole vibe",
                        source=PostSource.MANUAL))
    db_session.commit()

    app.dependency_overrides[get_session] = lambda: db_session
    _login(client, monkeypatch)

    res = client.get("/feed")
    assert res.status_code == 200
    body = res.text
    assert "Redbone" in body            # the track title
    assert "Childish Gambino" in body   # the artist
    assert "a whole vibe" in body       # the caption


# With no posts, a logged-in user's feed still returns a page (never crashes) and shows
# the empty state — exactly what a brand-new or offline app looks like.
def test_feed_empty_state(client, db_session, monkeypatch):
    app.dependency_overrides[get_session] = lambda: db_session  # empty database
    _login(client, monkeypatch)
    res = client.get("/feed")
    assert res.status_code == 200
    assert "No songs shared yet" in res.text
    assert "Search above to share the first one" in res.text


# ---- T41: feed shows live reaction counts + highlights the viewer's own reactions ----


def test_feed_shows_reaction_counts_and_marks_own(client, db_session, monkeypatch):
    # The viewer's own post, plus another user who also reacts to it (parents before children —
    # the test DB enforces foreign keys, and a Reaction references both a Post and a User).
    viewer = _seed_viewer(db_session)
    other = User(handle="other", display_name="Other", created_at=datetime.now(timezone.utc))
    db_session.add(other)
    db_session.add(Track(spotify_id="t_song", title="Song One", artist_name="Artist One"))
    db_session.commit()
    db_session.refresh(other)
    post = Post(user_id=viewer.id, track_id="t_song", source=PostSource.MANUAL)
    db_session.add(post)
    db_session.commit()
    db_session.refresh(post)

    # Two hearts (one is the VIEWER's own) and one fire. Sparkle stays at zero.
    db_session.add(Reaction(post_id=post.id, user_id=viewer.id, type=ReactionType.HEART))
    db_session.add(Reaction(post_id=post.id, user_id=other.id, type=ReactionType.HEART))
    db_session.add(Reaction(post_id=post.id, user_id=other.id, type=ReactionType.FIRE))
    db_session.commit()

    app.dependency_overrides[get_session] = lambda: db_session
    _login(client, monkeypatch)

    body = client.get("/feed").text

    # The reaction bar is wired to this post, with a button per type.
    assert f'data-post-id="{post.id}"' in body
    assert 'data-type="HEART"' in body
    assert 'data-type="FIRE"' in body
    assert 'data-type="SPARKLE"' in body
    # Counts render: heart 2, fire 1, sparkle 0 (the count is the span's text).
    assert ">2</span>" in body  # hearts
    assert ">1</span>" in body  # fire
    # The viewer's own heart is highlighted as already tapped.
    assert "reacted" in body


def test_feed_reactions_not_marked_for_other_viewer(client, db_session, monkeypatch):
    # The viewer's own post with a reaction left by SOMEONE ELSE: the count shows, but nothing
    # is marked as the viewer's.
    viewer = _seed_viewer(db_session)
    other = User(handle="other", display_name="Other", created_at=datetime.now(timezone.utc))
    db_session.add(other)
    db_session.add(Track(spotify_id="t_x", title="Track X", artist_name="Artist X"))
    db_session.commit()
    db_session.refresh(other)
    post = Post(user_id=viewer.id, track_id="t_x", source=PostSource.MANUAL)
    db_session.add(post)
    db_session.commit()
    db_session.refresh(post)
    db_session.add(Reaction(post_id=post.id, user_id=other.id, type=ReactionType.HEART))
    db_session.commit()

    app.dependency_overrides[get_session] = lambda: db_session
    _login(client, monkeypatch)  # signs in as _VIEWER_ID, who left no reactions

    body = client.get("/feed").text
    # The heart count shows (1), but the viewer hasn't tapped anything.
    assert 'aria-pressed="true"' not in body
    assert 'aria-pressed="false"' in body


# ---- T42: feed post cards carry a comment section with the live comment count ----


def test_feed_shows_comment_section_and_count(client, db_session, monkeypatch):
    viewer = _seed_viewer(db_session)
    db_session.add(Track(spotify_id="t_c", title="Commented Song", artist_name="Artist"))
    db_session.commit()
    post = Post(user_id=viewer.id, track_id="t_c", source=PostSource.MANUAL)
    db_session.add(post)
    db_session.commit()
    db_session.refresh(post)
    db_session.add(Comment(post_id=post.id, user_id=viewer.id, body="first!"))
    db_session.commit()

    app.dependency_overrides[get_session] = lambda: db_session
    _login(client, monkeypatch)

    body = client.get("/feed").text
    # The comment section is present and wired to this post, with an add-comment input.
    assert f'class="comments" data-post-id="{post.id}"' in body
    assert 'onclick="toggleComments(this)"' in body
    assert 'name="body"' in body
    # The comment count from build_feed renders (this post has one comment).
    assert 'class="comment-count">1<' in body


# ---- T95: the latest comments render inline on the card (Instagram-style) ----


def test_feed_renders_latest_comments_inline(client, db_session, monkeypatch):
    viewer = _seed_viewer(db_session)
    db_session.add(Track(spotify_id="t_ic", title="Chatty Song", artist_name="Artist"))
    db_session.commit()
    post = Post(user_id=viewer.id, track_id="t_ic", source=PostSource.MANUAL)
    db_session.add(post)
    db_session.commit()
    db_session.refresh(post)
    db_session.add(Comment(post_id=post.id, user_id=viewer.id, body="so good live"))
    db_session.commit()

    app.dependency_overrides[get_session] = lambda: db_session
    _login(client, monkeypatch)

    body = client.get("/feed").text
    # The comment shows on the card itself — no click needed — with its author linked.
    assert "so good live" in body
    assert 'class="comment-inline-list"' in body
    assert 'class="comment-inline-author" href="/u/viewer"' in body
    # The existing toggle/panel machinery is still there for "view all + add a comment".
    assert 'onclick="toggleComments(this)"' in body


# ---- T40: the composer (search + share a song) renders on the feed ----


def test_feed_has_composer(client, db_session, monkeypatch):
    _seed_viewer(db_session)
    app.dependency_overrides[get_session] = lambda: db_session
    _login(client, monkeypatch)

    body = client.get("/feed").text
    assert 'class="composer' in body               # the composer block is present
    assert 'for="composer-search-input"' in body   # search input has a real label
    assert 'id="composer-status"' in body          # JS has a visible status/error target
    assert "composerSearch(this)" in body          # the search box is wired
    assert "/static/composer.js" in body           # the script is loaded
    # T104: the text box + Share are always present (a song is optional), and the remove-song
    # control on the attached-song chip is wired.
    assert 'id="composer-caption-input"' in body   # the always-visible "just writing" box
    assert "composerPublish(this)" in body         # the always-visible Share button is wired
    assert "composerRemoveTrack(this)" in body     # the attached-song chip's × is wired


# T104: the composer script can publish a TEXT-ONLY post — it doesn't bail when no song is
# attached, sends `track: null`, and blocks a completely empty share.
def test_composer_script_supports_text_only(client):
    script = client.get("/static/composer.js").text
    assert "composerRemoveTrack" in script          # removing an attached song is supported
    assert "track: track" in script                 # the track is optional in the publish body
    assert "Write something or add a song" in script  # the empty-share guard message


# ---- T102: feed song card shows "played N times by {author}" at 2+ plays ----


# A song whose author has played it 2+ times shows the endorsement line; a song played only once
# (below the threshold) shows no line at all — one play is "they just heard it", not a signal.
def test_feed_song_card_shows_author_play_count_past_threshold(client, db_session, monkeypatch):
    viewer = _seed_viewer(db_session)  # display_name "Viewer"
    db_session.add(Track(spotify_id="t_multi", title="Multi", artist_name="Band"))
    db_session.add(Track(spotify_id="t_once", title="Once", artist_name="Band"))
    db_session.commit()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db_session.add(Post(id="pp-multi", user_id=viewer.id, track_id="t_multi",
                        source=PostSource.MANUAL, created_at=now))
    db_session.add(Post(id="pp-once", user_id=viewer.id, track_id="t_once",
                        source=PostSource.MANUAL, created_at=now - timedelta(minutes=1)))
    # The viewer played t_multi three times (shown) and t_once just once (hidden). Distinct times —
    # Play is unique on (userId, playedAt).
    for i in range(3):
        db_session.add(Play(user_id=viewer.id, track_id="t_multi", played_at=now - timedelta(hours=i)))
    db_session.add(Play(user_id=viewer.id, track_id="t_once", played_at=now - timedelta(days=1)))
    db_session.commit()

    app.dependency_overrides[get_session] = lambda: db_session
    _login(client, monkeypatch)

    body = client.get("/feed").text
    assert "played 3 times by Viewer" in body   # 3 plays -> endorsement line shown
    assert "played 1 time" not in body          # 1 play -> below threshold, never rendered


# T104: a TEXT-ONLY post (no track) renders as a distinct note card on the feed — the caption in a
# `.post-note-body`, and no play button (there's no song to play).
def test_feed_renders_text_only_post_as_note(client, db_session, monkeypatch):
    viewer = _seed_viewer(db_session)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db_session.add(Post(id="pp-text", user_id=viewer.id, track_id=None,
                        caption="thinking out loud", source=PostSource.MANUAL, created_at=now))
    db_session.commit()

    app.dependency_overrides[get_session] = lambda: db_session
    _login(client, monkeypatch)

    body = client.get("/feed").text
    assert "post-note" in body                  # the note card styling is applied
    assert "thinking out loud" in body          # the caption is the post body
    # No play button for a song-less post: the note card omits the .post-art play control.
    assert 'aria-label="Play thinking out loud"' not in body


# ---- T101: one-tap "Share what you're hearing" button in the composer ----


# The composer carries a "share what you're hearing" button wired to the now-playing handler,
# so a user can drop their current Spotify track into the composer with one tap.
def test_feed_composer_has_share_now_playing_button(client, db_session, monkeypatch):
    _seed_viewer(db_session)
    app.dependency_overrides[get_session] = lambda: db_session
    _login(client, monkeypatch)

    body = client.get("/feed").text
    assert "shareNowPlaying(this)" in body   # the button is wired to the T101 handler


# The composer script drives the one-tap flow: it fetches the now-playing endpoint, publishes the
# resulting post with the SPOTIFY source (so it's distinguishable from a typed MANUAL post), and
# handles the "nothing playing" empty case via the status line rather than breaking.
def test_composer_script_shares_now_playing(client):
    script = client.get("/static/composer.js").text
    assert "/api/me/now-playing" in script      # it asks what's playing
    assert "shareNowPlaying" in script          # the handler exists
    assert '"SPOTIFY"' in script                 # these posts publish with the SPOTIFY source
    assert "Nothing playing" in script          # the null case is handled with friendly copy


# ---- T94: feed song cards are playable in place via the Spotify embed player ----


# A song card carries its Spotify track id and an accessible play control, and loads the
# player script. The embed iframe itself must NOT be in the initial HTML — player.js only
# builds it when the listener taps play (keeps the page light: no third-party frames on load).
def test_feed_song_card_is_playable(client, db_session, monkeypatch):
    viewer = _seed_viewer(db_session)
    db_session.add(Track(spotify_id="t_redbone", title="Redbone", artist_name="Childish Gambino",
                         album_art_url="https://img.example/redbone.jpg"))
    db_session.commit()
    db_session.add(Post(user_id=viewer.id, track_id="t_redbone", source=PostSource.MANUAL))
    db_session.commit()

    app.dependency_overrides[get_session] = lambda: db_session
    _login(client, monkeypatch)

    body = client.get("/feed").text
    assert 'data-spotify-id="t_redbone"' in body   # the card knows which track it plays
    assert 'aria-label="Play Redbone"' in body     # the art is a labelled play button
    assert "togglePlayer(this)" in body            # wired to the player script
    assert "/static/player.js" in body             # the script is loaded
    assert "<iframe" not in body                   # lazy: no embed frame on initial load


# A post whose track has no album art must still be playable — the play button renders
# (with its gradient placeholder background) even without an <img> inside it.
def test_feed_song_card_playable_without_art(client, db_session, monkeypatch):
    viewer = _seed_viewer(db_session)
    db_session.add(Track(spotify_id="t_noart", title="No Art Song", artist_name="Somebody"))
    db_session.commit()
    db_session.add(Post(user_id=viewer.id, track_id="t_noart", source=PostSource.MANUAL))
    db_session.commit()

    app.dependency_overrides[get_session] = lambda: db_session
    _login(client, monkeypatch)

    body = client.get("/feed").text
    assert 'data-spotify-id="t_noart"' in body
    assert 'aria-label="Play No Art Song"' in body


# ---- T97: double-tap a song card to heart it (Instagram's signature gesture) ----


# The feed loads the double-tap script whenever song posts render, so the gesture is live.
def test_feed_loads_double_tap_script(client, db_session, monkeypatch):
    viewer = _seed_viewer(db_session)
    db_session.add(Track(spotify_id="t_dt", title="Tap Tap", artist_name="Gesture"))
    db_session.commit()
    db_session.add(Post(user_id=viewer.id, track_id="t_dt", source=PostSource.MANUAL))
    db_session.commit()

    app.dependency_overrides[get_session] = lambda: db_session
    _login(client, monkeypatch)

    assert "/static/double-tap.js" in client.get("/feed").text


# The gesture must be ADD-ONLY (Instagram semantics: double-tap never removes a heart —
# removal stays on the ❤️ button) and must reuse the existing react() logic rather than
# talking to the API itself. We assert on the script's source, like the T86 script test.
def test_double_tap_script_is_add_only_and_reuses_react(client):
    script = client.get("/static/double-tap.js").text
    assert 'classList.contains("reacted")' in script   # checks before hearting — never unhearts
    assert "react(" in script                          # delegates to reactions.js
    assert "prefers-reduced-motion" in script          # respects the reduced-motion setting


# The floating-heart animation the gesture triggers exists in the stylesheet.
def test_stylesheet_has_double_tap_heart_animation(client):
    css = client.get("/static/brink.css").text
    assert ".double-tap-heart" in css
    assert "@keyframes double-tap-pop" in css


# ---- T049: followed artists' behind-the-scenes posts render in the feed page ----


# A followed artist's ArtistPost renders on the feed page as an artist card, with its signed image,
# the audience like/comment controls wired to the T52 API, and the artist-engagement script loaded.
def test_feed_shows_followed_artist_post(client, db_session, monkeypatch):
    viewer = _seed_viewer(db_session)
    artist = User(handle="the-band", display_name="The Band", is_artist=True,
                  created_at=datetime.now(timezone.utc))
    db_session.add(artist)
    db_session.commit()
    db_session.refresh(artist)
    db_session.add(Follow(follower_id=viewer.id, following_id=artist.id))
    post = ArtistPost(artist_user_id=artist.id, image_url="the-band/soundcheck.jpg",
                      caption="soundcheck vibes")
    db_session.add(post)
    db_session.commit()
    db_session.refresh(post)
    # The feed builder signs the private image path; stub it so no test hits Supabase.
    monkeypatch.setattr(
        "app.routers.feed.create_signed_read_url_or_blank",
        lambda bucket, path: f"https://signed/{bucket}/{path}?token=readtok",
    )
    app.dependency_overrides[get_session] = lambda: db_session
    _login(client, monkeypatch)

    body = client.get("/feed").text
    assert "soundcheck vibes" in body                                  # the caption
    assert "behind the scenes" in body                                 # the artist card label
    assert 'src="https://signed/artist-images/the-band/soundcheck.jpg?token=readtok"' in body
    assert "artist-reactions" in body                                  # audience reaction bar
    assert "artistReact(this)" in body
    assert "toggleArtistComments(this)" in body
    assert "aria-expanded=\"false\"" in body
    assert f'aria-controls="artist-comment-panel-{post.id}"' in body
    assert f'data-post-id="{post.id}"' in body
    assert "/static/artist-engagement.js" in body                      # the engagement script


# A feed with only song posts (no artist posts) does NOT load the artist-engagement script.
def test_feed_without_artist_posts_omits_engagement_script(client, db_session, monkeypatch):
    viewer = _seed_viewer(db_session)
    db_session.add(Track(spotify_id="t1", title="Song", artist_name="Someone"))
    db_session.commit()
    db_session.add(Post(user_id=viewer.id, track_id="t1", source=PostSource.MANUAL))
    db_session.commit()
    app.dependency_overrides[get_session] = lambda: db_session
    _login(client, monkeypatch)

    body = client.get("/feed").text
    assert "Song" in body                                              # the song post rendered
    assert "/static/artist-engagement.js" not in body                  # no artist script needed


# ---- T43: profile page + follow button ----


def test_profile_page_shows_follow_button(client, db_session, monkeypatch):
    _seed_viewer(db_session)
    target = User(handle="artist-x", display_name="Artist X",
                  created_at=datetime.now(timezone.utc))
    db_session.add(target)
    db_session.commit()
    db_session.refresh(target)

    app.dependency_overrides[get_session] = lambda: db_session
    _login(client, monkeypatch)

    body = client.get("/u/artist-x").text
    assert "Artist X" in body
    assert "followers" in body
    assert f'data-user-id="{target.id}"' in body   # follow button wired to this user
    assert "toggleFollow(this)" in body


def test_profile_shows_following_state_and_counts(client, db_session, monkeypatch):
    viewer = _seed_viewer(db_session)
    target = User(handle="followed-one", display_name="Followed",
                  created_at=datetime.now(timezone.utc))
    db_session.add(target)
    db_session.commit()
    db_session.refresh(target)
    # The viewer already follows the target -> button reads "Following"; target has 1 follower.
    db_session.add(Follow(follower_id=viewer.id, following_id=target.id))
    db_session.commit()

    app.dependency_overrides[get_session] = lambda: db_session
    _login(client, monkeypatch)

    body = client.get("/u/followed-one").text
    assert 'data-following="true"' in body
    assert "Following" in body
    assert 'class="follower-count">1<' in body


def test_profile_counts_link_to_follow_lists(client, db_session, monkeypatch):
    viewer = _seed_viewer(db_session)
    target = User(handle="with-graph", display_name="With Graph",
                  created_at=datetime.now(timezone.utc))
    follower = User(handle="follower-one", display_name="Follower One",
                    created_at=datetime.now(timezone.utc))
    followed = User(handle="followed-one", display_name="Followed One",
                    created_at=datetime.now(timezone.utc))
    db_session.add(target)
    db_session.add(follower)
    db_session.add(followed)
    db_session.commit()
    db_session.refresh(target)
    db_session.refresh(follower)
    db_session.refresh(followed)
    db_session.add(Follow(follower_id=follower.id, following_id=target.id))
    db_session.add(Follow(follower_id=target.id, following_id=followed.id))
    db_session.commit()

    app.dependency_overrides[get_session] = lambda: db_session
    _login(client, monkeypatch)

    body = client.get("/u/with-graph").text
    assert 'href="/u/with-graph?list=followers"' in body
    assert 'href="/u/with-graph?list=following"' in body
    assert 'class="follower-count">1<' in body
    assert ">1</b> following" in body

    followers_body = client.get("/u/with-graph?list=followers").text
    assert "Followers" in followers_body
    assert "Follower One" in followers_body
    assert "Followed One" not in followers_body

    following_body = client.get("/u/with-graph?list=following").text
    assert "Following" in following_body
    assert "Followed One" in following_body
    assert "Follower One" not in following_body


# T48: a user's bio renders under their profile header (both own and others').
def test_profile_shows_bio(client, db_session, monkeypatch):
    _seed_viewer(db_session)
    target = User(handle="bio-haver", display_name="Bio Haver", bio="just here for the tunes",
                  created_at=datetime.now(timezone.utc))
    db_session.add(target)
    db_session.commit()

    app.dependency_overrides[get_session] = lambda: db_session
    _login(client, monkeypatch)

    body = client.get("/u/bio-haver").text
    assert "just here for the tunes" in body


# T48: your OWN profile shows the "Edit profile" control that reveals the bio/avatar form.
def test_own_profile_shows_edit_profile(client, db_session, monkeypatch):
    _seed_viewer(db_session)  # handle "viewer"
    app.dependency_overrides[get_session] = lambda: db_session
    _login(client, monkeypatch)

    body = client.get("/u/viewer").text
    assert "Edit profile" in body
    assert 'aria-expanded="false"' in body
    assert 'aria-controls="edit-profile-form"' in body
    assert 'id="edit-profile-form" class="edit-profile-form" hidden' in body
    assert "/static/edit-profile.js" in body


def test_own_profile_has_no_follow_button(client, db_session, monkeypatch):
    _seed_viewer(db_session)  # the viewer's handle is "viewer"
    app.dependency_overrides[get_session] = lambda: db_session
    _login(client, monkeypatch)
    body = client.get("/u/viewer").text
    assert "toggleFollow(this)" not in body  # you can't follow yourself


# T55: a non-artist viewing their OWN profile sees the "Become an artist" button (which calls
# POST /api/me/become-artist). It must not appear on someone else's profile or for an artist.
def test_own_profile_shows_become_artist_button(client, db_session, monkeypatch):
    _seed_viewer(db_session)  # a normal listener (is_artist defaults to False), handle "viewer"
    app.dependency_overrides[get_session] = lambda: db_session
    _login(client, monkeypatch)
    body = client.get("/u/viewer").text
    assert 'class="profile-actions"' in body
    assert "becomeArtist(this)" in body
    assert 'aria-describedby="become-artist-status"' in body
    assert 'id="become-artist-status"' in body
    assert "/static/become-artist.js" in body


def test_own_profile_hides_become_artist_button_for_artist(client, db_session, monkeypatch):
    _ensure_artist_table(db_session)
    _seed_artist(db_session)  # is_artist=True, keyed to the login id, handle "the-artist"
    app.dependency_overrides[get_session] = lambda: db_session
    _login(client, monkeypatch)
    body = client.get("/u/the-artist").text
    assert "becomeArtist(this)" not in body  # already an artist — nothing to become


def test_profile_missing_handle_is_404(client, db_session, monkeypatch):
    _seed_viewer(db_session)
    app.dependency_overrides[get_session] = lambda: db_session
    _login(client, monkeypatch)
    res = client.get("/u/nobody-here")
    assert res.status_code == 404
    assert "couldn't find that profile" in res.text


# ---- T54: artist posts are visible on artist profiles, with audience engagement UI ----


def test_artist_profile_shows_artist_posts_to_fan(client, db_session, monkeypatch):
    _ensure_artist_table(db_session)
    _seed_viewer(db_session)  # signed-in fan
    artist = User(handle="stage-name", display_name="Stage Name", is_artist=True,
                  created_at=datetime.now(timezone.utc))
    db_session.add(artist)
    db_session.commit()
    db_session.refresh(artist)
    post = ArtistPost(artist_user_id=artist.id, image_url="stage-name/backstage.jpg",
                      caption="backstage warmup")
    db_session.add(post)
    db_session.commit()
    db_session.refresh(post)
    monkeypatch.setattr(
        "app.routers.pages.create_signed_read_url_or_blank",
        lambda bucket, path: f"https://signed/{bucket}/{path}?token=readtok",
    )
    app.dependency_overrides[get_session] = lambda: db_session
    _login(client, monkeypatch)

    body = client.get("/u/stage-name").text
    assert "Artist posts" in body
    assert "backstage warmup" in body
    assert 'src="https://signed/artist-images/stage-name/backstage.jpg?token=readtok"' in body
    assert "artist-reactions" in body
    assert "artist-comments" in body
    assert f'data-post-id="{post.id}"' in body
    assert "artistReact(this)" in body
    assert "toggleArtistComments(this)" in body
    assert f'aria-controls="artist-comment-panel-{post.id}"' in body
    assert f'id="artist-comment-status-{post.id}"' in body
    assert "/static/artist-engagement.js" in body
    assert "Artist-only engagement" not in body


# T104 regression: a TEXT-ONLY artist post (imageUrl None) on a profile renders as a note — NOT the
# muted "image unavailable" placeholder, which only belongs to a real-but-unsignable image (T103).
def test_artist_profile_text_only_post_has_no_image_box(client, db_session, monkeypatch):
    _ensure_artist_table(db_session)
    _seed_viewer(db_session)
    artist = User(handle="stage-name", display_name="Stage Name", is_artist=True,
                  created_at=datetime.now(timezone.utc))
    db_session.add(artist)
    db_session.commit()
    db_session.refresh(artist)
    db_session.add(ArtistPost(artist_user_id=artist.id, image_url=None, caption="just words"))
    db_session.commit()
    app.dependency_overrides[get_session] = lambda: db_session
    _login(client, monkeypatch)

    body = client.get("/u/stage-name").text
    assert "just words" in body                    # the caption renders as the note body
    assert "artist-post-note" in body              # the note styling is applied
    assert "artist-post-img-missing" not in body   # no placeholder image box for a text-only post
    assert "<img class=\"artist-post-img\"" not in body


def test_artist_profile_owner_sees_engagement_summary(client, db_session, monkeypatch):
    _ensure_artist_table(db_session)
    artist = _seed_artist(db_session)
    fan = User(handle="fan", display_name="Fan", created_at=datetime.now(timezone.utc))
    db_session.add(fan)
    db_session.commit()
    db_session.refresh(fan)
    post = ArtistPost(artist_user_id=artist.id, image_url="the-artist/x.jpg", caption="new clip")
    db_session.add(post)
    db_session.commit()
    db_session.refresh(post)
    db_session.add(ArtistReaction(artist_post_id=post.id, user_id=fan.id, type=ReactionType.HEART))
    db_session.add(ArtistComment(artist_post_id=post.id, user_id=fan.id, body="love this"))
    db_session.commit()
    monkeypatch.setattr(
        "app.routers.pages.create_signed_read_url_or_blank",
        lambda bucket, path: f"https://signed/{bucket}/{path}?token=readtok",
    )
    app.dependency_overrides[get_session] = lambda: db_session
    _login(client, monkeypatch)

    body = client.get("/u/the-artist").text
    assert "Artist-only engagement" in body
    assert "1 comments" in body
    assert ">1</span>" in body  # public reaction count and owner summary both reflect the heart


def test_non_artist_profile_has_no_artist_posts_section(client, db_session, monkeypatch):
    _seed_viewer(db_session)
    target = User(handle="listener", display_name="Listener", created_at=datetime.now(timezone.utc))
    db_session.add(target)
    db_session.commit()
    app.dependency_overrides[get_session] = lambda: db_session
    _login(client, monkeypatch)

    body = client.get("/u/listener").text
    assert "Artist posts" not in body
    assert "/static/artist-engagement.js" not in body


# ---- T44: profile listening summary + now-playing badge ----


def _seed_target_with_plays(db_session, handle="dj-nova"):
    # A user (not the viewer) with a couple of plays, so we can view THEIR profile and see the
    # listening summary. Track must be inserted before the Play that references it (FKs are on).
    target = User(handle=handle, display_name="DJ Nova", spotify_id="sp_nova",
                  created_at=datetime.now(timezone.utc))
    db_session.add(target)
    db_session.add(Track(spotify_id="t_pulse", title="Pulse", artist_name="Nova"))
    db_session.commit()
    db_session.refresh(target)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db_session.add(Play(user_id=target.id, track_id="t_pulse", played_at=now))
    db_session.commit()
    return target


def test_profile_shows_listening_summary(client, db_session, monkeypatch):
    _seed_viewer(db_session)
    _seed_target_with_plays(db_session)
    app.dependency_overrides[get_session] = lambda: db_session
    _login(client, monkeypatch)

    body = client.get("/u/dj-nova").text
    assert "Listening" in body
    assert "Pulse" in body            # the played track shows in top tracks / recent
    assert "day streak" in body
    assert "plays" in body


def test_own_profile_without_spotify_shows_link_prompt(client, db_session, monkeypatch):
    # The viewer (handle "viewer") has no linked Spotify and no plays -> link-Spotify prompt.
    _seed_viewer(db_session)
    # No Spotify token exists, so now-playing resolves to None without any network call; stub it
    # anyway to keep the test hermetic.
    monkeypatch.setattr("app.spotify.get_currently_playing", lambda s, u: None)
    app.dependency_overrides[get_session] = lambda: db_session
    _login(client, monkeypatch)

    body = client.get("/u/viewer").text
    assert "Link Spotify" in body
    assert 'href="/auth/login"' in body


def test_own_profile_shows_now_playing_badge(client, db_session, monkeypatch):
    _seed_viewer(db_session)
    # Pretend the viewer is currently playing a track (T20 shape: is_playing + normalized track).
    monkeypatch.setattr(
        "app.spotify.get_currently_playing",
        lambda s, u: {"is_playing": True,
                      "track": {"title": "Midnight", "artist_name": "Aurora",
                                "album_art_url": None}},
    )
    app.dependency_overrides[get_session] = lambda: db_session
    _login(client, monkeypatch)

    body = client.get("/u/viewer").text
    assert "Now playing" in body
    assert "Midnight" in body


def test_own_profile_ignores_now_playing_failure(client, db_session, monkeypatch):
    _seed_viewer(db_session)

    def boom(session, user_id):
        raise RuntimeError("spotify is having a bad day")

    monkeypatch.setattr("app.spotify.get_currently_playing", boom)
    app.dependency_overrides[get_session] = lambda: db_session
    _login(client, monkeypatch)

    res = client.get("/u/viewer")
    assert res.status_code == 200
    assert "Viewer" in res.text
    assert "Internal Server Error" not in res.text


def test_artist_profile_ignores_artist_engagement_read_failure(client, db_session, monkeypatch):
    _ensure_artist_table(db_session)
    _seed_viewer(db_session)
    artist = User(handle="stage-name", display_name="Stage Name", is_artist=True,
                  created_at=datetime.now(timezone.utc))
    db_session.add(artist)
    db_session.commit()
    db_session.refresh(artist)
    post = ArtistPost(artist_user_id=artist.id, image_url="stage-name/backstage.jpg",
                      caption="backstage warmup")
    db_session.add(post)
    db_session.commit()
    db_session.refresh(post)

    monkeypatch.setattr(
        "app.routers.pages.create_signed_read_url_or_blank",
        lambda bucket, path: f"https://signed/{bucket}/{path}?token=readtok",
    )
    real_exec = db_session.exec

    def flaky_exec(statement, *args, **kwargs):
        if "ArtistReaction" in str(statement) or "ArtistComment" in str(statement):
            raise RuntimeError("artist engagement tables unavailable")
        return real_exec(statement, *args, **kwargs)

    monkeypatch.setattr(db_session, "exec", flaky_exec)
    app.dependency_overrides[get_session] = lambda: db_session
    _login(client, monkeypatch)

    res = client.get("/u/stage-name")
    assert res.status_code == 200
    assert "backstage warmup" in res.text
    assert "Internal Server Error" not in res.text


def test_artist_profile_omits_image_when_signing_fails(client, db_session, monkeypatch):
    _ensure_artist_table(db_session)
    _seed_viewer(db_session)
    artist = User(handle="stage-name", display_name="Stage Name", is_artist=True,
                  created_at=datetime.now(timezone.utc))
    db_session.add(artist)
    db_session.commit()
    db_session.refresh(artist)
    db_session.add(ArtistPost(artist_user_id=artist.id, image_url="stage-name/backstage.jpg",
                              caption="backstage warmup"))
    db_session.commit()

    # Make the UNDERLYING signer raise so the real resilient wrapper (T103) is exercised: it should
    # swallow the error and return "", and the template then omits the <img>/shows a placeholder.
    def boom(bucket, path, expires_in=3600):
        raise RuntimeError("storage signing unavailable")

    monkeypatch.setattr("app.security.supabase.create_signed_read_url", boom)
    app.dependency_overrides[get_session] = lambda: db_session
    _login(client, monkeypatch)

    res = client.get("/u/stage-name")
    assert res.status_code == 200
    assert "backstage warmup" in res.text          # the post still renders (not a 500, not blank)
    assert 'src=""' not in res.text                # never a broken <img> with an empty src
    assert "artist-post-img-missing" in res.text   # the muted placeholder is shown instead


# ---- T51: artist page + upload UI ----


def _ensure_artist_table(db_session):
    # The shared db_session fixture only builds a few tables; the artist page also reads ArtistPost.
    ArtistPost.__table__.create(db_session.get_bind(), checkfirst=True)


def _seed_artist(db_session):
    # An artist account (is_artist=True) keyed to the login id, so require_user returns them.
    artist = User(supabase_user_id=_VIEWER_ID, handle="the-artist", display_name="The Artist",
                  is_artist=True, created_at=datetime.now(timezone.utc))
    db_session.add(artist)
    db_session.commit()
    db_session.refresh(artist)
    return artist


def test_artist_page_shows_upload_for_artist(client, db_session, monkeypatch):
    _ensure_artist_table(db_session)
    _seed_artist(db_session)
    app.dependency_overrides[get_session] = lambda: db_session
    _login(client, monkeypatch)

    body = client.get("/artist").text
    assert 'class="artist-file"' in body            # the file picker is shown
    assert "/static/artist-upload.js" in body       # the upload script is loaded
    # T104: the caption is now ALWAYS visible (a photo is optional — an artist can post text only),
    # so the box renders WITHOUT `hidden` (reverting the old T57 reveal-on-image behavior).
    assert 'class="artist-caption"' in body
    assert 'maxlength="2000" hidden' not in body
    assert "artistCaptionInput(this)" in body       # typing text alone can enable Share (T104)


# T104: the artist upload script can publish a TEXT-ONLY post — it enables Share on text alone and
# skips the image upload when no file is picked (imageUrl is only added when there's a file).
def test_artist_upload_script_supports_text_only(client):
    script = client.get("/static/artist-upload.js").text
    assert "artistCaptionInput" in script            # a caption alone can make the post shareable
    assert "if (_artistFile)" in script              # the image upload runs only when a file exists
    assert "body.imageUrl = path" in script          # imageUrl is set only inside that branch


def test_artist_page_hides_upload_for_non_artist(client, db_session, monkeypatch):
    _ensure_artist_table(db_session)
    _seed_viewer(db_session)  # a normal listener (is_artist defaults to False)
    app.dependency_overrides[get_session] = lambda: db_session
    _login(client, monkeypatch)

    body = client.get("/artist").text
    assert 'class="artist-file"' not in body        # no upload box for non-artists
    assert "Artist accounts only" in body
    assert 'href="/u/viewer"' in body


def test_artist_page_shows_existing_posts(client, db_session, monkeypatch):
    _ensure_artist_table(db_session)
    artist = _seed_artist(db_session)
    db_session.add(ArtistPost(artist_user_id=artist.id, image_url="the-artist/x.jpg",
                              caption="new EP out now"))
    db_session.commit()
    app.dependency_overrides[get_session] = lambda: db_session
    # The bucket is private, so the page must sign a READ url for each stored path (T53). Stub the
    # helper so no test hits Supabase — it just wraps the raw path into a recognisable signed URL.
    monkeypatch.setattr(
        "app.routers.pages.create_signed_read_url_or_blank",
        lambda bucket, path: f"https://signed/{bucket}/{path}?token=readtok",
    )
    _login(client, monkeypatch)

    body = client.get("/artist").text
    assert "new EP out now" in body


# The private artist bucket rejects unauthenticated GETs, so the page must render a SIGNED read URL
# for each post's stored path — never the raw path (which would show a broken image). T53.
def test_artist_page_signs_image_read_urls(client, db_session, monkeypatch):
    _ensure_artist_table(db_session)
    artist = _seed_artist(db_session)
    db_session.add(ArtistPost(artist_user_id=artist.id, image_url="the-artist/x.jpg",
                              caption="cover art"))
    db_session.commit()
    app.dependency_overrides[get_session] = lambda: db_session
    captured = {}

    def fake_sign(bucket, path):
        captured["bucket"] = bucket
        captured["path"] = path
        return "https://signed/read-url?token=readtok"

    monkeypatch.setattr("app.routers.pages.create_signed_read_url_or_blank", fake_sign)
    _login(client, monkeypatch)

    body = client.get("/artist").text
    # the helper was asked to sign the private bucket + the stored raw path
    assert captured == {"bucket": "artist-images", "path": "the-artist/x.jpg"}
    # the rendered <img> uses the signed URL, and the raw path is NOT emitted as an src
    assert 'src="https://signed/read-url?token=readtok"' in body
    assert 'src="the-artist/x.jpg"' not in body


# T103 resilience: the 2026-07-22 incident — a signing failure 500'd the whole artist page. Now the
# page must render (200) with a muted placeholder instead of crashing. We make the UNDERLYING signer
# raise so the real resilient wrapper handles it.
def test_artist_page_survives_signing_failure(client, db_session, monkeypatch):
    _ensure_artist_table(db_session)
    artist = _seed_artist(db_session)
    db_session.add(ArtistPost(artist_user_id=artist.id, image_url="the-artist/x.jpg",
                              caption="tour dates soon"))
    db_session.commit()
    app.dependency_overrides[get_session] = lambda: db_session

    def boom(bucket, path, expires_in=3600):
        raise RuntimeError("StorageApiError: Object not found")

    monkeypatch.setattr("app.security.supabase.create_signed_read_url", boom)
    _login(client, monkeypatch)

    res = client.get("/artist")
    assert res.status_code == 200                  # NOT the 500 from the incident
    assert "tour dates soon" in res.text           # the post still renders
    assert 'src=""' not in res.text                # never a broken <img>
    assert "artist-post-img-missing" in res.text   # the muted placeholder is shown instead


# ---- T47: authenticated nav (feed / my profile / artist studio / log out) ----
#
# The shared nav (base.html) shows the public landing nav when logged out, and the in-app
# nav (Feed / My profile / Log out, plus Artist studio for artists) when logged in. These
# tests exercise both variants via real pages, since the nav is rendered on every page.


def test_nav_logged_out_shows_landing_nav(client):
    # An anonymous visitor to the landing page sees the public nav: the "Log in with Spotify"
    # button and the in-page anchors — and NONE of the authenticated links.
    app.dependency_overrides[get_session] = lambda: MagicMock()
    body = client.get("/").text
    assert "Log in with Spotify" in body
    assert 'href="#features"' in body
    # No in-app links leak to a logged-out visitor.
    assert 'href="/feed"' not in body
    assert 'href="/auth/logout"' not in body


def test_nav_logged_in_shows_app_links(client, db_session, monkeypatch):
    # A signed-in NON-artist sees Feed, their own profile, and Log out — but not the artist link.
    viewer = _seed_viewer(db_session)  # handle "viewer", is_artist defaults to False
    app.dependency_overrides[get_session] = lambda: db_session
    _login(client, monkeypatch)

    body = client.get("/feed").text
    assert 'href="/feed"' in body
    assert f'href="/u/{viewer.handle}"' in body   # My profile → own handle
    assert 'href="/auth/logout"' in body
    assert "Artist studio" not in body            # not an artist
    # The logged-out call to action is gone once you're signed in.
    assert "Log in with Spotify" not in body


def test_nav_logged_in_shows_user_search(client, db_session, monkeypatch):
    # T46 puts "find people" in the shared authenticated nav, so every signed-in page can reach
    # profiles without hand-typing /u/<handle>. The API does the real auth/rate-limit work; this
    # page test only proves the shared nav renders and loads the browser script.
    _seed_viewer(db_session)
    app.dependency_overrides[get_session] = lambda: db_session
    _login(client, monkeypatch)

    body = client.get("/feed").text
    assert 'class="user-search"' in body
    assert 'placeholder="Find people"' in body
    assert "userSearch(this)" in body
    assert "/static/user-search.js" in body


def test_nav_logged_in_artist_shows_artist_studio(client, db_session, monkeypatch):
    # A signed-in ARTIST additionally sees the Artist studio link (/artist).
    _ensure_artist_table(db_session)
    _seed_artist(db_session)  # is_artist=True, handle "the-artist"
    app.dependency_overrides[get_session] = lambda: db_session
    _login(client, monkeypatch)

    body = client.get("/feed").text
    assert "Artist studio" in body
    assert 'href="/artist"' in body


def test_nav_logged_in_on_home_page(client, db_session, monkeypatch):
    # The public landing page ("/") also reflects the logged-in nav when a session cookie is
    # present, so a signed-in user who lands on "/" can still reach Feed / their profile / logout.
    _seed_viewer(db_session)
    app.dependency_overrides[get_session] = lambda: db_session
    _login(client, monkeypatch)

    body = client.get("/").text
    assert 'href="/feed"' in body
    assert 'href="/auth/logout"' in body


# ---- T96: the "Liked by X and N others" line renders on song cards ----


def test_feed_renders_liked_by_line(client, db_session, monkeypatch):
    viewer = _seed_viewer(db_session)
    other = User(handle="fan", display_name="Fan One", created_at=datetime.now(timezone.utc))
    db_session.add(other)
    db_session.add(Track(spotify_id="t_lb", title="Popular Song", artist_name="Artist"))
    db_session.commit()
    db_session.refresh(other)
    post = Post(user_id=viewer.id, track_id="t_lb", source=PostSource.MANUAL)
    db_session.add(post)
    db_session.commit()
    db_session.refresh(post)
    # Two reactions: the viewer's is older, Fan One's is the most recent.
    db_session.add(Reaction(post_id=post.id, user_id=viewer.id, type=ReactionType.HEART,
                            created_at=datetime(2026, 7, 22, 11, 0, 0)))
    db_session.add(Reaction(post_id=post.id, user_id=other.id, type=ReactionType.FIRE,
                            created_at=datetime(2026, 7, 22, 12, 0, 0)))
    db_session.commit()

    app.dependency_overrides[get_session] = lambda: db_session
    _login(client, monkeypatch)

    body = client.get("/feed").text
    assert "Liked by" in body
    assert "Fan One" in body            # the most recent reactor is named
    assert "and 1 other" in body        # 2 total reactions -> "and 1 other"
    assert "toggleReactors(this)" in body   # the line opens the reactors list
    assert "/static/liked-by.js" in body    # the script is loaded


# ---- T45: analytics page ----


def test_analytics_requires_login(client, db_session):
    app.dependency_overrides[get_session] = lambda: db_session
    res = client.get("/analytics", follow_redirects=False)
    assert res.status_code == 303
    assert res.headers["location"] == "/auth/login"


def test_analytics_page_renders_with_pending_states(client, db_session, monkeypatch):
    # No gold ModelMetrics/Cluster tables exist in the SQLite test DB, so _analytics_data
    # fail-safes to empty and both sections show their friendly "not ready yet" state — which
    # is exactly the pre-T34/T36 experience we want to verify renders (never a crash).
    _seed_viewer(db_session)
    app.dependency_overrides[get_session] = lambda: db_session
    _login(client, monkeypatch)

    res = client.get("/analytics")
    assert res.status_code == 200
    body = res.text
    assert "Taste communities" in body                     # clustering section present (pending state)
    assert "The sound of Brink" in body                    # T106: replaced the old popularity card
    assert "aren't ready yet" in body                      # clustering pending state
    assert "sound of Brink shows up here" in body          # sound-of-Brink pending state (no model yet)
    # T106: the "Which tribe are you in?" card lives inside the clustering block, so with no model
    # it correctly does NOT appear — the "Taste communities aren't ready" card covers that state.
    assert "Which tribe are you in?" not in body
    # Regression guard: a signed-in visitor must get the signed-in nav, not the logged-out
    # header. The route originally forgot to pass `viewer`, so the nav fell back to
    # Features/How it works/Sign in even though the analytics content rendered.
    assert 'href="/auth/logout"' in body         # "Log out" -> signed-in nav is present
    assert "Log in with Spotify" not in body     # logged-out header must NOT show here


def test_analytics_page_renders_rich_visuals(client, db_session, monkeypatch):
    # Exercise the POPULATED branch (communities + audio-DNA + the T106 "sound of Brink" card)
    # without needing the gold tables (which SQLite can't build) by faking _analytics_data's
    # output. This catches template bugs in the rich path that the pending-state test can't reach.
    _seed_viewer(db_session)
    fake = {
        "kmeans": {"silhouette": 0.16, "k": 2, "silhouette_pct": 16,
                   "silhouette_reading": "the tribes share a lot of taste"},
        "total_listeners": 1500,
        "total_listeners_display": "1,500",
        "communities": [
            {"id": "c1", "rank": 1, "label": "High Valence, High Danceability", "size": 1000,
             "size_display": "1,000", "share_pct": 66.7, "bar_pct": 100, "color": "#9d8df1",
             "features": [{"name": "danceability", "pct": 75}, {"name": "energy", "pct": 60}]},
            {"id": "c2", "rank": 2, "label": "Low Energy", "size": 500, "size_display": "500",
             "share_pct": 33.3, "bar_pct": 50, "color": "#f472b6", "features": []},
        ],
        # T106: the whole-app "sound of Brink" summary (mean of the tribes' audio DNA).
        "sound": [{"name": "danceability", "pct": 68}, {"name": "energy", "pct": 60}],
    }
    monkeypatch.setattr("app.routers.pages._analytics_data", lambda session: fake)
    # T106: place the signed-in viewer in the first community so the "Which tribe are you in?" card
    # renders its populated state. assign_cluster is the on-read T33 step the route calls per viewer.
    monkeypatch.setattr(
        "app.routers.pages.assign_cluster",
        lambda session, user_id: {"cluster": {"id": "c1", "label": "High Valence, High Danceability"},
                                  "coverage_pct": 42.0},
    )
    app.dependency_overrides[get_session] = lambda: db_session
    _login(client, monkeypatch)

    res = client.get("/analytics")
    assert res.status_code == 200
    body = res.text
    assert "2 music tribes" in body                          # hero uses real k
    assert "1,500" in body                                   # total listeners
    assert "High Valence, High Danceability" in body         # community label
    assert "Danceability" in body                            # audio-DNA feature label (capitalized)
    assert "the tribes share a lot of taste" in body         # silhouette reading
    # T106 — the viewer's own tribe card (populated state):
    assert "You're in" in body                               # viewer placed on the map
    assert "Your tribe's audio DNA" in body                  # their tribe's DNA rendered
    assert "42%" in body                                     # coverage line (rounded from 42.0)
    # T106 — the "sound of Brink" card:
    assert "The sound of Brink" in body
    assert 'href="/auth/logout"' in body                     # signed-in nav
