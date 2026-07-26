# WHAT THIS FILE IS
# Tests for T34's K-means training (analytics/cluster.py). The model-selection
# and labeling logic are pure functions tested with small synthetic data, no
# database needed. The one test that writes to the database
# (test_run_cluster_writes_and_is_idempotent) touches gold.Cluster/
# ModelMetrics/ModelArtifact — tables with no per-run scoping column, so a
# real training run's results and a test run's results can't coexist by id.
# It snapshots whatever's really there first and restores it afterward, so
# running the test suite can never silently wipe a real trained model.

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest
from sqlalchemy import text

from cluster import label_clusters, load_feature_matrix, run_cluster, select_k
from db import get_engine


_CSV_HEADER = (
    "id,danceability,energy,valence,tempo,loudness,"
    "acousticness,instrumentalness,liveness,speechiness,mode,extra_column"
)


def test_load_feature_matrix_reads_features_in_order(tmp_path):
    csv_path = tmp_path / "tracks.csv"
    csv_path.write_text(
        _CSV_HEADER + "\n"
        "a,0.5,0.6,0.7,120.0,-6.0,0.1,0.0,0.2,0.05,1,ignored\n"
        "b,0.1,0.2,0.3,90.0,-12.0,0.9,0.8,0.1,0.02,0,ignored\n",
        encoding="utf-8",
    )

    X = load_feature_matrix(csv_path)

    assert X.shape == (2, 10)
    assert X[0].tolist() == [0.5, 0.6, 0.7, 120.0, -6.0, 0.1, 0.0, 0.2, 0.05, 1.0]
    assert X[1].tolist() == [0.1, 0.2, 0.3, 90.0, -12.0, 0.9, 0.8, 0.1, 0.02, 0.0]


def test_select_k_picks_the_true_number_of_well_separated_clusters():
    rng = np.random.default_rng(0)
    # Three tight, widely-separated blobs in 5D — an easy case where silhouette
    # should unambiguously prefer k=3 over k=2 or k=4.
    centers = [np.full(5, -10.0), np.full(5, 0.0), np.full(5, 10.0)]
    X = np.vstack([c + rng.normal(scale=0.1, size=(20, 5)) for c in centers])

    best_k, metrics = select_k(X, k_range=range(2, 5), seed=42, sample_size=60)

    assert best_k == 3
    assert set(metrics.keys()) == {2, 3, 4}
    for k, m in metrics.items():
        assert "inertia" in m and "silhouette" in m


def test_select_k_is_deterministic():
    rng = np.random.default_rng(1)
    centers = [np.full(5, -10.0), np.full(5, 10.0)]
    X = np.vstack([c + rng.normal(scale=0.1, size=(15, 5)) for c in centers])

    first_k, first_metrics = select_k(X, k_range=range(2, 4), seed=7, sample_size=30)
    second_k, second_metrics = select_k(X, k_range=range(2, 4), seed=7, sample_size=30)

    assert first_k == second_k
    assert first_metrics == second_metrics


