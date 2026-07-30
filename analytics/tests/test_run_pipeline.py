# WHAT THIS FILE IS
# Tests for T38's orchestration (analytics/run_pipeline.py): it sequences T31's ingest
# (bronze landing + silver Track conform) and T34's cluster training (gold export) — both
# already built, tested, and independently idempotent. The orchestration-order test is a
# fast monkeypatched unit test (no DB). The one test that runs the real pipeline touches
# gold.Cluster/ModelMetrics/ModelArtifact (no per-run scoping column, same situation as
# test_cluster.py) and a disposable silver.Track row, so it snapshots/restores the gold
# tables and cleans up its own Track row, gated behind RUN_ANALYTICS_DB_TESTS like every
# other live-DB analytics test.

import json
import os
import uuid
from pathlib import Path

import numpy as np
import pytest
from sqlalchemy import text

import run_pipeline as run_pipeline_module
from db import get_engine
from run_pipeline import run_pipeline

_FEATURE_ORDER = [
    "danceability", "energy", "valence", "tempo", "loudness",
    "acousticness", "instrumentalness", "liveness", "speechiness", "mode",
]


def test_run_pipeline_calls_ingest_then_cluster_in_order(monkeypatch):
    calls = []

    def fake_ingest(csv_path, engine=None):
        calls.append(("ingest", csv_path))
        return {"total_tracks": 10, "matched": 5, "coverage_pct": 50.0}

    def fake_cluster(csv_path, engine=None, **kwargs):
        calls.append(("cluster", csv_path))
        return {"k": 3, "silhouette": 0.4, "sizes": [3, 3, 4]}

    monkeypatch.setattr(run_pipeline_module, "run_ingest", fake_ingest)
    monkeypatch.setattr(run_pipeline_module, "run_cluster", fake_cluster)

    result = run_pipeline("fake.csv", engine=object())

    assert [c[0] for c in calls] == ["ingest", "cluster"]
    assert result == {
        "ingest": {"total_tracks": 10, "matched": 5, "coverage_pct": 50.0},
        "cluster": {"k": 3, "silhouette": 0.4, "sizes": [3, 3, 4]},
    }


def test_run_pipeline_passes_cluster_kwargs_through(monkeypatch):
    seen_kwargs = {}

    def fake_ingest(csv_path, engine=None):
        return {"total_tracks": 0, "matched": 0, "coverage_pct": 0.0}

    def fake_cluster(csv_path, engine=None, **kwargs):
        seen_kwargs.update(kwargs)
        return {"k": 2, "silhouette": 0.0, "sizes": [1, 1]}

    monkeypatch.setattr(run_pipeline_module, "run_ingest", fake_ingest)
    monkeypatch.setattr(run_pipeline_module, "run_cluster", fake_cluster)

    run_pipeline("fake.csv", engine=object(), cluster_kwargs={"seed": 7, "forced_k": 2})

    assert seen_kwargs == {"seed": 7, "forced_k": 2}


def _snapshot_gold_tables(conn):
    return {
        "clusters": conn.execute(
            text('SELECT id, label, centroid, size, "computedAt" FROM gold."Cluster"')
        ).mappings().all(),
        "metrics": conn.execute(
            text(
                'SELECT "modelName", silhouette, k, r2, rmse, "featureImportances", "computedAt" '
                'FROM gold."ModelMetrics"'
            )
        ).mappings().all(),
        "artifacts": conn.execute(
            text(
                "SELECT model_name, feature_order, scaler_mean, scaler_std, params, computed_at "
                'FROM gold."ModelArtifact"'
            )
        ).mappings().all(),
    }


