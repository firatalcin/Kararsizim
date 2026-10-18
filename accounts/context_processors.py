from django.conf import settings


def site(request):
    """Settings the shared templates need (login link, verification banner, privacy page)."""
    return {
        "email_features_enabled": settings.EMAIL_FEATURES_ENABLED,
        "contact_email": settings.CONTACT_EMAIL,
    }
