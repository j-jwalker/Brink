# WHAT THIS FILE IS
# T32: seeds ~50 synthetic User rows (isSynthetic=true) as genre-coherent
# "personas", each with a Play history sampled from Kaggle tracks near one of
# T34's 7 trained gold.Cluster centroids. Rescoped from ADR-0004 C3's original
# ~100-200 down to ~50 — see the ticket's "Changed from ADR-0004 C3" note.
#
# WHY personas = T34's clusters, not genre tags: neither Kaggle CSV
# (tracks_features.csv) has a genre column, so "genre-coherent" is
# operationalized as an audio feature-space region — the same 7 regions T34
# already trained K-means on. Reusing them (rather than inventing new
# grouping logic) keeps one shared feature definition across the whole
# pipeline, the same principle T33 will follow for real users.
#
# WHY this also inserts new silver.Track rows: Play.trackId is a hard FK
# (ondelete=RESTRICT) to silver.Track.spotifyId, and ingest_kaggle.py (T31)
# only ever *updates* existing Track rows — it never inserts new ones. Live
# brink-dev has only 67 Kaggle-matched tracks, far too few and too narrow in
# feature-space to sample genre-coherent plays from. So for each persona this
# builds a small SHARED pool of new Track rows (real Spotify track IDs from
# the Kaggle `id` column, picked as the nearest points to that persona's
# centroid) and every user in that persona draws their plays from the same
# shared pool — Track growth (~150-200 rows total) doesn't scale with user
# count, only with persona count (fixed at 7).
#
# WHY no User column records which persona a user belongs to: ADR-0003
# already decided a user's cluster is computed ON READ (T33 does this for
# every user, real or synthetic) from their Play history's track features,
# not stored. A synthetic user's persona is therefore implicit in which
# pool their plays were drawn from, not a separate column here.
#
# WHY idempotent by deterministic handle: re-running must not pile up
# duplicate users/tracks/plays (same idempotency expectation as T31/T34).
# Handles are assigned in a fixed (cluster order, index) traversal, so the
# same synthetic "slot" always gets the same handle across runs — a rerun
# finds it already exists (ON CONFLICT DO NOTHING) and skips both that user
# and their plays, rather than adding a second batch.
#
# Run it directly against the full downloaded CSV:
# `uv run python seed_users.py <path-to-tracks_features.csv>`.

import ast
import csv
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import numpy as np
from sqlalchemy import Engine, text

from cluster import FEATURE_ORDER
from db import get_engine

_DEFAULT_TOTAL_USERS = 50
_DEFAULT_POOL_SIZE = 25
_DEFAULT_PLAYS_RANGE = (15, 25)
_DEFAULT_DAYS_RANGE = (8, 15)
_DEFAULT_LOOKBACK_DAYS = 30
_DEFAULT_SEED = 42

# Only these 5 of FEATURE_ORDER's 10 features have columns on silver.Track
# today (T31's original join) — the other 5 need a migration T33 flags as its
# own prerequisite, not built here. New Track rows this script inserts only
# populate the 5 that actually exist.
_TRACK_COLUMNS = ["danceability", "energy", "valence", "tempo", "loudness"]


def _parse_artist_name(raw: str) -> str:
    # Kaggle's `artists` column is a Python-list repr string, e.g.
    # "['Rage Against The Machine']" or "['A', 'B']" for multiple artists.
    # We only need one display name, so take the first.
    try:
        parsed = ast.literal_eval(raw)
        if isinstance(parsed, (list, tuple)) and parsed:
            return str(parsed[0])
    except (ValueError, SyntaxError):
        pass
    return raw.strip("[]'\" ")


def standardize_matrix(X: np.ndarray, mean, std) -> np.ndarray:
    return (X - np.asarray(mean, dtype=float)) / np.asarray(std, dtype=float)


