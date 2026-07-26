# WHAT THIS FILE IS
# Tests for T32's synthetic user seeding (analytics/seed_users.py). The pure
# helpers (matching clusters to centroids, picking nearest tracks, splitting
# users evenly across personas, spreading play timestamps) are tested with
# small synthetic data, no database needed. The one test that writes to the
# database (test_run_seed_writes_and_is_idempotent) touches "User",
# silver."Track", and gold."Cluster"/"ModelArtifact" — real tables shared with
# production (brink-dev) — so it snapshots+restores the gold tables (reusing
# test_cluster.py's helpers, since seed_users.py reads the same well-known
# "kmeans" artifact T34 writes) and only ever creates obviously-fake
# "synth-listener-..." / "test-seed-..." rows, cleaned up in a `finally`
# block — the same pattern test_ingest_kaggle.py and test_cluster.py use.

import os
import uuid
from datetime import datetime, timezone

import numpy as np
import pytest
from sqlalchemy import text

from db import get_engine
from seed_users import (
    build_persona_pools,
    load_track_catalog,
    match_clusters_to_centroids,
    nearest_indices,
    run_seed,
    spread_play_timestamps,
    split_evenly,
    standardize_matrix,
)
from test_cluster import _restore_gold_tables, _snapshot_gold_tables

FEATURE_ORDER = [
    "danceability", "energy", "valence", "tempo", "loudness",
    "acousticness", "instrumentalness", "liveness", "speechiness", "mode",
]


def test_standardize_matrix_applies_zscore():
    X = np.array([[1.0, 10.0], [3.0, 30.0]])
    mean = [2.0, 20.0]
    std = [1.0, 10.0]

    scaled = standardize_matrix(X, mean, std)

    assert scaled.tolist() == [[-1.0, -1.0], [1.0, 1.0]]


def test_nearest_indices_excludes_claimed_and_returns_closest_n():
    X_scaled = np.array([
        [0.0, 0.0],   # 0: closest to origin
        [0.1, 0.0],   # 1: second closest
        [5.0, 5.0],   # 2: far
        [0.2, 0.0],   # 3: third closest, but excluded
    ])
    centroid = np.array([0.0, 0.0])

    result = nearest_indices(X_scaled, centroid, exclude={3}, n=2)

    assert result == [0, 1]


def test_match_clusters_to_centroids_pairs_by_nearest_standardized_point():
    # Two well-separated clusters; gold.Cluster stores centroids in ORIGINAL
    # units, gold.ModelArtifact stores them STANDARDIZED — pairing must find
    # the right correspondence even though the two representations differ.
    mean = [5.0, 5.0]
    std = [1.0, 1.0]
    centroids_scaled = [[-5.0, -5.0], [5.0, 5.0]]  # standardized, in artifact order
    clusters = [
        {"id": "cluster-b", "label": "High", "centroid": {"danceability": 10.0, "energy": 10.0}},
        {"id": "cluster-a", "label": "Low", "centroid": {"danceability": 0.0, "energy": 0.0}},
    ]

    matched = match_clusters_to_centroids(
        clusters, centroids_scaled, mean, std, ["danceability", "energy"]
    )

    by_id = {m["cluster_id"]: m["centroid_scaled"].tolist() for m in matched}
    assert by_id["cluster-b"] == [5.0, 5.0]
    assert by_id["cluster-a"] == [-5.0, -5.0]


def test_match_clusters_to_centroids_raises_on_ambiguous_double_match():
    # If gold.Cluster and gold.ModelArtifact ever disagree (stale data from
    # different training runs), two clusters resolving to the same centroid
    # is a real bug, not something to silently paper over.
    mean = [0.0]
    std = [1.0]
    centroids_scaled = [[0.0], [10.0]]
    clusters = [
        {"id": "a", "label": "A", "centroid": {"danceability": 0.5}},
        {"id": "b", "label": "B", "centroid": {"danceability": 0.4}},
    ]

    with pytest.raises(ValueError):
        match_clusters_to_centroids(clusters, centroids_scaled, mean, std, ["danceability"])


