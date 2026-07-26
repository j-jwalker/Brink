# WHAT THIS FILE IS
# T34: fits K-means on the Kaggle track corpus — the full local CSV file, not
# just the small set of tracks matched to real listening history. ADR-0004 C2
# calls for training on the ~1M-track audio space so the elbow/silhouette
# story is real, not a handful of points; the file itself is already the
# complete archive (see T31), so training reads it directly rather than
# querying the database. Persists the result to the gold schema (ADR-0009):
#   - gold.Cluster — one human-readable row per cluster (label, centroid in
#     original feature units, size), for showing clusters in a UI/report.
#   - gold.ModelMetrics("kmeans") — silhouette + k, so model quality is on
#     record.
#   - gold.ModelArtifact("kmeans") — the self-describing export (feature
#     order, scaler mean/std, centroids in STANDARDIZED space) that a future
#     on-demand inference step (T33) reads to assign a real user to a
#     cluster, without needing this training corpus present at inference
#     time (ADR-0003).
#
# FEATURE_ORDER is the full set of genuine audio-character features in the
# Kaggle file (not release metadata like year/duration, and not `key`, which
# is circular/categorical and would distort Euclidean distance as a raw
# number). NOTE for whoever builds T33: since real Track rows only carry the
# original 5 features from T31's join, assigning a real user to one of these
# clusters will need Track's schema extended with the other 5 (a migration)
# before on-demand inference can compute a comparable point for them.
#
# WHY centroids are stored twice, in two different spaces: gold.Cluster's
# centroid is in original units (readable — "danceability 0.75"), because
# it's for humans. gold.ModelArtifact's centroids are in standardized
# (z-score) space, because that's the space K-means actually computed
# distances in, and inference must compare a new point the same way.
#
# WHY re-running replaces instead of duplicating: training must be safe to
# redo (e.g. after a better dataset shows up, same spirit as T31's dataset
# swap) without piling up stale results. gold.Cluster/ModelMetrics/
# ModelArtifact have no per-run scoping column, so a fresh run always deletes
# the previous "kmeans" results first.
#
# Run it directly against the full downloaded CSV:
# `uv run python cluster.py <path>`.

import csv
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler
from sqlalchemy import Engine, text

from db import get_engine

FEATURE_ORDER = [
    "danceability", "energy", "valence", "tempo", "loudness",
    "acousticness", "instrumentalness", "liveness", "speechiness", "mode",
]
_DEFAULT_K_RANGE = range(2, 11)
_DEFAULT_SEED = 42
_DEFAULT_SILHOUETTE_SAMPLE_SIZE = 10_000


def load_feature_matrix(csv_path: Path) -> np.ndarray:
    rows = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append([float(row[col]) for col in FEATURE_ORDER])
    return np.array(rows, dtype=float)


def select_k(
    X_scaled: np.ndarray,
    k_range=_DEFAULT_K_RANGE,
    seed: int = _DEFAULT_SEED,
    sample_size: int = _DEFAULT_SILHOUETTE_SAMPLE_SIZE,
) -> tuple[int, dict[int, dict[str, float]]]:
    # Elbow (inertia) is recorded for the report, but isn't itself an
    # automatable stopping rule — silhouette score is what actually picks k,
    # since it's a single number to maximize. Silhouette is scored on a fixed
    # random sample, not the full corpus: computing it exactly is O(n^2),
    # infeasible at ~1M rows.
    metrics: dict[int, dict[str, float]] = {}
    n = len(X_scaled)
    for k in k_range:
        model = KMeans(n_clusters=k, random_state=seed, n_init=10)
        labels = model.fit_predict(X_scaled)
        score = silhouette_score(X_scaled, labels, sample_size=min(sample_size, n), random_state=seed)
        metrics[k] = {"inertia": float(model.inertia_), "silhouette": float(score)}
    best_k = max(metrics, key=lambda candidate: metrics[candidate]["silhouette"])
    return best_k, metrics


def label_clusters(centroids_scaled: np.ndarray, feature_order: list[str]) -> list[str]:
    # Rule-based, not ML: for each centroid, name the 1-2 features furthest
    # from the corpus average (in standardized space, so features are
    # directly comparable) as "High X" / "Low X".
    labels = []
    for centroid in centroids_scaled:
        top = np.argsort(-np.abs(centroid))[:2]
        parts = [
            f"{'High' if centroid[i] > 0 else 'Low'} {feature_order[i].capitalize()}" for i in top
        ]
        labels.append(", ".join(parts))
    return labels