def nearest_indices(X_scaled: np.ndarray, centroid: np.ndarray, exclude: set[int], n: int) -> list[int]:
    distances = np.sum((X_scaled - centroid) ** 2, axis=1)
    if exclude:
        distances = distances.copy()
        distances[list(exclude)] = np.inf
    n = max(0, min(n, len(distances) - len(exclude)))
    order = np.argsort(distances)[:n]
    return order.tolist()


def match_clusters_to_centroids(
    clusters: list[dict], centroids, scaler_mean, scaler_std, feature_order: list[str]
) -> list[dict]:
    # gold.Cluster stores centroids in ORIGINAL feature units (for humans);
    # gold.ModelArtifact stores them STANDARDIZED (the space K-means actually
    # used). Pair each Cluster row with its corresponding artifact centroid by
    # standardizing the Cluster's centroid and finding the nearest match —
    # they were computed from the same numbers, so the true match is at
    # (near-)zero distance.
    centroids_arr = np.asarray(centroids, dtype=float)
    mean = np.asarray(scaler_mean, dtype=float)
    std = np.asarray(scaler_std, dtype=float)
    matched = []
    used_indices: set[int] = set()
    for cluster in clusters:
        original = np.array([cluster["centroid"][f] for f in feature_order], dtype=float)
        scaled = (original - mean) / std
        distances = np.sum((centroids_arr - scaled) ** 2, axis=1)
        idx = int(np.argmin(distances))
        if idx in used_indices:
            raise ValueError(
                f"cluster {cluster['id']} matched an already-claimed centroid index {idx} — "
                "gold.Cluster and gold.ModelArtifact('kmeans') are out of sync"
            )
        used_indices.add(idx)
        matched.append({
            "cluster_id": cluster["id"],
            "label": cluster["label"],
            "centroid_scaled": centroids_arr[idx],
        })
    return matched


def load_track_catalog(csv_path: Path, feature_order: list[str]):
    ids: list[str] = []
    titles: list[str] = []
    artists: list[str] = []
    features: list[list[float]] = []
    with Path(csv_path).open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ids.append(row["id"])
            titles.append(row["name"])
            artists.append(_parse_artist_name(row["artists"]))
            features.append([float(row[col]) for col in feature_order])
    return ids, titles, artists, np.array(features, dtype=float)


def build_persona_pools(
    csv_path: Path,
    matched_clusters: list[dict],
    feature_order: list[str],
    scaler_mean,
    scaler_std,
    exclude_ids: set[str],
    pool_size: int = _DEFAULT_POOL_SIZE,
) -> dict[str, list[dict]]:
    ids, titles, artists, X = load_track_catalog(csv_path, feature_order)
    X_scaled = standardize_matrix(X, scaler_mean, scaler_std)

    claimed_idx = {i for i, track_id in enumerate(ids) if track_id in exclude_ids}
    pools: dict[str, list[dict]] = {}
    for cluster in matched_clusters:
        picked = nearest_indices(X_scaled, cluster["centroid_scaled"], claimed_idx, pool_size)
        pools[cluster["cluster_id"]] = [
            {
                "spotify_id": ids[i],
                "title": titles[i],
                "artist_name": artists[i],
                **{feature_order[j]: float(X[i][j]) for j in range(len(feature_order))},
            }
            for i in picked
        ]
        claimed_idx.update(picked)
    return pools


def split_evenly(total: int, buckets: int) -> list[int]:
    base, remainder = divmod(total, buckets)
    return [base + 1 if i < remainder else base for i in range(buckets)]


