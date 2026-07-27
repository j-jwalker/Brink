# WHAT THIS FILE IS
# Checks the resilient artist-image signing helper (app/security/supabase.py):
#   create_signed_read_url_or_blank(bucket, path) -> a signed read URL, or "" if signing FAILS.
# WHY it exists (T103): a private-bucket signing failure (bad creds, missing object, Storage outage)
# must NEVER take down the feed or the artist page — a blank URL lets the template show a placeholder
# instead. These tests stub the underlying create_signed_read_url so no real Supabase is touched.

from app.security import supabase


# On success the wrapper just passes the signed URL straight through (no behavior change).
def test_or_blank_passes_through_on_success(monkeypatch):
    monkeypatch.setattr(
        supabase, "create_signed_read_url",
        lambda bucket, path, expires_in=3600: f"https://signed/{bucket}/{path}",
    )
    assert supabase.create_signed_read_url_or_blank("artist-images", "a/b.png") == \
        "https://signed/artist-images/a/b.png"


# When the underlying signer RAISES (the production incident: StorageApiError 404), the wrapper
# swallows it and returns "" — the caller renders a placeholder instead of 500ing / blanking a page.
def test_or_blank_returns_empty_on_failure(monkeypatch):
    def boom(bucket, path, expires_in=3600):
        raise RuntimeError("StorageApiError: Object not found")

    monkeypatch.setattr(supabase, "create_signed_read_url", boom)
    assert supabase.create_signed_read_url_or_blank("artist-images", "a/b.png") == ""


# A SINGLE transient blip (network hiccup / free-tier cold start) must NOT blank the image: the
# wrapper retries and succeeds. This is the fix for the "sometimes the image shows, sometimes it
# doesn't" flicker — before, one failure gave up immediately and fell back to the placeholder.
def test_or_blank_retries_a_transient_failure(monkeypatch):
    calls = {"n": 0}

    def flaky(bucket, path, expires_in=3600):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("transient network blip")
        return f"https://signed/{bucket}/{path}"

    monkeypatch.setattr(supabase, "create_signed_read_url", flaky)
    assert supabase.create_signed_read_url_or_blank("artist-images", "a/b.png") == \
        "https://signed/artist-images/a/b.png"
    assert calls["n"] == 2  # it retried once after the blip, instead of giving up
