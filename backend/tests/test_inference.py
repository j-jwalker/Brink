# WHAT THIS FILE IS
# Tests for T33's on-demand inference core: app/inference/taste_vector.py (build a user's
# taste vector from their played/posted tracks) and app/inference/assign.py (standardize
# it and assign the nearest gold.Cluster). WHY split this way: taste_vector.py only touches
# Play/Post/Track, which are plain SQLite-friendly tables, so its tests drive a real
# in-memory DB (the shared db_session fixture) like test_stats.py does. assign.py's math
# (standardize, nearest-cluster) is tested as pure functions on plain data — no DB needed —
# because ModelArtifact/Cluster use Postgres-only JSONB columns that SQLite can't build
# (see conftest.py's db_session, which deliberately excludes the gold tables for the same
# reason). The one thing that DOES touch those tables, assign_cluster()'s graceful "not
# ready yet" path, is tested against db_session precisely BECAUSE those tables are absent
# there — the same "gold schema missing" case pages.py's _analytics_data already guards.

from datetime import datetime, timedelta, timezone

from app.inference.assign import assign_cluster, nearest_cluster_label, standardize
from app.inference.taste_vector import build_taste_vector
from app.models import Cluster, Play, Post, PostSource, Track, User

_FEATURE_ORDER = [
    "danceability", "energy", "valence", "tempo", "loudness",
    "acousticness", "instrumentalness", "liveness", "speechiness", "mode",
]
_CORPUS_MEAN = [0.5, 0.5, 0.5, 120.0, -10.0, 0.5, 0.5, 0.5, 0.5, 0.5]


def _seed_user(session, uid="u1"):
    session.add(User(id=uid, handle=uid, display_name=uid, created_at=datetime.now(timezone.utc)))
    session.commit()


def _seed_matched_track(session, spotify_id, values):
    # A track with all 10 kmeans features present — what a real Kaggle-matched, fully
    # backfilled row looks like (T33's join, on top of T31's original 5).
    session.add(Track(
        spotify_id=spotify_id, title=spotify_id, artist_name="Artist",
        kaggle_matched=True, **dict(zip(_FEATURE_ORDER, values)),
    ))
    session.commit()


def _seed_unmatched_track(session, spotify_id):
    # Never matched a Kaggle row — every feature column stays NULL.
    session.add(Track(spotify_id=spotify_id, title=spotify_id, artist_name="Artist"))
    session.commit()


_play_offset = 0


def _play(session, uid, track_id):
    # The unique (userId, playedAt) index means two plays in the same test need distinct
    # timestamps — a bare datetime.now() twice in a row can collide at this precision.
    global _play_offset
    _play_offset += 1
    when = datetime.now(timezone.utc) + timedelta(seconds=_play_offset)
    session.add(Play(user_id=uid, track_id=track_id, played_at=when))
    session.commit()


def _post(session, uid, track_id):
    session.add(Post(user_id=uid, track_id=track_id, source=PostSource.MANUAL))
    session.commit()


# ---- taste_vector.build_taste_vector (real SQLite DB — Track/Play/Post are schema-plain) ----


def test_no_tracks_returns_none(db_session):
    _seed_user(db_session)
    assert build_taste_vector(db_session, "u1", _FEATURE_ORDER, _CORPUS_MEAN) is None


def test_single_matched_track_returns_its_own_vector(db_session):
    _seed_user(db_session)
    values = [0.7, 0.6, 0.8, 120.0, -6.5, 0.2, 0.05, 0.15, 0.04, 1.0]
    _seed_matched_track(db_session, "t1", values)
    _play(db_session, "u1", "t1")

    result = build_taste_vector(db_session, "u1", _FEATURE_ORDER, _CORPUS_MEAN)

    assert result["vector"] == values
    assert result["coverage_pct"] == 100.0
    assert result["track_count"] == 1


def test_unmatched_track_falls_back_to_corpus_mean(db_session):
    # C4 fallback (ADR-0004): no genre field exists anywhere in the pipeline to build a
    # "genre-only" vector from (T32 hit the same gap), so an unmatched track's stand-in is
    # the training corpus's own mean point.
    _seed_user(db_session)
    _seed_unmatched_track(db_session, "t1")
    _play(db_session, "u1", "t1")

    result = build_taste_vector(db_session, "u1", _FEATURE_ORDER, _CORPUS_MEAN)

    assert result["vector"] == _CORPUS_MEAN
    assert result["coverage_pct"] == 0.0
    assert result["track_count"] == 1