def spread_play_timestamps(
    num_plays: int,
    num_days: int,
    lookback_days: int,
    rng: random.Random,
    now: datetime,
) -> list[datetime]:
    # Picks `num_days` distinct days within the lookback window, then
    # distributes `num_plays` across them (every chosen day gets >=1 play) so
    # a synthetic user's history reads as real activity, not a single burst —
    # T44's profile listening summary shows a streak and a 30-day view, both
    # of which need genuine day-to-day spread.
    num_days = max(1, min(num_days, num_plays, lookback_days))
    days_ago = rng.sample(range(lookback_days), num_days)
    plays_per_day = [1] * num_days
    for _ in range(num_plays - num_days):
        plays_per_day[rng.randrange(num_days)] += 1

    timestamps: list[datetime] = []
    for day_offset, count in zip(days_ago, plays_per_day):
        day_start = (now - timedelta(days=day_offset)).replace(hour=0, minute=0, second=0, microsecond=0)
        seconds_used: set[int] = set()
        for _ in range(count):
            while True:
                second_of_day = rng.randrange(0, 86400)
                if second_of_day not in seconds_used:
                    seconds_used.add(second_of_day)
                    break
            timestamps.append(day_start + timedelta(seconds=second_of_day))
    return timestamps


def load_kmeans_artifact(engine: Engine) -> dict:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                'SELECT feature_order, scaler_mean, scaler_std, params '
                'FROM gold."ModelArtifact" WHERE model_name = :n'
            ),
            {"n": "kmeans"},
        ).mappings().first()
    if row is None:
        raise RuntimeError('gold.ModelArtifact("kmeans") not found — run cluster.py (T34) first')
    return {
        "feature_order": row["feature_order"],
        "scaler_mean": row["scaler_mean"],
        "scaler_std": row["scaler_std"],
        "centroids": row["params"]["centroids"],
    }


def load_clusters(engine: Engine) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(
            text('SELECT id, label, centroid FROM gold."Cluster" ORDER BY id')
        ).mappings().all()
    if not rows:
        raise RuntimeError('gold.Cluster is empty — run cluster.py (T34) first')
    return [{"id": r["id"], "label": r["label"], "centroid": r["centroid"]} for r in rows]


def insert_track_pool(engine: Engine, rows: list[dict]) -> int:
    # WHY check existing ids first instead of trusting INSERT ... ON CONFLICT
    # DO NOTHING's rowcount: for a batched/executemany insert, driver rowcount
    # reporting is unreliable across conflicting and non-conflicting rows (it
    # reported "10" on a rerun where 0 rows were actually new) — filtering
    # candidates against what already exists is the only way to know the true
    # count, and it's the same "fetch existing ids first" pattern
    # ingest_kaggle.py already uses.
    if not rows:
        return 0
    candidate_ids = [row["spotify_id"] for row in rows]
    with engine.begin() as conn:
        existing = {
            r[0]
            for r in conn.execute(
                text('SELECT "spotifyId" FROM silver."Track" WHERE "spotifyId" = ANY(:ids)'),
                {"ids": candidate_ids},
            ).fetchall()
        }
        new_rows = [row for row in rows if row["spotify_id"] not in existing]
        if new_rows:
            conn.execute(
                text(
                    'INSERT INTO silver."Track" '
                    '("spotifyId", title, "artistName", danceability, energy, valence, tempo, loudness, "kaggleMatched") '
                    "VALUES (:spotify_id, :title, :artist_name, :danceability, :energy, :valence, :tempo, :loudness, true)"
                ),
                [{**{col: row[col] for col in _TRACK_COLUMNS}, **{
                    "spotify_id": row["spotify_id"], "title": row["title"], "artist_name": row["artist_name"],
                }} for row in new_rows],
            )
    return len(new_rows)


def insert_synthetic_user(engine: Engine, *, handle: str, display_name: str, bio: str) -> Optional[str]:
    user_id = "synth_" + uuid.uuid4().hex
    with engine.begin() as conn:
        row = conn.execute(
            text(
                'INSERT INTO "User" (id, handle, "displayName", bio, "isSynthetic") '
                "VALUES (:id, :handle, :display_name, :bio, true) "
                'ON CONFLICT ("handle") DO NOTHING RETURNING id'
            ),
            {"id": user_id, "handle": handle, "display_name": display_name, "bio": bio},
        ).first()
    return row[0] if row else None


