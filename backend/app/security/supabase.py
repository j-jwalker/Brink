# WHAT THIS FILE IS
# A small wrapper around Supabase (our login/auth provider). It builds a "service
# role" client — an admin connection with full access — used on the SERVER only to
# verify a user's login token. WHY server-only: the service-role key can do anything,
# so it must NEVER be sent to the browser.

import logging
from functools import lru_cache
from typing import Optional

from supabase import Client, create_client
from supabase.client import ClientOptions
from supabase_auth.types import Session, User

from app.config import get_settings

logger = logging.getLogger(__name__)


# Build the admin client once and reuse it (@lru_cache = build-once-then-reuse).
@lru_cache
def admin() -> Client:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise ValueError("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set")
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def _pkce_client() -> Client:
    # A FRESH client configured for the PKCE OAuth flow (used by the server-side Spotify
    # login, T09). WHY fresh (not @lru_cache like admin()): sign_in_with_oauth stashes a
    # one-time "code_verifier" in the client's in-memory storage, so two concurrent logins
    # sharing one cached client could clobber each other's verifier before we read it.
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise ValueError("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set")
    return create_client(
        settings.supabase_url,
        settings.supabase_service_role_key,
        options=ClientOptions(flow_type="pkce"),
    )


def _password_client() -> Client:
    # A FRESH default client (no PKCE) for email/password auth (T03, ADR-0015). WHY fresh and
    # NOT the cached admin() client: sign_up / sign_in_with_password store the resulting user
    # session in the client's in-memory storage. admin() is shared and used for SERVICE-ROLE
    # calls (verifying tokens, storage) — letting a user session land on it could make a later
    # admin call act as that user. A throwaway client per call keeps each signup/login isolated
    # (same reasoning as _pkce_client). WHY still the service-role key: it's the only Supabase
    # key the server holds, and for sign_up / sign_in_with_password it just authenticates the
    # request — the password itself is what proves the user — and the client is discarded after.
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise ValueError("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set")
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def sign_up_email(email: str, password: str, email_redirect_to: Optional[str] = None):
    # Create an email/password account (ADR-0015). Returns the SDK's AuthResponse, which carries
    # a `.user` and — only once the email is confirmed — a `.session`. With "Confirm email" ON
    # (our setting), sign_up returns a user but NO usable session, so the caller shows a "check
    # your inbox" state rather than logging the person straight in. `email_redirect_to` is where
    # Supabase's confirmation link sends the browser back (our /auth/confirm URL).
    credentials = {"email": email, "password": password}
    if email_redirect_to:
        credentials["options"] = {"email_redirect_to": email_redirect_to}
    return _password_client().auth.sign_up(credentials)


def sign_in_password(email: str, password: str):
    # Log in with an email/password (ADR-0015). Returns the SDK's AuthResponse with `.session`
    # (access + refresh tokens) and `.user` — the SAME shapes the Spotify callback consumes, so
    # the caller reuses get_or_create_user + login_session.set_cookie. The SDK RAISES on bad
    # credentials (AuthApiError); the caller catches it and shows a generic, non-enumerating error.
    return _password_client().auth.sign_in_with_password({"email": email, "password": password})


def oauth_authorize(redirect_to: str, scopes: str) -> tuple[str, str]:
    # Start a server-side Spotify login (PKCE). Returns (authorize_url, code_verifier):
    #   - authorize_url — where we redirect the browser to sign in with Spotify.
    #   - code_verifier — a one-time secret PKCE generates; it must be replayed to
    #     exchange_code() on the callback. PKCE cryptographically binds the login code to
    #     this browser, so a stolen code is useless without the matching verifier.
    # The caller stores the verifier in a short-lived encrypted cookie until the callback.
    client = _pkce_client()
    resp = client.auth.sign_in_with_oauth(
        {"provider": "spotify", "options": {"redirect_to": redirect_to, "scopes": scopes}}
    )
    verifier = client.auth._storage.get_item(f"{client.auth._storage_key}-code-verifier")
    return resp.url, verifier


def exchange_code(auth_code: str, code_verifier: str) -> Optional[Session]:
    # Finish the server-side login: swap the one-time `auth_code` Spotify sent to our
    # callback for a Supabase session, using the PKCE `code_verifier` we stored at login.
    # The returned Session carries the user AND the Spotify provider tokens
    # (provider_token / provider_refresh_token) we encrypt and store. Returns None if the
    # exchange yields no session.
    client = _pkce_client()
    response = client.auth.exchange_code_for_session(
        {"auth_code": auth_code, "code_verifier": code_verifier}
    )
    return response.session if response else None