def test_load_track_catalog_reads_ids_titles_artists_and_features(tmp_path):
    csv_path = tmp_path / "tracks.csv"
    csv_path.write_text(
        "id,name,artists,danceability,energy,valence,tempo,loudness,"
        "acousticness,instrumentalness,liveness,speechiness,mode\n"
        "t1,Testify,\"['Rage Against The Machine']\",0.47,0.978,0.503,117.9,-5.4,"
        "0.026,0.0,0.356,0.073,1\n"
        "t2,Two Artists,\"['A', 'B']\",0.5,0.5,0.5,120.0,-6.0,0.1,0.1,0.1,0.1,0\n",
        encoding="utf-8",
    )

    ids, titles, artists, X = load_track_catalog(csv_path, FEATURE_ORDER)

    assert ids == ["t1", "t2"]
    assert titles == ["Testify", "Two Artists"]
    assert artists == ["Rage Against The Machine", "A"]
    assert X.shape == (2, 10)
    assert X[0].tolist() == [0.47, 0.978, 0.503, 117.9, -5.4, 0.026, 0.0, 0.356, 0.073, 1.0]


def test_build_persona_pools_shares_one_pool_per_cluster_with_no_overlap(tmp_path):
    csv_path = tmp_path / "tracks.csv"
    feature_order = [f"f{i}" for i in range(9)]
    header = "id,name,artists," + ",".join(feature_order)
    lines = [header]
    # 5 tracks near all-0.1, 5 tracks near all-9.9 in the 9-feature space.
    for i in range(5):
        lines.append(f"low{i},Low {i},['Artist']," + ",".join(["0.1"] * 9))
    for i in range(5):
        lines.append(f"high{i},High {i},['Artist']," + ",".join(["9.9"] * 9))
    csv_path.write_text("\n".join(lines), encoding="utf-8")

    matched = [
        {"cluster_id": "low-cluster", "label": "Low", "centroid_scaled": np.full(9, 0.1)},
        {"cluster_id": "high-cluster", "label": "High", "centroid_scaled": np.full(9, 9.9)},
    ]
    # scaler mean/std of identity (0/1) so "standardized" == raw values here.
    pools = build_persona_pools(
        csv_path, matched, feature_order, [0.0] * 9, [1.0] * 9,
        exclude_ids=set(), pool_size=3,
    )

    assert set(pools.keys()) == {"low-cluster", "high-cluster"}
    assert len(pools["low-cluster"]) == 3
    assert len(pools["high-cluster"]) == 3
    low_ids = {row["spotify_id"] for row in pools["low-cluster"]}
    high_ids = {row["spotify_id"] for row in pools["high-cluster"]}
    assert low_ids.issubset({f"low{i}" for i in range(5)})
    assert high_ids.issubset({f"high{i}" for i in range(5)})
    assert low_ids.isdisjoint(high_ids)


def test_build_persona_pools_excludes_already_known_track_ids(tmp_path):
    csv_path = tmp_path / "tracks.csv"
    feature_order = ["f0"]
    lines = ["id,name,artists,f0", "a,A,['X'],0.0", "b,B,['X'],0.0"]
    csv_path.write_text("\n".join(lines), encoding="utf-8")

    matched = [{"cluster_id": "only-cluster", "label": "Only", "centroid_scaled": np.array([0.0])}]
    pools = build_persona_pools(
        csv_path, matched, feature_order, [0.0], [1.0], exclude_ids={"a"}, pool_size=5,
    )

    assert [row["spotify_id"] for row in pools["only-cluster"]] == ["b"]


def test_split_evenly_distributes_remainder_to_first_buckets():
    assert split_evenly(50, 7) == [8, 7, 7, 7, 7, 7, 7]
    assert sum(split_evenly(50, 7)) == 50
    assert split_evenly(21, 7) == [3, 3, 3, 3, 3, 3, 3]


def test_spread_play_timestamps_covers_multiple_distinct_days_with_no_duplicates():
    import random
    rng = random.Random(1)
    now = datetime(2026, 7, 23, tzinfo=timezone.utc)

    timestamps = spread_play_timestamps(20, 10, lookback_days=30, rng=rng, now=now)

    assert len(timestamps) == 20
    assert len(set(timestamps)) == 20  # no duplicate playedAt instants
    distinct_days = {ts.date() for ts in timestamps}
    assert len(distinct_days) == 10
    for ts in timestamps:
        assert (now - ts).days <= 30


def _fixture_cluster_rows(now):
    return [
        {
            "id": "test-seed-cluster-low", "label": "Test Low", "size": 20, "computedAt": now,
            "centroid": {f: 0.15 for f in FEATURE_ORDER},
        },
        {
            "id": "test-seed-cluster-high", "label": "Test High", "size": 20, "computedAt": now,
            "centroid": {f: 0.85 for f in FEATURE_ORDER},
        },
    ]


