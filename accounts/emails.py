"""E-mail address verification: a signed link that proves the owner can read the address."""

from django.contrib.auth import get_user_model
from django.core import signing
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse

VERIFY_SALT = "kararsizim.verify-email"
VERIFY_MAX_AGE = 3 * 24 * 60 * 60


def make_verification_token(user):
    return signing.dumps({"uid": user.pk, "email": user.email}, salt=VERIFY_SALT)


def read_verification_token(token):
    """The user a token was issued for, or None if it is forged, expired or for an old address."""
    try:
        data = signing.loads(token, salt=VERIFY_SALT, max_age=VERIFY_MAX_AGE)
    except signing.BadSignature:  # includes SignatureExpired
        return None
    return get_user_model().objects.filter(pk=data.get("uid"), email=data.get("email")).first()


def send_verification_email(request, user):
    url = request.build_absolute_uri(reverse("accounts:verify_email", args=[make_verification_token(user)]))
    body = render_to_string("accounts/email/verify_email.txt", {"user": user, "url": url})
    send_mail("E-postanı doğrula · Kararsızım", body, None, [user.email])