def test_partially_backfilled_track_counts_as_unmatched(db_session):
    # A track flagged kaggleMatched=True by an ingest run BEFORE T33 widened Track's schema
    # still has NULLs in the 5 new columns until ingest is re-run. Averaging a None would
    # crash, so completeness (all 10 features present), not the flag alone, decides coverage.
    _seed_user(db_session)
    session = db_session
    session.add(Track(
        spotify_id="t1", title="t1", artist_name="Artist", kaggle_matched=True,
        danceability=0.7, energy=0.6, valence=0.8, tempo=120.0, loudness=-6.5,
        # acousticness/instrumentalness/liveness/speechiness/mode left NULL on purpose.
    ))
    session.commit()
    _play(session, "u1", "t1")

    result = build_taste_vector(session, "u1", _FEATURE_ORDER, _CORPUS_MEAN)

    assert result["vector"] == _CORPUS_MEAN
    assert result["coverage_pct"] == 0.0


def test_mean_averages_matched_and_fallback_tracks(db_session):
    _seed_user(db_session)
    matched_values = [1.0, 1.0, 1.0, 200.0, 0.0, 1.0, 1.0, 1.0, 1.0, 1.0]
    _seed_matched_track(db_session, "t_matched", matched_values)
    _seed_unmatched_track(db_session, "t_unmatched")
    _play(db_session, "u1", "t_matched")
    _play(db_session, "u1", "t_unmatched")

    result = build_taste_vector(db_session, "u1", _FEATURE_ORDER, _CORPUS_MEAN)

    expected = [(m + c) / 2 for m, c in zip(matched_values, _CORPUS_MEAN)]
    assert result["vector"] == expected
    assert result["coverage_pct"] == 50.0
    assert result["track_count"] == 2


def test_posted_and_played_tracks_are_unioned_without_duplication(db_session):
    _seed_user(db_session)
    values = [0.7, 0.6, 0.8, 120.0, -6.5, 0.2, 0.05, 0.15, 0.04, 1.0]
    _seed_matched_track(db_session, "t1", values)
    _play(db_session, "u1", "t1")
    _post(db_session, "u1", "t1")  # same track, shared via a post too — must count once

    result = build_taste_vector(db_session, "u1", _FEATURE_ORDER, _CORPUS_MEAN)

    assert result["track_count"] == 1


def test_text_only_post_has_no_track_and_is_ignored(db_session):
    # T104: a post can be text-only (trackId NULL) — must not blow up the union.
    _seed_user(db_session)
    session = db_session
    session.add(Post(user_id="u1", track_id=None, caption="just words", source=PostSource.MANUAL))
    session.commit()

    assert build_taste_vector(session, "u1", _FEATURE_ORDER, _CORPUS_MEAN) is None


# ---- assign.standardize / nearest_cluster_label (pure functions, no DB) ----


def test_standardize_applies_zscore_in_feature_order():
    vector = [10.0, 20.0]
    mean = [5.0, 25.0]
    std = [5.0, 10.0]
    assert standardize(vector, mean, std) == [1.0, -0.5]


def test_standardize_zero_std_contributes_zero_not_a_crash():
    vector = [3.0]
    mean = [3.0]
    std = [0.0]
    assert standardize(vector, mean, std) == [0.0]


def _cluster(cluster_id, label, centroid):
    return Cluster(id=cluster_id, label=label, centroid=centroid, size=1, computed_at=datetime.now(timezone.utc))


def test_nearest_cluster_label_picks_the_closest_centroid():
    feature_order = ["a", "b"]
    mean = [0.0, 0.0]
    std = [1.0, 1.0]
    near = _cluster("c_near", "Near", {"a": 1.0, "b": 1.0})
    far = _cluster("c_far", "Far", {"a": 10.0, "b": 10.0})

    standardized_vector = standardize([1.1, 1.1], mean, std)
    result = nearest_cluster_label(standardized_vector, [near, far], feature_order, mean, std)

    assert result.id == "c_near"


def test_nearest_cluster_label_empty_list_returns_none():
    assert nearest_cluster_label([0.0], [], ["a"], [0.0], [1.0]) is None


# ---- assign.assign_cluster (orchestration) ----


def test_assign_cluster_degrades_when_gold_schema_is_unavailable(db_session):
    # db_session (conftest.py) deliberately never creates ModelArtifact/Cluster — they use
    # Postgres-only JSONB columns SQLite can't build. That's exactly the "gold schema
    # missing" case (e.g. local dev without the medallion schemas) this must degrade for,
    # the same case pages.py's _analytics_data already guards for T45. Must never raise.
    _seed_user(db_session)
    result = assign_cluster(db_session, "u1")
    assert result == {"cluster": None, "coverage_pct": None}
