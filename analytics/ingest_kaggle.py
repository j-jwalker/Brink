# WHAT THIS FILE IS
# T31: matches a Kaggle audio-features CSV onto tracks we already know about
# (from real Spotify plays/posts, T21/T10), then records the result in two
# layers (ADR-0009 medallion):
#   - bronze.kaggle_tracks_raw — a raw-JSON copy of the Kaggle rows we actually
#     used (i.e. the ones that matched a Track), so the original source data
#     for those matches is preserved even if our join logic changes later.
#     Each run replaces the table's contents (delete-then-insert), so
#     re-running never piles up duplicate raw rows.
#   - silver.Track — for each match (spotifyId == the CSV's id column), fill in
#     all 10 kmeans audio features (danceability/energy/valence/tempo/loudness
#     from T31, plus acousticness/instrumentalness/liveness/speechiness/mode
#     added in T33 to match T34's trained feature space) + set
#     kaggleMatched=True. A Track with no Kaggle match is left alone
#     (kaggleMatched keeps its default False) — the fallback for those is
#     built on read by T33's inference module, not this file's job. NOTE: this
#     dataset has no popularity column, so the join never touches
#     Track.popularity — that value already comes from live Spotify data
#     captured when a track is posted/snapshotted (backend/app/tracks.py), not
#     from Kaggle.
#
# WHY bronze only keeps the matched rows, not every Kaggle row: the Kaggle
# file has ~1.2M songs, but only a tiny fraction will ever match something a
# real user has actually played. Landing a raw copy of all 1.2M rows filled
# the database's disk in production. The CSV file itself is already the
# complete archive — nothing is lost by not duplicating the other 99%+ of it
# inside the database too; a future re-run just re-reads the file again.
#
# WHY coverage is logged: ADR-0004 says match coverage must be reported, not
# hidden, since the Kaggle set never covers every real-world track.
#
# Run it directly against a downloaded CSV: `uv run python ingest_kaggle.py <path>`.

import csv
import json
import sys
import uuid
from pathlib import Path
from typing import Optional

from sqlalchemy import Engine, text

from db import get_engine


def _fetch_track_ids(engine: Engine) -> set[str]:
    with engine.connect() as conn:
        return {
            row[0] for row in conn.execute(text('SELECT "spotifyId" FROM silver."Track"')).fetchall()
        }


def _load_matching_rows(csv_path: Path, track_ids: set[str]) -> dict[str, dict[str, str]]:
    # Streams the CSV one row at a time (it's ~1.2M rows — too big to
    # comfortably hold as a list of dicts) and keeps only the rows whose id
    # matches a Track we already know about. Some Kaggle exports repeat an id
    # (e.g. re-released singles); keep the first occurrence so the join is
    # deterministic.
    matches: dict[str, dict[str, str]] = {}
    with csv_path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            row_id = row["id"]
            if row_id in track_ids and row_id not in matches:
                matches[row_id] = row
    return matches


def _land_bronze(engine: Engine, rows: list[dict[str, str]]) -> None:
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM bronze.kaggle_tracks_raw"))
        if not rows:
            return
        conn.execute(
            text(
                "INSERT INTO bronze.kaggle_tracks_raw (id, payload) "
                "VALUES (:id, CAST(:payload AS JSONB))"
            ),
            [{"id": uuid.uuid4().hex, "payload": json.dumps(row)} for row in rows],
        )


def _apply_matches(engine: Engine, matched_rows: dict[str, dict[str, str]]) -> None:
    if not matched_rows:
        return
    with engine.begin() as conn:
        conn.execute(
            text(
                'UPDATE silver."Track" SET '
                "danceability = :danceability, energy = :energy, valence = :valence, "
                "tempo = :tempo, loudness = :loudness, "
                "acousticness = :acousticness, instrumentalness = :instrumentalness, "
                "liveness = :liveness, speechiness = :speechiness, mode = :mode, "
                '"kaggleMatched" = true '
                'WHERE "spotifyId" = :id'
            ),
            [
                {
                    "id": track_id,
                    "danceability": float(row["danceability"]),
                    "energy": float(row["energy"]),
                    "valence": float(row["valence"]),
                    "tempo": float(row["tempo"]),
                    "loudness": float(row["loudness"]),
                    # T33: the remaining 5 kmeans features (T34's FEATURE_ORDER), joined
                    # the same way as the original 5 so a real user's vector is
                    # comparable to what the model was trained on.
                    "acousticness": float(row["acousticness"]),
                    "instrumentalness": float(row["instrumentalness"]),
                    "liveness": float(row["liveness"]),
                    "speechiness": float(row["speechiness"]),
                    "mode": float(row["mode"]),
                }
                for track_id, row in matched_rows.items()
            ],
        )


def _count_cumulative_matches(engine: Engine) -> int:
    with engine.connect() as conn:
        return conn.execute(
            text('SELECT COUNT(*) FROM silver."Track" WHERE "kaggleMatched" = true')
        ).scalar()


def run_ingest(csv_path: Path | str, engine: Optional[Engine] = None) -> dict[str, float]:
    engine = engine or get_engine()
    track_ids = _fetch_track_ids(engine)
    matched_rows = _load_matching_rows(Path(csv_path), track_ids)

    _land_bronze(engine, list(matched_rows.values()))
    _apply_matches(engine, matched_rows)

    # Coverage reflects the database's true, cumulative state — not just this
    # run's matches. A track matched by an earlier ingest (e.g. against a
    # since-replaced Kaggle file) keeps its real features even if it's absent
    # from this run's CSV, and coverage must still count it (ADR-0004: report
    # honestly, don't understate).
    total_tracks = len(track_ids)
    matched = _count_cumulative_matches(engine)
    coverage_pct = (matched / total_tracks * 100) if total_tracks else 0.0
    summary = {"total_tracks": total_tracks, "matched": matched, "coverage_pct": coverage_pct}
    print(
        f"Kaggle match coverage: {summary['matched']}/{summary['total_tracks']} "
        f"({summary['coverage_pct']:.1f}%) — {len(matched_rows)} matched by this run"
    )
    return summary


if __name__ == "__main__":
    run_ingest(sys.argv[1])