def _insert_fixture_gold(conn, now):
    import json

    conn.execute(
        text(
            'INSERT INTO gold."Cluster" (id, label, centroid, size, "computedAt") '
            'VALUES (:id, :label, CAST(:centroid AS JSONB), :size, :computedAt)'
        ),
        [{**row, "centroid": json.dumps(row["centroid"])} for row in _fixture_cluster_rows(now)],
    )
    conn.execute(
        text(
            'INSERT INTO gold."ModelArtifact" '
            "(model_name, feature_order, scaler_mean, scaler_std, params, computed_at) "
            "VALUES ('kmeans', CAST(:feature_order AS JSONB), CAST(:scaler_mean AS JSONB), "
            "CAST(:scaler_std AS JSONB), CAST(:params AS JSONB), :computed_at)"
        ),
        {
            "feature_order": json.dumps(FEATURE_ORDER),
            "scaler_mean": json.dumps([0.0] * 10),
            "scaler_std": json.dumps([1.0] * 10),
            "params": json.dumps({"centroids": [[0.15] * 10, [0.85] * 10]}),
            "computed_at": now,
        },
    )


@pytest.mark.skipif(
    os.getenv("RUN_ANALYTICS_DB_TESTS") != "1",
    reason="live Supabase analytics DB check; set RUN_ANALYTICS_DB_TESTS=1 to run",
)
def test_run_seed_writes_and_is_idempotent(tmp_path):
    engine = get_engine()
    run_id = uuid.uuid4().hex[:8]
    csv_path = tmp_path / "tracks.csv"
    header = "id,name,artists," + ",".join(FEATURE_ORDER)
    lines = [header]
    # Two tight, well-separated blobs matching the two fixture cluster centroids.
    for i in range(10):
        lines.append(f"test-seed-{run_id}-low-{i},Low Track {i},['Test Artist']," + ",".join(["0.15"] * 10))
    for i in range(10):
        lines.append(f"test-seed-{run_id}-high-{i},High Track {i},['Test Artist']," + ",".join(["0.85"] * 10))
    csv_path.write_text("\n".join(lines), encoding="utf-8")

    now = datetime.now(timezone.utc)
    with engine.begin() as conn:
        original = _snapshot_gold_tables(conn)
        conn.execute(text('DELETE FROM gold."Cluster"'))
        conn.execute(text('DELETE FROM gold."ModelArtifact" WHERE model_name = :n'), {"n": "kmeans"})
        _insert_fixture_gold(conn, now)

    try:
        first = run_seed(csv_path, engine=engine, total_users=6, pool_size=5, seed=7)
        second = run_seed(csv_path, engine=engine, total_users=6, pool_size=5, seed=7)

        assert first["users_created"] == 6
        assert first["tracks_inserted"] == 10  # 2 personas x pool_size=5
        assert second["users_created"] == 0  # idempotent: all 6 already exist
        assert second["tracks_inserted"] == 0  # pool already seeded, ON CONFLICT DO NOTHING

        with engine.connect() as conn:
            users = conn.execute(
                text('SELECT id, "isSynthetic" FROM "User" WHERE handle LIKE :p'),
                {"p": "synth-listener-%"},
            ).mappings().all()
        assert len(users) == 6
        assert all(u["isSynthetic"] for u in users)

        user_ids = [u["id"] for u in users]
        with engine.connect() as conn:
            play_counts = conn.execute(
                text(
                    'SELECT "userId", COUNT(*) c FROM silver."Play" '
                    'WHERE "userId" = ANY(:ids) GROUP BY "userId"'
                ),
                {"ids": user_ids},
            ).mappings().all()
        # Every seeded user has plays, and re-running did not add a second
        # batch on top (each user still has exactly one batch of plays).
        assert len(play_counts) == len(user_ids)
        assert all(15 <= row["c"] <= 25 for row in play_counts)
    finally:
        with engine.begin() as conn:
            conn.execute(
                text(
                    'DELETE FROM silver."Play" WHERE "userId" IN '
                    '(SELECT id FROM "User" WHERE handle LIKE :p)'
                ),
                {"p": "synth-listener-%"},
            )
            conn.execute(text('DELETE FROM "User" WHERE handle LIKE :p'), {"p": "synth-listener-%"})
            conn.execute(
                text('DELETE FROM silver."Track" WHERE "spotifyId" LIKE :p'),
                {"p": f"test-seed-{run_id}-%"},
            )
            _restore_gold_tables(conn, original)
