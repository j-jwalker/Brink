# WHAT THIS FILE IS
# Tests for T31's Kaggle ingest (analytics/ingest_kaggle.py): the bronze landing of
# the raw CSV + the silver join that fills in audio features on Track rows we
# already know about. We use a tiny CSV built on the fly (not the real ~1.2M-row
# dataset, which is gitignored and won't exist on another machine or in CI) and
# two disposable Track rows created just for this test, so the suite never
# rewrites real listening data in brink-dev.
#
# NOTE: bronze only lands rows that actually matched a Track we already know
# about — landing a raw copy of all ~1.2M Kaggle rows filled the database's
# disk in production, since the overwhelming majority never match anything.
# The full file remains the source of truth for training (T34 reads it
# directly); bronze is just a raw-provenance record of the matches we used.

import csv
import os
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text

from db import get_engine
from ingest_kaggle import run_ingest

# The columns of the real Kaggle CSV (tracks_features.csv) that ingest_kaggle.py
# actually reads. The real file has many more (name, artists, year, ...); only
# "id" + the ten kmeans audio features (T33: widened from the original 5 so a
# real user's taste vector is comparable to what T34 trained the model on)
# matter for the join, so the fixture sticks to those. Note: this dataset has no
# popularity column (unlike the earlier ~114k one T31 shipped with) —
# Track.popularity comes from live Spotify data captured at post/snapshot time
# instead, so the join must never touch it.
_CSV_FIELDS = [
    "id", "name", "danceability", "energy", "valence", "tempo", "loudness",
    "acousticness", "instrumentalness", "liveness", "speechiness", "mode",
]


def _insert_track(conn, spotify_id: str, popularity: int) -> None:
    conn.execute(
        text(
            'INSERT INTO silver."Track" ("spotifyId", title, "artistName", popularity) '
            "VALUES (:id, :title, :artist, :popularity)"
        ),
        {"id": spotify_id, "title": "Test Track", "artist": "Test Artist", "popularity": popularity},
    )


def _delete_track(conn, spotify_id: str) -> None:
    conn.execute(text('DELETE FROM silver."Track" WHERE "spotifyId" = :id'), {"id": spotify_id})


def _fetch_track(conn, spotify_id: str):
    return conn.execute(
        text(
            "SELECT danceability, energy, valence, tempo, loudness, "
            "acousticness, instrumentalness, liveness, speechiness, mode, "
            'popularity, "kaggleMatched" '
            'FROM silver."Track" WHERE "spotifyId" = :id'
        ),
        {"id": spotify_id},
    ).one()


def _write_fixture_csv(path: Path, matched_id: str) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_FIELDS)
        writer.writeheader()
        writer.writerow({
            "id": matched_id, "name": "Test Track", "danceability": "0.7",
            "energy": "0.6", "loudness": "-6.5", "tempo": "120.0", "valence": "0.8",
            "acousticness": "0.2", "instrumentalness": "0.05", "liveness": "0.15",
            "speechiness": "0.04", "mode": "1",
        })
        # A Kaggle row with no corresponding Track row — should land in bronze
        # but have nothing to join against.
        writer.writerow({
            "id": "kaggle_only_" + uuid.uuid4().hex, "name": "Unheard", "danceability": "0.1",
            "energy": "0.1", "loudness": "-20.0", "tempo": "80.0", "valence": "0.1",
            "acousticness": "0.9", "instrumentalness": "0.8", "liveness": "0.7",
            "speechiness": "0.06", "mode": "0",
        })