def _restore_gold_tables(conn, snapshot):
    conn.execute(text('DELETE FROM gold."Cluster"'))
    conn.execute(text('DELETE FROM gold."ModelMetrics"'))
    conn.execute(text('DELETE FROM gold."ModelArtifact"'))
    if snapshot["clusters"]:
        conn.execute(
            text(
                'INSERT INTO gold."Cluster" (id, label, centroid, size, "computedAt") '
                'VALUES (:id, :label, CAST(:centroid AS JSONB), :size, :computedAt)'
            ),
            [{**dict(row), "centroid": json.dumps(row["centroid"])} for row in snapshot["clusters"]],
        )
    if snapshot["metrics"]:
        conn.execute(
            text(
                'INSERT INTO gold."ModelMetrics" '
                '("modelName", silhouette, k, r2, rmse, "featureImportances", "computedAt") '
                'VALUES (:modelName, :silhouette, :k, :r2, :rmse, '
                'CAST(:featureImportances AS JSONB), :computedAt)'
            ),
            [
                {**dict(row), "featureImportances": json.dumps(row["featureImportances"])}
                for row in snapshot["metrics"]
            ],
        )
    if snapshot["artifacts"]:
        conn.execute(
            text(
                'INSERT INTO gold."ModelArtifact" '
                "(model_name, feature_order, scaler_mean, scaler_std, params, computed_at) "
                "VALUES (:model_name, CAST(:feature_order AS JSONB), CAST(:scaler_mean AS JSONB), "
                "CAST(:scaler_std AS JSONB), CAST(:params AS JSONB), :computed_at)"
            ),
            [
                {
                    **dict(row),
                    "feature_order": json.dumps(row["feature_order"]),
                    "scaler_mean": json.dumps(row["scaler_mean"]),
                    "scaler_std": json.dumps(row["scaler_std"]),
                    "params": json.dumps(row["params"]),
                }
                for row in snapshot["artifacts"]
            ],
        )


@pytest.mark.skipif(
    os.getenv("RUN_ANALYTICS_DB_TESTS") != "1",
    reason="live Supabase analytics DB check; set RUN_ANALYTICS_DB_TESTS=1 to run",
)
def test_run_pipeline_end_to_end_and_idempotent(tmp_path):
    engine = get_engine()
    matched_id = "test_pipeline_" + uuid.uuid4().hex

    # Two well-separated 10-feature blobs, same shape as test_cluster.py's fixture, so
    # k-means has something real to separate. The first row is the one Track we seed —
    # ingest should match it and the join should carry into cluster.py's training read.
    rng = np.random.default_rng(4)
    centers = [np.full(10, -5.0), np.full(10, 5.0)]
    header = "id," + ",".join(_FEATURE_ORDER)
    rows = [header]
    first = True
    for c in centers:
        for _ in range(15):
            point = c + rng.normal(scale=0.1, size=10)
            row_id = matched_id if first else "kaggle_only_" + uuid.uuid4().hex
            first = False
            rows.append(f"{row_id}," + ",".join(f"{v:.4f}" for v in point))
    csv_path = tmp_path / "kaggle_sample.csv"
    csv_path.write_text("\n".join(rows), encoding="utf-8")

    with engine.begin() as conn:
        original = _snapshot_gold_tables(conn)
        conn.execute(
            text('INSERT INTO silver."Track" ("spotifyId", title, "artistName") VALUES (:id, :t, :a)'),
            {"id": matched_id, "t": "Test Track", "a": "Test Artist"},
        )

    try:
        cluster_kwargs = {"k_range": range(2, 4), "seed": 3, "sample_size": 20}
        first_run = run_pipeline(csv_path, engine=engine, cluster_kwargs=cluster_kwargs)
        second_run = run_pipeline(csv_path, engine=engine, cluster_kwargs=cluster_kwargs)

        # Silver: the seeded Track matched and got joined.
        assert first_run["ingest"]["matched"] >= 1
        with engine.connect() as conn:
            track = conn.execute(
                text('SELECT "kaggleMatched", danceability FROM silver."Track" WHERE "spotifyId" = :id'),
                {"id": matched_id},
            ).one()
        assert track.kaggleMatched is True
        assert track.danceability is not None

        # Gold: re-running the whole pipeline is idempotent (replaces, not duplicates).
        assert first_run["cluster"]["k"] == second_run["cluster"]["k"]
        assert first_run["cluster"]["labels"] == second_run["cluster"]["labels"]
        with engine.connect() as conn:
            cluster_rows = conn.execute(text('SELECT * FROM gold."Cluster"')).mappings().all()
        assert len(cluster_rows) == first_run["cluster"]["k"]
    finally:
        with engine.begin() as conn:
            conn.execute(text('DELETE FROM silver."Track" WHERE "spotifyId" = :id'), {"id": matched_id})
            _restore_gold_tables(conn, original)