def refresh_session(refresh_token: str) -> Optional[Session]:
    # Trade a Supabase refresh token for a fresh session (new access + refresh tokens).
    # Used by require_user when a logged-in page request arrives with an expired access
    # token, so the user stays signed in without logging in again. Returns None if no
    # session comes back; raises if Supabase rejects the refresh token (caller treats
    # that as "session invalid → re-login").
    response = admin().auth.refresh_session(refresh_token)
    return response.session if response else None


def create_signed_upload_url(bucket: str, path: str) -> dict:
    # Mint a Supabase Storage "signed upload URL" (T50): a short-lived, single-use URL that lets
    # the browser upload ONE file straight to `path` in a PRIVATE bucket, WITHOUT ever seeing the
    # service-role key. WHY this shape: the browser can't be trusted with admin credentials, so the
    # server (which holds the key) signs a narrow permission for exactly one object path and hands
    # back just that. Returns Supabase's dict: {"signed_url", "token", "path"}.
    return admin().storage.from_(bucket).create_signed_upload_url(path)


def create_signed_read_url(bucket: str, path: str, expires_in: int = 3600) -> str:
    # Mint a Supabase Storage "signed READ url" (T53) — the display-side sibling of
    # create_signed_upload_url above. WHY it's needed: the artist-images bucket is PRIVATE
    # (ADR-0008), so a raw storage path in an <img src> is rejected and the image never renders —
    # not even for the artist who uploaded it. This asks Supabase (as the server, holding the
    # service-role key) to sign a time-limited URL for one object; expiry (default 1 hour) keeps a
    # leaked URL short-lived.
    data = admin().storage.from_(bucket).create_signed_url(path, expires_in)
    # The key's casing has differed across supabase-py releases ("signedURL" vs "signedUrl"),
    # so accept either rather than break images on a library upgrade.
    signed = data.get("signedURL") or data.get("signedUrl") or ""
    # Likewise the VALUE has differed: older releases return a path RELATIVE to the storage API
    # (e.g. "/object/sign/<bucket>/<path>?token=..."), while the currently installed one returns
    # the full absolute URL (verified live against brink-dev — blindly prefixing doubled the host
    # and broke the image). Only prefix "{SUPABASE_URL}/storage/v1" when we got the relative form.
    if signed.startswith("http"):
        return signed
    return f"{get_settings().supabase_url}/storage/v1{signed}"


def create_signed_read_url_or_blank(bucket: str, path: str, expires_in: int = 3600,
                                    attempts: int = 2) -> str:
    # The RESILIENT sibling of create_signed_read_url (T103). WHY it exists: signing hits Supabase
    # Storage over the network and RAISES on any failure — a missing object, a wrong/expired
    # service-role key, or a Storage outage. On 2026-07-22 exactly that (a bad Render key ->
    # StorageApiError 404) took down the WHOLE feed and 500'd the artist page, because the callers
    # let the exception propagate. A single un-signable artist image must never do that. So any
    # display surface that signs an artist image calls THIS: on failure we log it and return "" (an
    # empty URL), and the template renders a muted placeholder instead of a broken <img> or a crash.
    #
    # RETRY (fixes the "images show sometimes, not others" flicker): a SINGLE transient hiccup — a
    # network blip, or the free-tier server waking from sleep — used to blank an image for that whole
    # page load, because we gave up after one try. Now we retry the sign a couple of times before
    # degrading, so only a *persistent* failure falls back to the placeholder. The signing call is
    # fast and there are only a handful of artist images per page, so the extra attempt is cheap.
    last_error: Exception | None = None
    for _ in range(max(1, attempts)):
        try:
            return create_signed_read_url(bucket, path, expires_in)
        except Exception as e:  # noqa: BLE001 - degrade only after all retries, never crash a page
            last_error = e
    logger.warning("signed read URL unavailable for %s/%s after %d attempts: %s",
                   bucket, path, attempts, last_error)
    return ""


def public_object_url(bucket: str, path: str) -> str:
    # Build the public read URL for an object in a PUBLIC Supabase Storage bucket (T48, the avatars
    # bucket). WHY no signing (unlike create_signed_read_url): a public bucket serves its objects to
    # anyone, so there's no token/expiry — the URL is just a fixed path off SUPABASE_URL. We store
    # THIS on User.avatar_url so a profile picture renders directly in an <img src> forever.
    return f"{get_settings().supabase_url}/storage/v1/object/public/{bucket}/{path}"


def get_user_from_token(token: str) -> Optional[User]:
    # Ask Supabase "who does this login token belong to?" It checks the token against
    # Supabase's auth server and returns that user.
    # CONTRACT (verified against supabase_auth 2.31.0): get_user RAISES AuthApiError
    # for an INVALID/expired token; it returns a response with `user=None` only for an
    # empty token string. So callers must handle the raised error — they cannot rely on
    # a None return to mean "bad token". (deps.require_user catches the raise and turns
    # it into a 401.) Kept as its own function so tests can stand in a fake with no network.
    response = admin().auth.get_user(token)
    return response.user if response else None
