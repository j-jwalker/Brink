# WHAT THIS FILE IS
# Automated checks for the data model in app/models.py. WHY: these run in CI on
# every change and fail loudly if a model drifts from what we expect (a missing
# table, a broken "no duplicates" rule, a wrong delete rule). A test named
# test_* is picked up and run automatically by pytest; `assert X` means "X must be
# true, or the test fails."

from sqlmodel import SQLModel

from app import models

# The exact set of tables we expect to exist. If a table is added or removed
# without updating this, the first test below fails on purpose.
# NOTE (T39, ADR-0009 medallion layering): tables now live in Postgres SCHEMAS, so
# metadata keys are schema-qualified ("silver.Track"), except the public social/auth
# tables which stay unqualified. `UserStats`/`TasteVector`/`Compatibility` were dropped
# (computed on read now — ADR-0003); `ModelArtifact` + the bronze raw tables were added.
EXPECTED_TABLES = {
    # public schema — identity + social + rate limiting
    "User",
    "SpotifyToken",
    "Post",
    "Reaction",
    "Comment",
    "Follow",
    "ArtistPost",
    "ArtistReaction",  # added in T52 — engagement on artist posts
    "ArtistComment",   # added in T52 — engagement on artist posts
    "RateLimitHit",  # added in T10 for rate limiting (ADR-0011)
    # silver schema — conformed play/track data
    "silver.Track",
    "silver.Play",
    # gold schema — analytics results / model artifacts
    "gold.Cluster",
    "gold.ModelMetrics",
    "gold.ModelArtifact",  # added in T39 (self-describing model params)
    # bronze schema — raw immutable landing
    "bronze.spotify_recently_played_raw",
    "bronze.kaggle_tracks_raw",
}


# All expected tables are present (no more, no fewer).
def test_all_expected_tables_registered():
    assert set(SQLModel.metadata.tables) == EXPECTED_TABLES


# The fixed value lists (enums) still match what the database expects.
def test_enums_preserve_prisma_values_and_type_names():
    assert [e.value for e in models.PostSource] == ["MANUAL", "SPOTIFY"]
    assert [e.value for e in models.ReactionType] == ["HEART", "FIRE", "SPARKLE"]
    assert models.Post.__table__.c.source.type.name == "PostSource"
    assert models.Reaction.__table__.c.type.type.name == "ReactionType"


# The "no duplicates" rules exist and are actually marked unique.
def test_unique_dedup_indexes():
    idx = {i.name: i for i in models.Reaction.__table__.indexes}
    assert idx["Reaction_postId_userId_type_key"].unique
    play_idx = {i.name: i for i in models.Play.__table__.indexes}
    assert play_idx["Play_userId_playedAt_key"].unique


# Tables whose ID is made of two columns together (e.g. follower + following).
def test_composite_primary_keys():
    assert {c.name for c in models.Follow.__table__.primary_key.columns} == {
        "followerId",
        "followingId",
    }


# The "what happens on delete" rules are set correctly for a few key links.
def test_cascade_and_restrict_delete_rules():
    def ondelete(attr):
        # Dig out the delete rule attached to a linking (foreign key) column.
        fk = next(iter(attr.property.columns[0].foreign_keys))
        return fk.ondelete

    assert ondelete(models.SpotifyToken.user_id) == "CASCADE"   # delete user -> delete their token
    assert ondelete(models.Play.track_id) == "RESTRICT"         # can't delete a song still in use


def test_snake_case_attrs_map_to_camelcase_columns():
    # The ORM attribute is snake_case; the actual DB column stays camelCase (legacy Prisma tables).
    assert models.User.display_name.property.columns[0].name == "displayName"
    assert models.Track.album_art_url.property.columns[0].name == "albumArtUrl"


def test_medallion_schemas_assigned():
    # T39: the moved/new tables carry their medallion schema (ADR-0009).
    assert models.Track.__table__.schema == "silver"
    assert models.Play.__table__.schema == "silver"
    assert models.Cluster.__table__.schema == "gold"
    assert models.ModelMetrics.__table__.schema == "gold"
    assert models.ModelArtifact.__table__.schema == "gold"


def test_model_artifact_new_table_uses_snake_case_columns():
    # New (non-Prisma) tables use snake_case columns directly — no camelCase legacy alias.
    assert models.ModelArtifact.feature_order.property.columns[0].name == "feature_order"
    assert {c.name for c in models.ModelArtifact.__table__.primary_key.columns} == {"model_name"}


def test_track_carries_all_ten_kmeans_features():
    # T33 prerequisite: the trained ModelArtifact("kmeans")'s featureOrder (T34,
    # analytics/cluster.py FEATURE_ORDER) has 10 audio features, but Track only had
    # columns for the first 5 (from T31's join). On-demand inference can't build a
    # taste vector comparable to what the model was trained on until Track carries
    # all 10 — see T33's ticket "New prerequisite surfaced by T34".
    kmeans_feature_order = [
        "danceability", "energy", "valence", "tempo", "loudness",
        "acousticness", "instrumentalness", "liveness", "speechiness", "mode",
    ]
    track_columns = {c.name for c in models.Track.__table__.columns}
    missing = [f for f in kmeans_feature_order if f not in track_columns]
    assert not missing, f"Track is missing kmeans feature columns: {missing}"