def _write_results(
    engine: Engine,
    *,
    k: int,
    silhouette: float,
    labels: list[str],
    centroids_original: np.ndarray,
    centroids_scaled: np.ndarray,
    sizes: list[int],
    scaler_mean: list[float],
    scaler_std: list[float],
    feature_order: list[str],
) -> None:
    now = datetime.now(timezone.utc)
    with engine.begin() as conn:
        conn.execute(text('DELETE FROM gold."Cluster"'))
        conn.execute(text('DELETE FROM gold."ModelMetrics" WHERE "modelName" = :name'), {"name": "kmeans"})
        conn.execute(text('DELETE FROM gold."ModelArtifact" WHERE model_name = :name'), {"name": "kmeans"})

        conn.execute(
            text(
                'INSERT INTO gold."Cluster" (id, label, centroid, size, "computedAt") '
                'VALUES (:id, :label, CAST(:centroid AS JSONB), :size, :computed_at)'
            ),
            [
                {
                    "id": uuid.uuid4().hex,
                    "label": labels[i],
                    "centroid": json.dumps(dict(zip(feature_order, centroids_original[i].tolist()))),
                    "size": sizes[i],
                    "computed_at": now,
                }
                for i in range(k)
            ],
        )

        conn.execute(
            text(
                'INSERT INTO gold."ModelMetrics" ("modelName", silhouette, k, "computedAt") '
                "VALUES (:name, :silhouette, :k, :computed_at)"
            ),
            {"name": "kmeans", "silhouette": silhouette, "k": k, "computed_at": now},
        )

        conn.execute(
            text(
                'INSERT INTO gold."ModelArtifact" '
                "(model_name, feature_order, scaler_mean, scaler_std, params, computed_at) "
                "VALUES (:name, CAST(:feature_order AS JSONB), CAST(:scaler_mean AS JSONB), "
                "CAST(:scaler_std AS JSONB), CAST(:params AS JSONB), :computed_at)"
            ),
            {
                "name": "kmeans",
                "feature_order": json.dumps(feature_order),
                "scaler_mean": json.dumps(scaler_mean),
                "scaler_std": json.dumps(scaler_std),
                "params": json.dumps({"centroids": centroids_scaled.tolist()}),
                "computed_at": now,
            },
        )


def run_cluster(
    csv_path: Path | str,
    engine: Optional[Engine] = None,
    k_range=_DEFAULT_K_RANGE,
    seed: int = _DEFAULT_SEED,
    sample_size: int = _DEFAULT_SILHOUETTE_SAMPLE_SIZE,
    forced_k: Optional[int] = None,
) -> dict:
    engine = engine or get_engine()
    X = load_feature_matrix(Path(csv_path))

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # silhouette_best_k is always computed and kept on record, even when
    # forced_k overrides it — choosing more clusters than silhouette prefers
    # (for a usable persona system) must stay a disclosed trade-off, not a
    # silently hidden one (ADR-0004: report honestly).
    silhouette_best_k, k_metrics = select_k(X_scaled, k_range=k_range, seed=seed, sample_size=sample_size)
    k = forced_k if forced_k is not None else silhouette_best_k

    if k not in k_metrics:
        # forced_k fell outside k_range — fit it directly so there's still a
        # silhouette score on record for the k actually used.
        probe = KMeans(n_clusters=k, random_state=seed, n_init=10)
        probe_labels = probe.fit_predict(X_scaled)
        probe_score = silhouette_score(
            X_scaled, probe_labels, sample_size=min(sample_size, len(X_scaled)), random_state=seed
        )
        k_metrics[k] = {"inertia": float(probe.inertia_), "silhouette": float(probe_score)}

    model = KMeans(n_clusters=k, random_state=seed, n_init=10)
    cluster_labels = model.fit_predict(X_scaled)
    centroids_scaled = model.cluster_centers_
    centroids_original = scaler.inverse_transform(centroids_scaled)
    sizes = np.bincount(cluster_labels, minlength=k).tolist()
    silhouette = k_metrics[k]["silhouette"]
    labels = label_clusters(centroids_scaled, FEATURE_ORDER)

    _write_results(
        engine,
        k=k,
        silhouette=silhouette,
        labels=labels,
        centroids_original=centroids_original,
        centroids_scaled=centroids_scaled,
        sizes=sizes,
        scaler_mean=scaler.mean_.tolist(),
        scaler_std=scaler.scale_.tolist(),
        feature_order=FEATURE_ORDER,
    )

    if forced_k is not None and forced_k != silhouette_best_k:
        print(
            f"K-means: k={k} FORCED (silhouette={silhouette:.3f}) — silhouette actually "
            f"preferred k={silhouette_best_k} (silhouette={k_metrics[silhouette_best_k]['silhouette']:.3f}); "
            f"cluster sizes: {sizes}"
        )
    else:
        print(f"K-means: selected k={k} (silhouette={silhouette:.3f}); cluster sizes: {sizes}")
    for candidate_k, m in sorted(k_metrics.items()):
        marker = " <- silhouette-best" if candidate_k == silhouette_best_k else ""
        marker += " <- used" if candidate_k == k else ""
        print(f"  k={candidate_k}: inertia={m['inertia']:.1f}, silhouette={m['silhouette']:.3f}{marker}")

    return {
        "k": k,
        "silhouette": silhouette,
        "sizes": sizes,
        "labels": labels,
        "k_metrics": k_metrics,
        "silhouette_best_k": silhouette_best_k,
        "forced": forced_k is not None,
    }


if __name__ == "__main__":
    forced = int(sys.argv[2]) if len(sys.argv) > 2 else None
    run_cluster(sys.argv[1], forced_k=forced)
