import json
from datetime import timedelta
from importlib import import_module
from unittest import mock

from django.contrib.sessions.models import Session
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from . import throttle
from .models import ThrottleBucket

DEMO_LIMITS = {"demo": (3, 60), "other": (3, 60)}


@override_settings(THROTTLE_ENABLED=True, THROTTLE_LIMITS=DEMO_LIMITS)
class HitTests(TestCase):
    def test_allows_up_to_the_limit_then_blocks(self):
        results = [throttle.hit("demo", "1.2.3.4")[0] for _ in range(5)]
        self.assertEqual(results, [True, True, True, False, False])

    def test_identifiers_and_scopes_are_independent(self):
        for _ in range(3):
            throttle.hit("demo", "a")
        self.assertFalse(throttle.hit("demo", "a")[0])
        self.assertTrue(throttle.hit("demo", "b")[0])
        self.assertTrue(throttle.hit("other", "a")[0])

    def test_retry_after_is_within_the_window(self):
        for _ in range(3):
            throttle.hit("demo", "a")
        allowed, retry_after = throttle.hit("demo", "a")
        self.assertFalse(allowed)
        self.assertTrue(1 <= retry_after <= 60)

    def test_a_new_window_starts_from_zero(self):
        start = timezone.now()
        with mock.patch("core.throttle.timezone.now", return_value=start):
            for _ in range(4):
                throttle.hit("demo", "a")
            self.assertFalse(throttle.hit("demo", "a")[0])
        with mock.patch("core.throttle.timezone.now", return_value=start + timedelta(seconds=61)):
            self.assertTrue(throttle.hit("demo", "a")[0])

    def test_keys_are_keyed_hashes_of_the_identifier(self):
        with override_settings(SECRET_KEY="a" * 50):
            throttle.hit("demo", "203.0.113.7")
        with override_settings(SECRET_KEY="b" * 50):
            throttle.hit("demo", "203.0.113.7")
        first, second = ThrottleBucket.objects.order_by("pk")
        self.assertEqual(len(first.key), 64)
        self.assertNotEqual(first.key, second.key)

    def test_expired_rows_are_purged_now_and_then(self):
        past = timezone.now() - timedelta(hours=1)
        ThrottleBucket.objects.create(key="old", count=1, expires_at=past)
        with mock.patch("core.throttle.random.random", return_value=0.99):
            throttle.hit("demo", "a")
        self.assertTrue(ThrottleBucket.objects.filter(key="old").exists())
        with mock.patch("core.throttle.random.random", return_value=0.0):
            throttle.hit("demo", "a")
        self.assertFalse(ThrottleBucket.objects.filter(key="old").exists())


class DataApiGrantsMigrationTests(TestCase):
    """Supabase's Data API roles must not keep table privileges: RLS should not be the only barrier."""

    def revoke(self, vendor):
        migration = import_module("core.migrations.0002_revoke_data_api_grants")
        editor = mock.Mock(connection=mock.Mock(vendor=vendor))
        migration.revoke(None, editor)
        return editor

    def test_it_does_nothing_outside_postgres(self):
        self.revoke("sqlite").execute.assert_not_called()

    def test_on_postgres_it_revokes_only_when_the_supabase_roles_exist(self):
        editor = self.revoke("postgresql")
        editor.execute.assert_called_once()
        sql = editor.execute.call_args.args[0]
        self.assertIn("rolname = 'anon'", sql)
        self.assertIn("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon, authenticated", sql)
        self.assertIn("ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM anon, authenticated", sql)


class DisabledTests(TestCase):
    @override_settings(THROTTLE_ENABLED=False, THROTTLE_LIMITS=DEMO_LIMITS)
    def test_nothing_is_blocked_or_stored(self):
        for _ in range(10):
            self.assertTrue(throttle.hit("demo", "a")[0])
        self.assertFalse(ThrottleBucket.objects.exists())


