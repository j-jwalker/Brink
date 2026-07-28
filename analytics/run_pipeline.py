# WHAT THIS FILE IS
# T38: the idempotent orchestration GitHub Actions runs nightly (+ workflow_dispatch for a
# pre-demo refresh). It sequences the two training steps that already exist and are already
# independently idempotent/tested:
#   - ingest_kaggle.run_ingest — bronze landing (raw Kaggle rows that matched a Track) +
#     silver conform (join audio features onto silver.Track, T31/T33).
#   - cluster.run_cluster — gold train + export (K-means fit + Cluster/ModelMetrics/
#     ModelArtifact, T34).
# T36 (a second, gold-stage regression step) was cut entirely (ADR-0016) — no dataset
# supports a defensible popularity regression — so this pipeline is cluster export only.
#
# WHY this file barely does anything itself: both steps were already built to be safely
# re-run (each replaces its own results rather than accumulating them), so orchestration is
# just "call one, then the other" — there's no new state to coordinate between them beyond
# passing the same Kaggle CSV path and DB engine to both.
#
# Run it directly against the full downloaded CSV: `uv run python run_pipeline.py <path>`.

import json
import sys
from pathlib import Path
from typing import Optional

from sqlalchemy import Engine

from cluster import run_cluster
from db import get_engine
from ingest_kaggle import run_ingest


def run_pipeline(
    kaggle_csv_path: Path | str,
    engine: Optional[Engine] = None,
    cluster_kwargs: Optional[dict] = None,
) -> dict:
    engine = engine or get_engine()
    cluster_kwargs = cluster_kwargs or {}

    print("=== stage: bronze/silver (Kaggle ingest + Track join, T31/T33) ===")
    ingest_summary = run_ingest(kaggle_csv_path, engine=engine)

    print("=== stage: gold (K-means train + export, T34) ===")
    cluster_summary = run_cluster(kaggle_csv_path, engine=engine, **cluster_kwargs)

    return {"ingest": ingest_summary, "cluster": cluster_summary}


if __name__ == "__main__":
    result = run_pipeline(sys.argv[1])
    print("=== pipeline summary ===")
    print(json.dumps(result, default=str, indent=2))
