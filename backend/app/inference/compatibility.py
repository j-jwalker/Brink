# WHAT THIS FILE IS
# T35: cosine similarity between two users' taste vectors (T33's build_taste_vector),
# computed on read (ADR-0003) — no stored Compatibility table. Used by the profile API
# (T14) to show "how compatible are you with this listener".

import logging
import math
from typing import Optional

from sqlmodel import Session

from app.inference.taste_vector import build_taste_vector
from app.models import ModelArtifact

logger = logging.getLogger(__name__)


def cosine(vector_a: list[float], vector_b: list[float]) -> float:
    # Cosine similarity, clamped to 0..1 (ADR-0003): the raw formula ranges -1..1, but a
    # negative value just means "less similar than average" here, not a meaningful
    # negative compatibility — so it reads as 0 rather than as a confusing negative
    # number on what's shown as a 0-100% scale. A zero-magnitude vector (all-zero
    # features) would divide by zero; treated as 0 compatibility instead of crashing.
    dot = sum(a * b for a, b in zip(vector_a, vector_b))
    magnitude_a = math.sqrt(sum(a * a for a in vector_a))
    magnitude_b = math.sqrt(sum(b * b for b in vector_b))
    if magnitude_a == 0 or magnitude_b == 0:
        return 0.0
    # round() before clamping: floating-point error can push an identical pair's
    # similarity a hair past 1.0 (or a hair under), which the raw formula would
    # otherwise report as e.g. 0.9999999999999999 instead of a clean 1.0.
    similarity = round(dot / (magnitude_a * magnitude_b), 6)
    return max(0.0, min(1.0, similarity))


def compatibility_from_vectors(vector_a_result: Optional[dict], vector_b_result: Optional[dict]) -> Optional[float]:
    # Either side missing a taste vector (a user with no plays/posts, or no complete
    # Kaggle-matched track at all — see T33's build_taste_vector) -> null, not an error.
    if vector_a_result is None or vector_b_result is None:
        return None
    return cosine(vector_a_result["vector"], vector_b_result["vector"])


def compatibility(session: Session, user_a_id: str, user_b_id: str) -> Optional[float]:
    # Both vectors must come from the SAME T33 builder call shape (same feature_order,
    # same corpus_mean) to be comparable — loading the artifact once and passing it into
    # both build_taste_vector calls guarantees that. Degrades to null — never raises —
    # when the model isn't trained yet or the gold schema doesn't exist at all (e.g.
    # local dev), same pattern as T33's assign_cluster.
    try:
        artifact = session.get(ModelArtifact, "kmeans")
        if artifact is None:
            return None

        vector_a_result = build_taste_vector(session, user_a_id, artifact.feature_order, artifact.scaler_mean)
        vector_b_result = build_taste_vector(session, user_b_id, artifact.feature_order, artifact.scaler_mean)
        return compatibility_from_vectors(vector_a_result, vector_b_result)
    except Exception as e:  # noqa: BLE001 — no analytics store yet -> null compatibility, not a 500
        logger.warning("compatibility computation failed (model store unavailable): %s", e)
        return None
