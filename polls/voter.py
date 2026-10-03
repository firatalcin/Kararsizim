"""Anonymous visitor identity: a random token in a signed cookie."""

import uuid

from django.conf import settings

COOKIE_NAME = "kz_voter"
COOKIE_SALT = "kararsizim.voter"
COOKIE_MAX_AGE = 365 * 24 * 60 * 60


def get_voter_token(request):
    """The visitor's token, or None if the cookie is missing or its signature is invalid."""
    return request.get_signed_cookie(COOKIE_NAME, default=None, salt=COOKIE_SALT)


def ensure_voter_token(request):
    """Return (token, is_new). A new token must be stored with set_voter_cookie()."""
    token = get_voter_token(request)
    if token:
        return token, False
    return uuid.uuid4().hex, True


def set_voter_cookie(response, token):
    response.set_signed_cookie(
        COOKIE_NAME,
        token,
        salt=COOKIE_SALT,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="Lax",
        secure=not settings.DEBUG,
    )