def insert_plays(engine: Engine, user_id: str, plays: list[tuple[str, datetime]]) -> None:
    if not plays:
        return
    with engine.begin() as conn:
        conn.execute(
            text(
                'INSERT INTO silver."Play" (id, "userId", "trackId", "playedAt") '
                "VALUES (:id, :user_id, :track_id, :played_at) "
                'ON CONFLICT ("userId", "playedAt") DO NOTHING'
            ),
            [
                {"id": "play_" + uuid.uuid4().hex, "user_id": user_id, "track_id": track_id, "played_at": played_at}
                for track_id, played_at in plays
            ],
        )


def run_seed(
    csv_path: Path | str,
    engine: Optional[Engine] = None,
    total_users: int = _DEFAULT_TOTAL_USERS,
    pool_size: int = _DEFAULT_POOL_SIZE,
    plays_range: tuple[int, int] = _DEFAULT_PLAYS_RANGE,
    days_range: tuple[int, int] = _DEFAULT_DAYS_RANGE,
    lookback_days: int = _DEFAULT_LOOKBACK_DAYS,
    seed: int = _DEFAULT_SEED,
) -> dict:
    engine = engine or get_engine()
    rng = random.Random(seed)

    artifact = load_kmeans_artifact(engine)
    clusters = load_clusters(engine)
    matched = match_clusters_to_centroids(
        clusters, artifact["centroids"], artifact["scaler_mean"], artifact["scaler_std"], artifact["feature_order"]
    )

    # exclude_ids starts empty (not "whatever Track already has in the DB")
    # so pool selection is a deterministic function of (csv, centroids,
    # pool_size) alone — the same nearest-N every run. That's what makes a
    # rerun idempotent: it recomputes the identical pool and insert_track_pool
    # then no-ops on the rows that already exist. Seeding this from live DB
    # state instead would drift: a rerun would see its OWN prior inserts as
    # "already taken" and pick a different, non-overlapping batch each time —
    # this parameter still exists (and is tested) so callers can pass a real
    # exclusion set for other purposes; run_seed just doesn't need one, since
    # insert_track_pool already protects any real pre-existing Track row from
    # being overwritten (it only inserts ids that don't exist yet).
    pools = build_persona_pools(
        Path(csv_path), matched, artifact["feature_order"], artifact["scaler_mean"], artifact["scaler_std"],
        set(), pool_size,
    )
    all_pool_rows = [row for pool in pools.values() for row in pool]
    tracks_inserted = insert_track_pool(engine, all_pool_rows)

    counts = split_evenly(total_users, len(matched))
    now = datetime.now(timezone.utc)
    users_created = 0
    plays_created = 0
    global_index = 0
    for cluster, n_users in zip(matched, counts):
        pool_ids = [row["spotify_id"] for row in pools[cluster["cluster_id"]]]
        for _ in range(n_users):
            handle = f"synth-listener-{global_index:03d}"
            display_name = f"Listener {global_index:03d}"
            bio = (
                "Synthetic listener seeded for demo purposes (T32; disclosed per ADR-0004 C3). "
                f"Persona: {cluster['label']}."
            )
            global_index += 1

            new_user_id = insert_synthetic_user(engine, handle=handle, display_name=display_name, bio=bio)
            if new_user_id is None:
                continue  # already exists from a prior run — idempotent no-op, leave their plays alone

            users_created += 1
            num_plays = rng.randint(*plays_range)
            num_days = rng.randint(*days_range)
            timestamps = spread_play_timestamps(num_plays, num_days, lookback_days, rng, now)
            plays = [(rng.choice(pool_ids), ts) for ts in timestamps]
            insert_plays(engine, new_user_id, plays)
            plays_created += len(plays)

    print(
        f"Seeded {users_created} synthetic users across {len(matched)} personas "
        f"({plays_created} plays, {tracks_inserted} new Track rows)."
    )
    return {
        "users_created": users_created,
        "plays_created": plays_created,
        "tracks_inserted": tracks_inserted,
        "personas": len(matched),
    }


if __name__ == "__main__":
    run_seed(sys.argv[1])
