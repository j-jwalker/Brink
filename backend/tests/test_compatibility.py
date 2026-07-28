# WHAT THIS FILE IS
# Tests for T35: cosine similarity between two users' taste vectors (T33), computed on
# read (ADR-0003), reused by the profile API (T14). Split the same way test_inference.py
# is: `cosine` and `compatibility_from_vectors` are pure functions tested on plain data —
# no DB needed. `compatibility()` itself (the thin orchestrator that loads
# ModelArtifact("kmeans") and calls T33's build_taste_vector twice) can only be exercised
# for its graceful "gold schema missing" path against db_session, since ModelArtifact uses
# a Postgres-only JSONB column SQLite can't build (see conftest.py's db_session, and
# test_inference.py's identical situation for assign_cluster).

from datetime import datetime, timezone

from app.inference.compatibility import compatibility, compatibility_from_vectors, cosine
from app.models import User


def _seed_user(session, uid="u1"):
    session.add(User(id=uid, handle=uid, display_name=uid, created_at=datetime.now(timezone.utc)))
    session.commit()


# ---- cosine (pure) ----


def test_identical_vectors_are_fully_compatible():
    v = [0.7, 0.2, 0.9]
    assert cosine(v, v) == 1.0


def test_orthogonal_vectors_are_zero_compatible():
    assert cosine([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_cosine_is_symmetric():
    a = [0.7, 0.2, 0.9, 0.1]
    b = [0.1, 0.9, 0.3, 0.6]
    assert cosine(a, b) == cosine(b, a)


def test_negative_correlation_is_clamped_to_zero():
    # A raw cosine of opposite vectors is -1 — clamped to 0 (ADR-0003: reads as "not
    # compatible", not a negative number on a 0..1 scale).
    assert cosine([1.0, 0.0], [-1.0, 0.0]) == 0.0


def test_zero_vector_is_zero_compatible_not_a_crash():
    # A zero-magnitude vector would divide by zero in the raw formula.
    assert cosine([0.0, 0.0], [1.0, 1.0]) == 0.0


# ---- compatibility_from_vectors (pure) ----


def test_compatibility_from_vectors_null_when_either_side_missing():
    some_result = {"vector": [1.0, 0.0], "coverage_pct": 100.0, "track_count": 1}
    assert compatibility_from_vectors(None, some_result) is None
    assert compatibility_from_vectors(some_result, None) is None
    assert compatibility_from_vectors(None, None) is None


def test_compatibility_from_vectors_computes_cosine_when_both_present():
    a = {"vector": [1.0, 0.0], "coverage_pct": 100.0, "track_count": 1}
    b = {"vector": [1.0, 0.0], "coverage_pct": 100.0, "track_count": 1}
    assert compatibility_from_vectors(a, b) == 1.0


# ---- compatibility() orchestration ----


def test_compatibility_degrades_when_gold_schema_is_unavailable(db_session):
    # Same "gold schema missing" case as T33's assign_cluster — must never raise.
    _seed_user(db_session, "u1")
    _seed_user(db_session, "u2")
    assert compatibility(db_session, "u1", "u2") is None
