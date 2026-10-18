import json
import os
import re
import subprocess
import sys
from pathlib import Path

from django.test import TestCase

BASE_DIR = Path(__file__).resolve().parent.parent


def load_settings(**env):
    """Import config.settings in a fresh interpreter with a controlled environment.

    Returns (CompletedProcess, dict of selected settings). The dict is empty if the import failed.
    """
    clean = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("DJANGO_", "VERCEL", "EMAIL_", "DATABASE_URL"))
    }
    clean.update(env)
    code = (
        "import json, os\n"
        "os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'\n"
        "from django.conf import settings\n"
        "print(json.dumps({\n"
        "  'DEBUG': settings.DEBUG,\n"
        "  'ALLOWED_HOSTS': settings.ALLOWED_HOSTS,\n"
        "  'HSTS': settings.SECURE_HSTS_SECONDS,\n"
        "  'HSTS_SUBDOMAINS': settings.SECURE_HSTS_INCLUDE_SUBDOMAINS,\n"
        "  'HSTS_PRELOAD': settings.SECURE_HSTS_PRELOAD,\n"
        "  'DB_OPTIONS': settings.DATABASES['default'].get('OPTIONS', {}),\n"
        "  'EMAIL_ENABLED': settings.EMAIL_FEATURES_ENABLED,\n"
        "  'EMAIL_BACKEND': settings.EMAIL_BACKEND,\n"
        "  'FROM': settings.DEFAULT_FROM_EMAIL,\n"
        "  'CLIENT_IP_HEADER': settings.CLIENT_IP_HEADER,\n"
        "}))\n"
    )
    result = subprocess.run([sys.executable, "-c", code], cwd=BASE_DIR, env=clean, capture_output=True, text=True)
    data = json.loads(result.stdout) if result.returncode == 0 else {}
    return result, data


class DebugDefaultTests(TestCase):
    def test_debug_is_off_by_default_and_needs_a_secret_key(self):
        result, _ = load_settings()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DJANGO_SECRET_KEY", result.stderr)

    def test_explicit_debug_works_locally(self):
        result, data = load_settings(DJANGO_DEBUG="True")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIs(data["DEBUG"], True)

    def test_debug_is_refused_on_vercel(self):
        result, _ = load_settings(DJANGO_DEBUG="True", VERCEL="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Vercel", result.stderr)

    def test_production_settings_with_key(self):
        result, data = load_settings(DJANGO_SECRET_KEY="x" * 50)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIs(data["DEBUG"], False)


class AllowedHostsTests(TestCase):
    def test_default_does_not_allow_every_vercel_app(self):
        _, data = load_settings(DJANGO_DEBUG="True")
        self.assertEqual(data["ALLOWED_HOSTS"], ["localhost", "127.0.0.1"])

    def test_hosts_come_from_the_environment(self):
        _, data = load_settings(DJANGO_DEBUG="True", DJANGO_ALLOWED_HOSTS="kararsizim.vercel.app, example.com")
        self.assertEqual(data["ALLOWED_HOSTS"], ["kararsizim.vercel.app", "example.com"])


class HstsTests(TestCase):
    def test_default_is_short_without_subdomains(self):
        _, data = load_settings(DJANGO_SECRET_KEY="x" * 50)
        self.assertEqual(data["HSTS"], 3600)
        self.assertIs(data["HSTS_SUBDOMAINS"], False)
        self.assertIs(data["HSTS_PRELOAD"], False)

    def test_can_be_raised_from_the_environment(self):
        _, data = load_settings(
            DJANGO_SECRET_KEY="x" * 50,
            DJANGO_HSTS_SECONDS="31536000",
            DJANGO_HSTS_INCLUDE_SUBDOMAINS="True",
            DJANGO_HSTS_PRELOAD="True",
        )
        self.assertEqual(data["HSTS"], 31536000)
        self.assertIs(data["HSTS_SUBDOMAINS"], True)
        self.assertIs(data["HSTS_PRELOAD"], True)