@pytest.mark.skipif(
    os.getenv("RUN_ANALYTICS_DB_TESTS") != "1",
    reason="live Supabase analytics DB check; set RUN_ANALYTICS_DB_TESTS=1 to run",
)
def test_join_sets_features_and_leaves_unmatched_alone(tmp_path):
    engine = get_engine()
    matched_id = "test_matched_" + uuid.uuid4().hex
    unmatched_id = "test_unmatched_" + uuid.uuid4().hex
    csv_path = tmp_path / "kaggle_sample.csv"
    _write_fixture_csv(csv_path, matched_id)

    with engine.begin() as conn:
        _insert_track(conn, matched_id, popularity=55)
        _insert_track(conn, unmatched_id, popularity=10)

    try:
        summary = run_ingest(csv_path, engine=engine)

        with engine.connect() as conn:
            matched_row = _fetch_track(conn, matched_id)
            unmatched_row = _fetch_track(conn, unmatched_id)

        assert matched_row.danceability == 0.7
        assert matched_row.energy == 0.6
        assert matched_row.valence == 0.8
        assert matched_row.tempo == 120.0
        assert matched_row.loudness == -6.5
        # T33: the remaining 5 kmeans features must be joined too, not just T31's
        # original 5 — otherwise a real user's vector can't be built in the same
        # feature space the model was trained on.
        assert matched_row.acousticness == 0.2
        assert matched_row.instrumentalness == 0.05
        assert matched_row.liveness == 0.15
        assert matched_row.speechiness == 0.04
        assert matched_row.mode == 1.0
        assert matched_row.kaggleMatched is True
        # This dataset has no popularity column — the join must never touch it,
        # since the real value already comes from live Spotify data.
        assert matched_row.popularity == 55

        # A Track that exists but has no row in the Kaggle CSV must stay
        # unmatched — the on-read fallback for these is built by T33, not this file.
        assert unmatched_row.kaggleMatched is False
        assert unmatched_row.popularity == 10

        assert summary["matched"] >= 1
        assert summary["coverage_pct"] > 0

        # Coverage % is reported, not silently dropped (ADR-0004).
        assert isinstance(summary["coverage_pct"], float)

        # Bronze only keeps the rows that actually matched a Track we know
        # about — the unmatched "kaggle_only_..." row must never land there.
        with engine.connect() as conn:
            bronze_ids = [
                row[0]
                for row in conn.execute(
                    text("SELECT payload->>'id' FROM bronze.kaggle_tracks_raw")
                ).fetchall()
            ]
        assert bronze_ids == [matched_id]
    finally:
        with engine.begin() as conn:
            _delete_track(conn, matched_id)
            _delete_track(conn, unmatched_id)


@pytest.mark.skipif(
    os.getenv("RUN_ANALYTICS_DB_TESTS") != "1",
    reason="live Supabase analytics DB check; set RUN_ANALYTICS_DB_TESTS=1 to run",
)
def test_coverage_is_cumulative_across_runs(tmp_path):
    # A track matched by an earlier ingest (e.g. against a since-replaced
    # Kaggle file) keeps its kaggleMatched=true and real feature values even
    # though it's absent from *this* run's CSV. Coverage must count it too —
    # reporting only "matched by this run" would understate the database's
    # true, cumulative state (ADR-0004: coverage reported honestly).
    engine = get_engine()
    already_matched_id = "test_already_matched_" + uuid.uuid4().hex
    new_matched_id = "test_new_matched_" + uuid.uuid4().hex
    csv_path = tmp_path / "kaggle_sample.csv"
    _write_fixture_csv(csv_path, new_matched_id)

    with engine.begin() as conn:
        _insert_track(conn, already_matched_id, popularity=20)
        conn.execute(
            text(
                'UPDATE silver."Track" SET danceability = 0.5, energy = 0.5, '
                'valence = 0.5, tempo = 100.0, loudness = -10.0, '
                '"kaggleMatched" = true WHERE "spotifyId" = :id'
            ),
            {"id": already_matched_id},
        )
        _insert_track(conn, new_matched_id, popularity=55)

    try:
        summary = run_ingest(csv_path, engine=engine)
        assert summary["matched"] >= 2

        with engine.connect() as conn:
            still_matched = _fetch_track(conn, already_matched_id)
        assert still_matched.kaggleMatched is True
        assert still_matched.danceability == 0.5
    finally:
        with engine.begin() as conn:
            _delete_track(conn, already_matched_id)
            _delete_track(conn, new_matched_id)


@pytest.mark.skipif(
    os.getenv("RUN_ANALYTICS_DB_TESTS") != "1",
    reason="live Supabase analytics DB check; set RUN_ANALYTICS_DB_TESTS=1 to run",
)
def test_ingest_is_idempotent(tmp_path):
    engine = get_engine()
    matched_id = "test_idempotent_" + uuid.uuid4().hex
    csv_path = tmp_path / "kaggle_sample.csv"
    _write_fixture_csv(csv_path, matched_id)

    with engine.begin() as conn:
        _insert_track(conn, matched_id, popularity=55)

    try:
        first = run_ingest(csv_path, engine=engine)
        second = run_ingest(csv_path, engine=engine)

        assert first == second

        with engine.connect() as conn:
            bronze_count = conn.execute(
                text("SELECT COUNT(*) FROM bronze.kaggle_tracks_raw")
            ).scalar()
        # Re-running must not accumulate duplicate raw rows — the bronze
        # landing table always mirrors just the latest ingest's matches.
        # Only 1, not 2: the unmatched "kaggle_only_..." row in the fixture
        # never lands in bronze at all.
        assert bronze_count == 1
    finally:
        with engine.begin() as conn:
            _delete_track(conn, matched_id)