class PurgeTests(TestCase):
    def test_removes_expired_buckets_and_sessions_only(self):
        now = timezone.now()
        ThrottleBucket.objects.create(key="old", count=1, expires_at=now - timedelta(seconds=1))
        ThrottleBucket.objects.create(key="new", count=1, expires_at=now + timedelta(hours=1))
        Session.objects.create(session_key="old", session_data="x", expire_date=now - timedelta(days=1))
        Session.objects.create(session_key="new", session_data="x", expire_date=now + timedelta(days=1))
        throttle.purge_expired()
        self.assertEqual(list(ThrottleBucket.objects.values_list("key", flat=True)), ["new"])
        self.assertEqual(list(Session.objects.values_list("session_key", flat=True)), ["new"])


class ClientIpTests(TestCase):
    rf = RequestFactory()

    def test_uses_remote_addr_by_default(self):
        request = self.rf.get("/", REMOTE_ADDR="198.51.100.4", HTTP_X_FORWARDED_FOR="203.0.113.9")
        self.assertEqual(throttle.client_ip(request), "198.51.100.4")

    @override_settings(CLIENT_IP_HEADER="HTTP_X_FORWARDED_FOR")
    def test_uses_the_configured_header_leftmost_value(self):
        request = self.rf.get("/", REMOTE_ADDR="10.0.0.1", HTTP_X_FORWARDED_FOR="203.0.113.9, 10.1.1.1")
        self.assertEqual(throttle.client_ip(request), "203.0.113.9")

    @override_settings(CLIENT_IP_HEADER="HTTP_X_FORWARDED_FOR")
    def test_missing_or_garbage_header_falls_back_to_remote_addr(self):
        self.assertEqual(throttle.client_ip(self.rf.get("/", REMOTE_ADDR="198.51.100.4")), "198.51.100.4")
        request = self.rf.get("/", REMOTE_ADDR="198.51.100.4", HTTP_X_FORWARDED_FOR="not-an-ip")
        self.assertEqual(throttle.client_ip(request), "198.51.100.4")

    def test_ipv6_addresses_are_grouped_by_their_64_bit_prefix(self):
        def ip(address):
            return throttle.client_ip(self.rf.get("/", REMOTE_ADDR=address))

        self.assertEqual(ip("2001:db8:1:2::1"), ip("2001:db8:1:2:ffff:ffff:ffff:ffff"))
        self.assertNotEqual(ip("2001:db8:1:2::1"), ip("2001:db8:1:3::1"))


@override_settings(THROTTLE_ENABLED=True, THROTTLE_LIMITS={"demo": (2, 60)})
class ThrottlePostTests(TestCase):
    rf = RequestFactory()

    def setUp(self):
        @throttle.throttle_post("demo")
        def view(request):
            return HttpResponse("ok")

        self.view = view

    def post(self, **extra):
        return self.view(self.rf.post("/", **extra))

    def test_only_posts_are_counted(self):
        for _ in range(5):
            self.assertEqual(self.view(self.rf.get("/")).status_code, 200)
        self.assertEqual([self.post().status_code for _ in range(3)], [200, 200, 429])

    def test_html_response_explains_and_sets_retry_after(self):
        self.post(), self.post()
        response = self.post()
        self.assertEqual(response.status_code, 429)
        self.assertContains(response, "Çok fazla deneme", status_code=429)
        self.assertTrue(1 <= int(response["Retry-After"]) <= 60)

    def test_json_clients_get_json(self):
        self.post(), self.post()
        response = self.post(HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response["Content-Type"], "application/json")
        data = json.loads(response.content)
        self.assertEqual(data["ok"], False)
        self.assertIn("Çok fazla deneme", data["error"])

    def test_a_missing_identifier_is_not_counted(self):
        @throttle.throttle_post("demo", ident=lambda request: None)
        def view(request):
            return HttpResponse("ok")

        self.assertEqual([view(self.rf.post("/")).status_code for _ in range(5)], [200] * 5)
        self.assertFalse(ThrottleBucket.objects.exists())

    def test_identifier_can_be_customised(self):
        @throttle.throttle_post("demo", ident=lambda request: request.POST["who"])
        def view(request):
            return HttpResponse("ok")

        statuses = [view(self.rf.post("/", {"who": who})).status_code for who in "aabbaab"]
        self.assertEqual(statuses, [200, 200, 200, 200, 429, 429, 429])
