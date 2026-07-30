# WHAT THIS FILE IS
# Tests for T14: the analytics layer on the profile page — the taste CLUSTER label and the
# COMPATIBILITY score vs the person viewing the page. The heavy lifting lives in the T33/T35
# inference core (app/inference/*); T14 only wires it into _profile_data + the template.
#
# WHY the "no analytics" path is the important one to test against SQLite: the shared db_session
# fixture deliberately omits the gold tables (Cluster/ModelArtifact use Postgres-only JSONB —
# see conftest.py / test_inference.py). So in these tests the real inference calls always hit
# their graceful "model store missing" branch and return null. That is exactly the contract T14
# must uphold — a profile with no trained model still renders (200), never 500s. The POPULATED
# path is exercised by monkeypatching the two inference functions to return fixed values, so we
# prove the wiring (and the "hide compatibility on your own profile" rule) without a real model.

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.db import get_session
from app.main import app
from app.routers import pages
from app.routers.pages import _profile_data
from app.models import Play, Track, User
from app.security import session as login_session
from app.security import supabase

_VIEWER_SUPA_ID = "abcdef12-3456-7890-abcd-ef1234567890"


def _login(client, monkeypatch):
    su = SimpleNamespace(id=_VIEWER_SUPA_ID, email=None, user_metadata={}, app_metadata={})
    monkeypatch.setattr(login_session, "decode", lambda raw: {"access_token": "AT", "refresh_token": "RT"})
    monkeypatch.setattr(supabase, "get_user_from_token", lambda t: su if t == "AT" else None)
    client.cookies.set(login_session.SESSION_COOKIE, "x")


def _seed_user(session, uid, handle, supabase_user_id=None):
    user = User(
        id=uid, handle=handle, display_name=handle,
        supabase_user_id=supabase_user_id, created_at=datetime.now(timezone.utc),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _seed_play(session, uid, spotify_id):
    session.add(Track(spotify_id=spotify_id, title=spotify_id, artist_name="Artist"))
    session.commit()
    session.add(Play(user_id=uid, track_id=spotify_id, played_at=datetime.now(timezone.utc)))
    session.commit()


# ---- Graceful empty: no trained model (gold tables absent in SQLite) -> null, never a crash ----


def test_profile_data_null_analytics_without_model(db_session):
    viewer = _seed_user(db_session, "v1", "viewer")
    _seed_user(db_session, "p1", "person")
    _seed_play(db_session, "p1", "t1")

    data = _profile_data(db_session, "person", viewer_id=viewer.id)

    assert data is not None
    assert data["taste_cluster"] is None
    assert data["compatibility"] is None


# ---- Populated: a trained model exists -> cluster label + compatibility surface on the page ----


def test_profile_data_surfaces_cluster_and_compatibility(db_session, monkeypatch):
    viewer = _seed_user(db_session, "v1", "viewer")
    _seed_user(db_session, "p1", "person")

    monkeypatch.setattr(
        pages, "assign_cluster",
        lambda session, uid: {"cluster": {"id": "c1", "label": "Indie Explorers"}, "coverage_pct": 80.0},
    )
    monkeypatch.setattr(pages, "compatibility", lambda session, a, b: 0.73)

    data = _profile_data(db_session, "person", viewer_id=viewer.id)

    assert data["taste_cluster"] == {"id": "c1", "label": "Indie Explorers"}
    assert data["compatibility"] == 0.73


# ---- Compatibility with yourself is meaningless (~100%); it is NOT shown on your own profile ----


def test_compatibility_hidden_on_own_profile(db_session, monkeypatch):
    viewer = _seed_user(db_session, "v1", "viewer")

    # Even if the inference core WOULD return a value, viewing your own profile must not call it.
    monkeypatch.setattr(
        pages, "assign_cluster",
        lambda session, uid: {"cluster": {"id": "c1", "label": "Indie Explorers"}, "coverage_pct": 80.0},
    )
    monkeypatch.setattr(pages, "compatibility", lambda session, a, b: 0.99)

    data = _profile_data(db_session, "viewer", viewer_id=viewer.id)

    assert data["is_self"] is True
    assert data["compatibility"] is None          # not vs yourself
    assert data["taste_cluster"] is not None       # but your own cluster still shows


# ---- Full HTTP path: the rendered profile page shows the cluster label + compatibility % ----


def test_profile_page_renders_taste_block(client, db_session, monkeypatch):
    _login(client, monkeypatch)
    # The viewer must resolve via supabase_user_id (that's who require_user returns).
    _seed_user(db_session, "v1", "viewer", supabase_user_id=_VIEWER_SUPA_ID)
    _seed_user(db_session, "p1", "person")

    monkeypatch.setattr(
        pages, "assign_cluster",
        lambda session, uid: {"cluster": {"id": "c1", "label": "Indie Explorers"}, "coverage_pct": 80.0},
    )
    monkeypatch.setattr(pages, "compatibility", lambda session, a, b: 0.73)
    app.dependency_overrides[get_session] = lambda: db_session

    try:
        body = client.get("/u/person").text
    finally:
        app.dependency_overrides.clear()

    assert "Indie Explorers" in body
    assert "73%" in body
    assert "compatible with your taste" in body


# A profile with no trained model renders (200) and simply omits the taste block — never 500s.
def test_profile_page_ok_without_analytics(client, db_session, monkeypatch):
    _login(client, monkeypatch)
    _seed_user(db_session, "v1", "viewer", supabase_user_id=_VIEWER_SUPA_ID)
    _seed_user(db_session, "p1", "person")
    app.dependency_overrides[get_session] = lambda: db_session

    try:
        res = client.get("/u/person")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    assert "compatible with your taste" not in res.text