def test_label_clusters_names_the_most_extreme_features():
    feature_order = ["danceability", "energy", "valence", "tempo", "loudness"]
    # A centroid that's mostly average except strongly high energy and low valence.
    centroids = np.array([
        [0.0, 2.5, -2.0, 0.1, -0.1],
    ])

    labels = label_clusters(centroids, feature_order)

    assert labels == ["High Energy, Low Valence"]


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
    # JSONB columns come back from .mappings() as plain Python dicts/lists
    # (psycopg auto-decodes them) — they must be re-serialized with
    # json.dumps() before going back in as a CAST(...AS JSONB) param, or
    # psycopg can't adapt them (same class of bug as T31's bronze insert).
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
def test_run_cluster_writes_and_is_idempotent(tmp_path):
    engine = get_engine()
    csv_path = tmp_path / "tracks.csv"
    rng = np.random.default_rng(2)
    centers = [np.full(10, -5.0), np.full(10, 5.0)]
    rows = [
        "id,danceability,energy,valence,tempo,loudness,"
        "acousticness,instrumentalness,liveness,speechiness,mode"
    ]
    i = 0
    for c in centers:
        for _ in range(15):
            point = c + rng.normal(scale=0.1, size=10)
            rows.append(f"t{i}," + ",".join(f"{v:.4f}" for v in point))
            i += 1
    csv_path.write_text("\n".join(rows), encoding="utf-8")

    with engine.begin() as conn:
        original = _snapshot_gold_tables(conn)

    try:
        first = run_cluster(csv_path, engine=engine, k_range=range(2, 4), seed=3, sample_size=30)
        second = run_cluster(csv_path, engine=engine, k_range=range(2, 4), seed=3, sample_size=30)

        assert first["k"] == 2
        assert first["k"] == second["k"]
        assert first["labels"] == second["labels"]
        assert sorted(first["sizes"]) == sorted(second["sizes"])

        with engine.connect() as conn:
            clusters = conn.execute(text('SELECT * FROM gold."Cluster"')).mappings().all()
            metrics = conn.execute(
                text('SELECT * FROM gold."ModelMetrics" WHERE "modelName" = :n'), {"n": "kmeans"}
            ).mappings().all()
            artifacts = conn.execute(
                text('SELECT * FROM gold."ModelArtifact" WHERE model_name = :n'), {"n": "kmeans"}
            ).mappings().all()

        # Re-running replaced, not duplicated: exactly k clusters, one metrics
        # row, one artifact row — never accumulates across runs.
        assert len(clusters) == first["k"]
        assert len(metrics) == 1
        assert len(artifacts) == 1

        expected_features = {
            "danceability", "energy", "valence", "tempo", "loudness",
            "acousticness", "instrumentalness", "liveness", "speechiness", "mode",
        }
        artifact = artifacts[0]
        assert set(artifact["feature_order"]) == expected_features
        assert len(artifact["scaler_mean"]) == 10
        assert len(artifact["scaler_std"]) == 10
        # Centroid dimensionality must match featureOrder — the guardrail
        # T33's on-demand inference depends on.
        assert all(len(c) == 10 for c in artifact["params"]["centroids"])
        assert len(artifact["params"]["centroids"]) == first["k"]

        for cluster in clusters:
            assert set(cluster["centroid"].keys()) == expected_features
    finally:
        with engine.begin() as conn:
            _restore_gold_tables(conn, original)


@pytest.mark.skipif(
    os.getenv("RUN_ANALYTICS_DB_TESTS") != "1",
    reason="live Supabase analytics DB check; set RUN_ANALYTICS_DB_TESTS=1 to run",
)
def test_forced_k_overrides_silhouette_but_records_it_honestly(tmp_path):
    # Data where silhouette clearly prefers k=2 (two tight, far-apart blobs),
    # but the persona feature needs more groups than that's willing to give.
    # Forcing k=3 must still work, and the summary must keep the honest
    # record of what silhouette actually preferred, not just the forced k
    # (ADR-0004: report honestly, don't hide the trade-off).
    engine = get_engine()
    csv_path = tmp_path / "tracks.csv"
    rng = np.random.default_rng(5)
    centers = [np.full(10, -8.0), np.full(10, 8.0)]
    rows = [
        "id,danceability,energy,valence,tempo,loudness,"
        "acousticness,instrumentalness,liveness,speechiness,mode"
    ]
    i = 0
    for c in centers:
        for _ in range(15):
            point = c + rng.normal(scale=0.1, size=10)
            rows.append(f"t{i}," + ",".join(f"{v:.4f}" for v in point))
            i += 1
    csv_path.write_text("\n".join(rows), encoding="utf-8")

    with engine.begin() as conn:
        original = _snapshot_gold_tables(conn)

    try:
        summary = run_cluster(
            csv_path, engine=engine, k_range=range(2, 4), seed=3, sample_size=30, forced_k=3
        )

        assert summary["k"] == 3
        assert summary["forced"] is True
        assert summary["silhouette_best_k"] == 2
        assert len(summary["labels"]) == 3
        assert len(summary["sizes"]) == 3

        with engine.connect() as conn:
            clusters = conn.execute(text('SELECT * FROM gold."Cluster"')).mappings().all()
            metrics = conn.execute(
                text('SELECT * FROM gold."ModelMetrics" WHERE "modelName" = :n'), {"n": "kmeans"}
            ).mappings().all()

        assert len(clusters) == 3
        assert metrics[0]["k"] == 3
    finally:
        with engine.begin() as conn:
            _restore_gold_tables(conn, original)