class DatabaseSslTests(TestCase):
    url = "postgresql://u:p@db.example.com:6543/postgres"

    def test_default_requires_ssl(self):
        _, data = load_settings(DJANGO_DEBUG="True", DATABASE_URL=self.url)
        self.assertEqual(data["DB_OPTIONS"]["sslmode"], "require")
        self.assertNotIn("sslrootcert", data["DB_OPTIONS"])

    def test_certificate_verification_can_be_enabled(self):
        _, data = load_settings(
            DJANGO_DEBUG="True",
            DATABASE_URL=self.url,
            DJANGO_DB_SSLMODE="verify-full",
            DJANGO_DB_SSLROOTCERT="/certs/supabase.crt",
        )
        self.assertEqual(data["DB_OPTIONS"]["sslmode"], "verify-full")
        self.assertEqual(data["DB_OPTIONS"]["sslrootcert"], "/certs/supabase.crt")


class EmailSettingsTests(TestCase):
    prod = {"DJANGO_SECRET_KEY": "x" * 50}

    def test_email_features_are_off_without_a_mail_server(self):
        _, data = load_settings(**self.prod)
        self.assertIs(data["EMAIL_ENABLED"], False)

    def test_a_configured_smtp_server_turns_them_on(self):
        _, data = load_settings(**self.prod, EMAIL_HOST="smtp.example.com", DEFAULT_FROM_EMAIL="Kararsızım <a@b.co>")
        self.assertIs(data["EMAIL_ENABLED"], True)
        self.assertEqual(data["EMAIL_BACKEND"], "django.core.mail.backends.smtp.EmailBackend")
        self.assertEqual(data["FROM"], "Kararsızım <a@b.co>")

    def test_enabling_them_in_production_without_a_server_is_refused(self):
        result, _ = load_settings(**self.prod, DJANGO_EMAIL_ENABLED="True")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("EMAIL_HOST", result.stderr)

    def test_local_development_can_print_mails_to_the_console(self):
        _, data = load_settings(DJANGO_DEBUG="True", DJANGO_EMAIL_ENABLED="True")
        self.assertIs(data["EMAIL_ENABLED"], True)
        self.assertEqual(data["EMAIL_BACKEND"], "django.core.mail.backends.console.EmailBackend")


class ClientIpHeaderTests(TestCase):
    def test_remote_addr_is_trusted_by_default(self):
        _, data = load_settings(DJANGO_DEBUG="True")
        self.assertEqual(data["CLIENT_IP_HEADER"], "REMOTE_ADDR")

    def test_on_vercel_the_forwarded_header_is_used(self):
        _, data = load_settings(DJANGO_SECRET_KEY="x" * 50, VERCEL="1")
        self.assertEqual(data["CLIENT_IP_HEADER"], "HTTP_X_FORWARDED_FOR")

    def test_it_can_be_overridden(self):
        _, data = load_settings(DJANGO_DEBUG="True", DJANGO_CLIENT_IP_HEADER="HTTP_X_REAL_IP")
        self.assertEqual(data["CLIENT_IP_HEADER"], "HTTP_X_REAL_IP")


class SecurityHeadersTests(TestCase):
    def test_pages_send_csp_and_permissions_policy(self):
        response = self.client.get("/")
        csp = response["Content-Security-Policy"]
        for directive in (
            "default-src 'self'",
            "script-src 'self'",
            "object-src 'none'",
            "base-uri 'self'",
            "form-action 'self'",
            "frame-ancestors 'none'",
        ):
            self.assertIn(directive, csp)
        self.assertNotIn("script-src 'self' 'unsafe-inline'", csp)
        self.assertIn("camera=()", response["Permissions-Policy"])

    def test_error_pages_are_covered_too(self):
        response = self.client.get("/yok-boyle-bir-sayfa/")
        self.assertEqual(response.status_code, 404)
        self.assertIn("Content-Security-Policy", response)

    def test_admin_is_left_alone(self):
        response = self.client.get("/admin/login/")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Content-Security-Policy", response)

    def test_pages_stay_compatible_with_the_csp(self):
        """script-src has no 'unsafe-inline': pages must not contain inline scripts or handlers."""
        for url in ("/", "/giris/", "/kayit/"):
            with self.subTest(url=url):
                html = self.client.get(url).content.decode()
                self.assertNotRegex(html, r"<script(?![^>]*\bsrc=)")
                self.assertIsNone(re.search(r"\son[a-z]+\s*=", html))
                self.assertNotIn("javascript:", html)
