# WHAT THIS FILE IS
# T33: given a user's taste vector (from taste_vector.py), standardizes it using the
# trained ModelArtifact("kmeans")'s scaler and assigns it to the nearest gold.Cluster —
# the "which taste community is this listener in?" step, computed on read (ADR-0003:
# nothing pre-stored).
#
# WHY we compare in standardized space, not raw units: K-means itself was FIT on
# standardized features (see analytics/cluster.py), so "nearest" only means the same
# thing here if distance is measured the same way it was during training.
#
# WHY each Cluster's centroid is re-standardized here instead of reading
# ModelArtifact.params directly: gold.Cluster stores its centroid in ORIGINAL units (for
# humans to read on the analytics page, T45) and has no stable column linking a row back
# to its position in ModelArtifact.params["centroids"] — relying on insertion order would
# be fragile. Standardizing each Cluster's own centroid with the SAME scaler at read time
# sidesteps that entirely: it always compares against whichever Cluster rows are actually
# in the database right now.

import logging
import math
from typing import Optional

from sqlmodel import Session, select

from app.inference.taste_vector import build_taste_vector
from app.models import Cluster, ModelArtifact

logger = logging.getLogger(__name__)


def standardize(vector: list[float], scaler_mean: list[float], scaler_std: list[float]) -> list[float]:
    # z-score each feature: (x - mean) / std. A zero std (a feature with no variance in
    # the training corpus) would divide by zero; that feature contributes 0 instead of
    # crashing — a no-variance feature carries no separating information anyway.
    return [
        (x - mean) / std if std else 0.0
        for x, mean, std in zip(vector, scaler_mean, scaler_std)
    ]


def nearest_cluster_label(
    standardized_vector: list[float],
    clusters: list[Cluster],
    feature_order: list[str],
    scaler_mean: list[float],
    scaler_std: list[float],
) -> Optional[Cluster]:
    best_cluster = None
    best_distance = None
    for cluster in clusters:
        centroid = [cluster.centroid[feature] for feature in feature_order]
        standardized_centroid = standardize(centroid, scaler_mean, scaler_std)
        distance = math.dist(standardized_vector, standardized_centroid)
        if best_distance is None or distance < best_distance:
            best_distance = distance
            best_cluster = cluster
    return best_cluster


def assign_cluster(session: Session, user_id: str) -> dict:
    # The full on-read pipeline: load the trained model, build the user's taste vector,
    # standardize it, and assign the nearest Cluster. Degrades to a null cluster — never
    # raises — when the model hasn't been trained yet, the gold schema doesn't exist at
    # all (e.g. local dev without the medallion schemas, same case pages.py's
    # _analytics_data guards for T45), or the user has no eligible tracks yet.
    try:
        artifact = session.get(ModelArtifact, "kmeans")
        if artifact is None:
            return {"cluster": None, "coverage_pct": None}

        result = build_taste_vector(session, user_id, artifact.feature_order, artifact.scaler_mean)
        if result is None:
            return {"cluster": None, "coverage_pct": None}

        standardized_vector = standardize(result["vector"], artifact.scaler_mean, artifact.scaler_std)
        clusters = list(session.exec(select(Cluster)).all())
        cluster = nearest_cluster_label(
            standardized_vector, clusters, artifact.feature_order, artifact.scaler_mean, artifact.scaler_std
        )
    except Exception as e:  # noqa: BLE001 — no analytics store yet -> null cluster, not a 500
        logger.warning("cluster assignment failed (model store unavailable): %s", e)
        return {"cluster": None, "coverage_pct": None}

    return {
        "cluster": {"id": cluster.id, "label": cluster.label} if cluster else None,
        "coverage_pct": result["coverage_pct"],
    }
