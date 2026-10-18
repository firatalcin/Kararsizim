"""Rate limiting without extra dependencies: fixed-window counters in the database.

Counters live in ThrottleBucket (an atomic UPDATE ... SET count = count + 1), so they work across
serverless instances. Keys are keyed hashes of scope + identifier + window, so no IP address or
e-mail is stored. Limits are configured in settings.THROTTLE_LIMITS as {scope: (max, window_seconds)}.
"""

import ipaddress
import random
from datetime import datetime, timezone as dt_timezone
from functools import wraps

from django.conf import settings
from django.contrib.sessions.models import Session
from django.db import transaction
from django.db.models import F
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.crypto import salted_hmac

from .models import ThrottleBucket

KEY_SALT = "kararsizim.throttle"
PURGE_PROBABILITY = 0.02
MESSAGE = "Çok fazla deneme yaptın. Biraz bekleyip tekrar dene."


def _parse_ip(value):
    try:
        return ipaddress.ip_address(value.strip())
    except ValueError:
        return None


def client_ip(request):
    """The visitor's IP; IPv6 addresses are reduced to their /64 prefix (one customer, one prefix).

    settings.CLIENT_IP_HEADER names the request header to trust (Vercel overwrites X-Forwarded-For,
    so it cannot be spoofed there); anything else falls back to REMOTE_ADDR.
    """
    address = None
    header = settings.CLIENT_IP_HEADER
    if header != "REMOTE_ADDR":
        address = _parse_ip(request.META.get(header, "").split(",")[0])
    if address is None:
        address = _parse_ip(request.META.get("REMOTE_ADDR", ""))
    if address is None:
        return "unknown"
    if address.version == 6:
        if address.ipv4_mapped:
            return str(address.ipv4_mapped)
        return str(ipaddress.ip_network(f"{address}/64", strict=False).network_address)
    return str(address)


def purge_expired():
    """Delete finished windows and expired sessions (nothing else cleans them up on Vercel)."""
    now = timezone.now()
    ThrottleBucket.objects.filter(expires_at__lt=now).delete()
    Session.objects.filter(expire_date__lt=now).delete()


def hit(scope, ident):
    """Count one request. Returns (allowed, seconds until the window resets)."""
    if not settings.THROTTLE_ENABLED:
        return True, 0
    limit, window = settings.THROTTLE_LIMITS[scope]
    now = timezone.now()
    index = int(now.timestamp()) // window
    window_end = (index + 1) * window
    key = salted_hmac(KEY_SALT, f"{scope}|{ident}|{index}", algorithm="sha256").hexdigest()

    with transaction.atomic():
        bucket, created = ThrottleBucket.objects.get_or_create(
            key=key,
            defaults={"count": 1, "expires_at": datetime.fromtimestamp(window_end, tz=dt_timezone.utc)},
        )
        if not created:
            ThrottleBucket.objects.filter(pk=bucket.pk).update(count=F("count") + 1)
            bucket.refresh_from_db(fields=["count"])

    if random.random() < PURGE_PROBABILITY:
        purge_expired()
    return bucket.count <= limit, max(1, int(window_end - now.timestamp()))


def too_many_requests(request, retry_after):
    if "application/json" in request.headers.get("Accept", ""):
        response = JsonResponse({"ok": False, "error": MESSAGE}, status=429)
    else:
        minutes = max(1, -(-retry_after // 60))
        response = render(request, "429.html", {"message": MESSAGE, "minutes": minutes}, status=429)
    response["Retry-After"] = str(retry_after)
    return response


def throttle_post(scope, ident=None):
    """Decorator: limit POSTs to a view.

    `ident(request, *args, **kwargs)` defaults to the client IP; returning None skips the count.
    """

    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if request.method == "POST":
                who = ident(request, *args, **kwargs) if ident else client_ip(request)
                if who is not None:
                    allowed, retry_after = hit(scope, who)
                    if not allowed:
                        return too_many_requests(request, retry_after)
            return view(request, *args, **kwargs)

        return wrapper

    return decorator
