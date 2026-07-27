# WHAT THIS FILE IS
# T33: builds a user's taste vector — a point in the same 10-feature audio space T34
# trained K-means on (analytics/cluster.py FEATURE_ORDER) — from the tracks they've
# actually played or posted. Computed fresh on every call (ADR-0003: no stored
# TasteVector table), since a user's history is small enough that this is cheap.
#
# C4 fallback (ADR-0004): the Kaggle audio-feature set doesn't cover every real-world
# track, and neither Kaggle CSV carries a genre field at all (T32 hit the exact same gap
# building its personas), so a literal "genre-only fallback vector" isn't buildable. We
# fall back to the training corpus's own mean feature vector instead — "assume average"
# for a track we have no real signal for. Coverage % is always returned alongside the
# vector, so a low-coverage result is visible on the page, never hidden (ADR-0004).

from typing import Optional

from sqlmodel import Session, select

from app.models import Play, Post, Track


def build_taste_vector(
    session: Session,
    user_id: str,
    feature_order: list[str],
    corpus_mean: list[float],
) -> Optional[dict]:
    # Average the per-track feature vectors of every track a user has played or posted.
    # A track counts as "matched" only when ALL of feature_order is present — not just
    # kaggleMatched=True — because a Track matched before T33 widened the schema still
    # has NULLs in the 5 new columns until ingest is re-run; treating it as matched would
    # crash averaging a None. Returns None when the user has no eligible tracks at all
    # (a brand-new account), so the caller can degrade gracefully instead of dividing by
    # zero.
    track_ids = _user_track_ids(session, user_id)
    if not track_ids:
        return None

    tracks = session.exec(select(Track).where(Track.spotify_id.in_(track_ids))).all()
    if not tracks:
        return None

    vectors: list[list[float]] = []
    matched_count = 0
    for track in tracks:
        values = [getattr(track, feature) for feature in feature_order]
        if all(v is not None for v in values):
            vectors.append(values)
            matched_count += 1
        else:
            vectors.append(corpus_mean)

    vector = [sum(column) / len(column) for column in zip(*vectors)]
    coverage_pct = matched_count / len(tracks) * 100

    return {"vector": vector, "coverage_pct": coverage_pct, "track_count": len(tracks)}


def _user_track_ids(session: Session, user_id: str) -> set[str]:
    # Union of every track a user has ever played (Play) or shared (Post). A text-only
    # post (T104) has track_id=None, so it's excluded by the WHERE clause below rather
    # than needing special-casing here.
    played = session.exec(select(Play.track_id).where(Play.user_id == user_id)).all()
    posted = session.exec(
        select(Post.track_id).where(Post.user_id == user_id, Post.track_id.is_not(None))
    ).all()
    return set(played) | set(posted)
