import re
import time
from unittest import mock

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.core import mail
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from polls.models import Option, Poll, Vote

from .emails import make_verification_token

User = get_user_model()


def limits(**overrides):
    return {**settings.THROTTLE_LIMITS, **overrides}


class UserModelTests(TestCase):
    def test_create_user_with_email(self):
        user = User.objects.create_user(email="ali@example.com", username="ali", password="guclu-parola-123")
        self.assertEqual(user.email, "ali@example.com")
        self.assertEqual(user.username, "ali")
        self.assertTrue(user.check_password("guclu-parola-123"))
        self.assertFalse(user.is_staff)

    def test_email_is_lowercased(self):
        user = User.objects.create_user(email="  Ali.Veli@Example.COM ", username="aliveli", password="x")
        self.assertEqual(user.email, "ali.veli@example.com")

    def test_email_is_lowercased_on_save(self):
        user = User.objects.create_user(email="a@example.com", username="aaa", password="x")
        user.email = "BUYUK@Example.com"
        user.save()
        user.refresh_from_db()
        self.assertEqual(user.email, "buyuk@example.com")

    def test_login_with_email(self):
        User.objects.create_user(email="ali@example.com", username="ali", password="guclu-parola-123")
        self.assertIsNotNone(authenticate(email="ali@example.com", password="guclu-parola-123"))
        self.assertIsNotNone(authenticate(email="ALI@example.com", password="guclu-parola-123"))
        self.assertIsNone(authenticate(email="ali@example.com", password="yanlis"))

    def test_duplicate_email_rejected(self):
        User.objects.create_user(email="ali@example.com", username="ali", password="x")
        with self.assertRaises(IntegrityError):
            User.objects.create_user(email="ALI@example.com", username="baska", password="x")

    def test_username_unique_case_insensitive(self):
        User.objects.create_user(email="a@example.com", username="Ali", password="x")
        with self.assertRaises(IntegrityError):
            User.objects.create_user(email="b@example.com", username="ali", password="x")

    def test_username_case_insensitive_validation_message(self):
        User.objects.create_user(email="a@example.com", username="Ali", password="x")
        user = User(email="b@example.com", username="ali")
        user.set_password("x")
        with self.assertRaises(ValidationError) as ctx:
            user.full_clean()
        self.assertIn("Bu kullanıcı adı alınmış.", str(ctx.exception))

    def test_invalid_usernames_rejected(self):
        for username in ["ali veli", "şule", "ab", "a" * 21, "admin", "Yonetici"]:
            user = User(email=f"{len(username)}@example.com", username=username)
            user.set_password("x")
            with self.subTest(username=username), self.assertRaises(ValidationError):
                user.full_clean()

    def test_reserved_words_are_rejected_inside_longer_names_too(self):
        for username in ["kararsizim_destek", "admin_", "Yonetici1", "a.d.m.i.n", "Destek.Ekibi", "u_", "a_p_i"]:
            user = User(email=f"{len(username)}@example.com", username=username)
            user.set_password("x")
            with self.subTest(username=username), self.assertRaises(ValidationError):
                user.full_clean()

    def test_ordinary_names_are_still_accepted(self):
        for username in ["ali_veli.99", "ankara", "admiral", "kararli", "ugur", "sude_2026"]:
            user = User(email=f"{len(username)}@example.com", username=username)
            user.set_password("x")
            with self.subTest(username=username):
                user.full_clean()

    def test_valid_username_accepted(self):
        user = User(email="v@example.com", username="ali_veli.99")
        user.set_password("x")
        user.full_clean()

    def test_create_superuser(self):
        admin = User.objects.create_superuser(email="root@example.com", username="kok", password="x")
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)


PASSWORD = "Kararsiz-Parola-2026"


def make_user(email="ali@example.com", username="ali", password=PASSWORD):
    return User.objects.create_user(email=email, username=username, password=password)


def register_data(**overrides):
    data = {
        "username": "yeniuye",
        "email": "yeni@example.com",
        "password1": PASSWORD,
        "password2": PASSWORD,
    }
    data.update(overrides)
    return data


class RegisterViewTests(TestCase):
    url = reverse("accounts:register")

    def test_page_renders(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "E-postan kimseye gösterilmez.")
        self.assertContains(response, "Anketlerinde bu isim görünecek.")

    def test_successful_register_logs_in_and_redirects_home(self):
        response = self.client.post(self.url, register_data(email="Yeni@Example.com"))
        # Don't let assertRedirects fetch "/" — that would consume the welcome message.
        self.assertRedirects(response, "/", fetch_redirect_response=False)
        user = User.objects.get(username="yeniuye")
        self.assertEqual(user.email, "yeni@example.com")
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

        home = self.client.get("/")
        self.assertContains(home, "@yeniuye")
        self.assertContains(home, "Hoş geldin @yeniuye")
        self.assertNotContains(home, "yeni@example.com")

    def test_duplicate_email_rejected_case_insensitive(self):
        make_user(email="ali@example.com")
        response = self.client.post(self.url, register_data(email="ALI@example.com"))
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context["form"], "email", "Bu e-posta ile zaten bir hesap var.")
        self.assertEqual(User.objects.count(), 1)

    def test_duplicate_username_rejected_case_insensitive(self):
        make_user(username="Ali")
        response = self.client.post(self.url, register_data(username="ali"))
        self.assertFormError(response.context["form"], "username", "Bu kullanıcı adı alınmış.")
        self.assertEqual(response.context["form"].non_field_errors(), [])
        self.assertEqual(User.objects.count(), 1)

    def test_invalid_usernames_rejected(self):
        for username in ["ali veli", "şule", "ab"]:
            with self.subTest(username=username):
                response = self.client.post(self.url, register_data(username=username))
                self.assertFormError(
                    response.context["form"],
                    "username",
                    "3–20 karakter; sadece harf, rakam, _ ve . kullanabilirsin.",
                )
        self.assertFalse(User.objects.exists())

    def test_reserved_username_rejected(self):
        response = self.client.post(self.url, register_data(username="Admin"))
        self.assertFormError(response.context["form"], "username", "Bu kullanıcı adı kullanılamaz.")
        self.assertFalse(User.objects.exists())

    def test_password_mismatch_and_weak_password_rejected(self):
        response = self.client.post(self.url, register_data(password2="baska-bir-parola-1"))
        self.assertTrue(response.context["form"].has_error("password2"))
        response = self.client.post(self.url, register_data(password1="12345678", password2="12345678"))
        self.assertTrue(response.context["form"].has_error("password2"))
        self.assertFalse(User.objects.exists())

    def test_redirects_to_safe_next(self):
        response = self.client.post(self.url, register_data(next="/anket/yeni/"))
        self.assertRedirects(response, "/anket/yeni/", fetch_redirect_response=False)

    def test_external_next_is_ignored(self):
        response = self.client.post(self.url, register_data(next="https://evil.example.com/"))
        self.assertRedirects(response, "/")

    def test_authenticated_user_is_redirected_home(self):
        self.client.force_login(make_user())
        self.assertRedirects(self.client.get(self.url), "/")


class LoginViewTests(TestCase):
    url = reverse("accounts:login")

    def setUp(self):
        self.user = make_user()

    def test_page_renders(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Hesabın yok mu?")

    def test_login_with_email(self):
        response = self.client.post(self.url, {"email": "ALI@example.com", "password": PASSWORD})
        self.assertRedirects(response, "/")
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_wrong_password_fails(self):
        response = self.client.post(self.url, {"email": "ali@example.com", "password": "yanlis-parola"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "E-posta veya parola hatalı.")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_unknown_email_fails_with_same_message(self):
        response = self.client.post(self.url, {"email": "yok@example.com", "password": PASSWORD})
        self.assertContains(response, "E-posta veya parola hatalı.")

    def test_inactive_user_cannot_login(self):
        self.user.is_active = False
        self.user.save()
        response = self.client.post(self.url, {"email": "ali@example.com", "password": PASSWORD})
        self.assertContains(response, "E-posta veya parola hatalı.")

    def test_redirects_to_safe_next(self):
        response = self.client.post(
            self.url, {"email": "ali@example.com", "password": PASSWORD, "next": "/anket/yeni/"}
        )
        self.assertRedirects(response, "/anket/yeni/", fetch_redirect_response=False)

    def test_external_next_is_ignored(self):
        for next_url in ["https://evil.example.com/", "//evil.example.com/"]:
            with self.subTest(next_url=next_url):
                self.client.logout()
                response = self.client.post(
                    self.url, {"email": "ali@example.com", "password": PASSWORD, "next": next_url}
                )
                self.assertRedirects(response, "/")

    def test_next_is_kept_in_form(self):
        response = self.client.get(self.url + "?next=/anket/yeni/")
        self.assertContains(response, 'name="next" value="/anket/yeni/"')

    def test_authenticated_user_is_redirected_home(self):
        self.client.force_login(self.user)
        self.assertRedirects(self.client.get(self.url), "/")


class LogoutViewTests(TestCase):
    url = reverse("accounts:logout")

    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)

    def test_get_does_not_log_out(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)

    def test_post_logs_out(self):
        response = self.client.post(self.url)
        self.assertRedirects(response, "/")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_then_login_returns_same_user(self):
        self.client.post(self.url)
        self.client.post(reverse("accounts:login"), {"email": "ali@example.com", "password": PASSWORD})
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)


class SchemaCompatibilityTests(TestCase):
    def test_rows_inserted_without_email_verified_get_a_database_default(self):
        """The previous release inserts users without this column; migrating first must not break it."""
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO accounts_user (password, is_superuser, first_name, last_name, is_staff, is_active,"
                " date_joined, email, username) VALUES ('x', 0, '', '', 0, 1, %s, %s, %s)",
                [timezone.now(), "eski@example.com", "eski"],
            )
        self.assertIs(User.objects.get(username="eski").email_verified, False)


class RegisterRaceTests(TestCase):
    def test_losing_a_uniqueness_race_shows_a_form_error_not_a_500(self):
        # The pre-save checks passed, then someone else took the name/e-mail before the INSERT.
        with mock.patch("accounts.forms.RegisterForm.save", side_effect=IntegrityError):
            response = self.client.post(reverse("accounts:register"), register_data())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "az önce başkası tarafından alındı")
        self.assertFalse(User.objects.exists())


@override_settings(THROTTLE_ENABLED=True, THROTTLE_LIMITS=limits(login=(3, 900)))
class LoginIpThrottleTests(TestCase):
    url = reverse("accounts:login")

    def setUp(self):
        make_user()

    def attempt(self, password="yanlis-parola", **extra):
        return self.client.post(self.url, {"email": "ali@example.com", "password": password}, **extra)

    def test_too_many_attempts_from_one_ip_are_refused_even_with_the_right_password(self):
        self.assertEqual([self.attempt().status_code for _ in range(3)], [200, 200, 200])
        response = self.attempt(password=PASSWORD)
        self.assertContains(response, "Çok fazla deneme", status_code=429)
        self.assertTrue(1 <= int(response["Retry-After"]) <= 900)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_another_ip_is_not_affected(self):
        for _ in range(4):
            self.attempt()
        self.assertEqual(self.attempt(password=PASSWORD, REMOTE_ADDR="203.0.113.5").status_code, 302)


@override_settings(THROTTLE_ENABLED=True, THROTTLE_LIMITS=limits(**{"login-email": (3, 900)}))
class LoginEmailThrottleTests(TestCase):
    url = reverse("accounts:login")

    def setUp(self):
        make_user()
        make_user(email="veli@example.com", username="veli")

    def attempt(self, ip, email="ali@example.com", password="yanlis-parola"):
        return self.client.post(self.url, {"email": email, "password": password}, REMOTE_ADDR=ip)

    def test_guesses_against_one_account_are_limited_across_many_ips(self):
        statuses = [self.attempt(f"203.0.113.{i}", email=email).status_code
                    for i, email in enumerate(["ali@example.com", "ALI@example.com", " ali@example.com ", "Ali@Example.com"])]
        self.assertEqual(statuses, [200, 200, 200, 429])

    def test_other_accounts_are_not_affected(self):
        for i in range(4):
            self.attempt(f"203.0.113.{i}")
        self.assertEqual(self.attempt("203.0.113.99", email="veli@example.com", password=PASSWORD).status_code, 302)

    def test_blank_email_is_not_counted(self):
        statuses = {self.attempt("203.0.113.7", email="").status_code for _ in range(10)}
        self.assertEqual(statuses, {200})


@override_settings(THROTTLE_ENABLED=True, THROTTLE_LIMITS=limits(register=(2, 3600)))
class RegisterThrottleTests(TestCase):
    def test_account_spam_from_one_ip_is_limited(self):
        url = reverse("accounts:register")
        # A fresh client each time: a successful sign-up logs the previous one in.
        statuses = [self.client_class().post(url, register_data(username=f"uye{i}", email=f"u{i}@example.com")).status_code
                    for i in range(3)]
        self.assertEqual(statuses, [302, 302, 429])
        self.assertEqual(User.objects.count(), 2)


@override_settings(THROTTLE_ENABLED=True, THROTTLE_LIMITS=limits(**{"admin-login": (2, 900)}))
class AdminLoginThrottleTests(TestCase):
    def test_admin_login_attempts_are_limited(self):
        data = {"username": "root@example.com", "password": "yanlis", "next": "/admin/"}
        statuses = [self.client.post("/admin/login/", data).status_code for _ in range(3)]
        self.assertEqual(statuses, [200, 200, 429])


class NavbarTests(TestCase):
    def test_anonymous_sees_login_and_register(self):
        response = self.client.get("/")
        self.assertContains(response, "Giriş yap")
        self.assertContains(response, "Kayıt ol")
        self.assertNotContains(response, "Çıkış")

    def test_member_sees_username_not_email(self):
        self.client.force_login(make_user())
        response = self.client.get("/")
        self.assertContains(response, "@ali")
        self.assertContains(response, "Anket oluştur")
        self.assertContains(response, "Çıkış")
        self.assertNotContains(response, "ali@example.com")


class AccountDeleteTests(TestCase):
    url = reverse("accounts:delete")

    def setUp(self):
        self.user = make_user()
        self.other = make_user(email="veli@example.com", username="veli")
        self.my_poll = Poll.objects.create(author=self.user, question="Benim anketim burada")
        my_options = [Option.objects.create(poll=self.my_poll, text=t, position=i) for i, t in enumerate("AB")]
        self.their_poll = Poll.objects.create(author=self.other, question="Veli'nin anketi burada")
        their_options = [Option.objects.create(poll=self.their_poll, text=t, position=i) for i, t in enumerate("CD")]
        Vote.objects.create(poll=self.my_poll, option=my_options[0], voter_token="ziyaretci")  # someone else's vote
        Vote.objects.create(poll=self.their_poll, option=their_options[0], user=self.user)  # my vote
        Vote.objects.create(poll=self.their_poll, option=their_options[1], user=self.other)
        self.client.force_login(self.user)

    def test_login_is_required(self):
        self.client.logout()
        self.assertRedirects(self.client.get(self.url), f"/giris/?next={self.url}")
        self.assertRedirects(self.client.post(self.url, {"password": PASSWORD}), f"/giris/?next={self.url}")
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_page_warns_and_asks_for_the_password(self):
        response = self.client.get(self.url)
        self.assertContains(response, "kalıcı olarak silinecek")
        self.assertContains(response, 'type="password"')
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_wrong_password_deletes_nothing(self):
        response = self.client.post(self.url, {"password": "yanlis-parola"})
        self.assertContains(response, "Parola hatalı.")
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())
        self.assertIn("_auth_user_id", self.client.session)

    def test_correct_password_removes_the_account_its_polls_and_votes(self):
        response = self.client.post(self.url, {"password": PASSWORD})
        self.assertRedirects(response, "/", fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())
        self.assertFalse(Poll.objects.filter(pk=self.my_poll.pk).exists())
        self.assertFalse(Vote.objects.filter(poll=self.my_poll).exists())
        self.assertContains(self.client.get("/"), "Hesabın ve tüm verilerin silindi")

    def test_other_members_data_is_untouched(self):
        self.client.post(self.url, {"password": PASSWORD})
        self.assertTrue(User.objects.filter(pk=self.other.pk).exists())
        self.assertTrue(Poll.objects.filter(pk=self.their_poll.pk).exists())
        self.assertEqual(Vote.objects.filter(poll=self.their_poll).count(), 1)

    @override_settings(THROTTLE_ENABLED=True, THROTTLE_LIMITS=limits(**{"account-delete": (2, 3600)}))
    def test_password_guessing_here_is_limited(self):
        statuses = [self.client.post(self.url, {"password": f"yanlis-{i}"}).status_code for i in range(3)]
        self.assertEqual(statuses, [200, 200, 429])
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())


class PrivacyPageTests(TestCase):
    url = reverse("privacy")

    def test_page_is_public_and_explains_what_is_stored(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        for expected in ("Gizlilik Bildirimi", "kz_voter", "sessionid", "csrftoken", "Supabase", "Vercel", "Hesabımı sil"):
            self.assertContains(response, expected)

    @override_settings(CONTACT_EMAIL="gizlilik@example.com")
    def test_contact_address_is_shown_when_configured(self):
        self.assertContains(self.client.get(self.url), "gizlilik@example.com")

    @override_settings(CONTACT_EMAIL="")
    def test_no_contact_section_without_a_configured_address(self):
        self.assertNotContains(self.client.get(self.url), "mailto:")

    def test_footer_links_to_it_everywhere(self):
        for url in ("/", "/giris/", "/kayit/", self.url, "/yok-boyle-bir-sayfa/"):
            with self.subTest(url=url):
                self.assertContains(self.client.get(url), f'href="{self.url}"', status_code=200 if url != "/yok-boyle-bir-sayfa/" else 404)

    def test_register_form_points_to_it(self):
        self.assertContains(self.client.get(reverse("accounts:register")), "Gizlilik Bildirimi")

    def test_delete_link_in_footer_only_for_members(self):
        self.assertNotContains(self.client.get("/"), reverse("accounts:delete"))
        self.client.force_login(make_user())
        self.assertContains(self.client.get("/"), reverse("accounts:delete"))


NEW_PASSWORD = "Yepyeni-Parola-2027"


def emailed_link(message, prefix):
    return re.search(rf"http://testserver({re.escape(prefix)}\S+)", message.body).group(1)


@override_settings(EMAIL_FEATURES_ENABLED=True)
class PasswordResetTests(TestCase):
    url = reverse("accounts:password_reset")
    done_url = reverse("accounts:password_reset_done")

    def setUp(self):
        self.user = make_user()

    def reset_password_with(self, link, password=NEW_PASSWORD):
        response = self.client.get(link, follow=True)
        set_url = response.redirect_chain[-1][0]
        return self.client.post(set_url, {"new_password1": password, "new_password2": password})

    def test_login_page_links_to_the_reset_form(self):
        self.assertContains(self.client.get(reverse("accounts:login")), f'href="{self.url}"')

    def test_known_address_gets_a_mail_and_can_choose_a_new_password(self):
        response = self.client.post(self.url, {"email": "ALI@example.com"})
        self.assertRedirects(response, self.done_url)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["ali@example.com"])
        self.assertIn("Parolanı sıfırla", message.subject)

        done = self.reset_password_with(emailed_link(message, "/parola/sifirla/"))
        self.assertRedirects(done, reverse("accounts:password_reset_complete"))
        self.assertIsNotNone(authenticate(email="ali@example.com", password=NEW_PASSWORD))
        self.assertIsNone(authenticate(email="ali@example.com", password=PASSWORD))

    def test_unknown_address_looks_the_same_and_sends_nothing(self):
        response = self.client.post(self.url, {"email": "yok@example.com"})
        self.assertRedirects(response, self.done_url)
        self.assertEqual(mail.outbox, [])

    def test_inactive_account_gets_no_mail(self):
        self.user.is_active = False
        self.user.save()
        self.client.post(self.url, {"email": "ali@example.com"})
        self.assertEqual(mail.outbox, [])

    def test_a_link_works_only_once(self):
        self.client.post(self.url, {"email": "ali@example.com"})
        link = emailed_link(mail.outbox[0], "/parola/sifirla/")
        self.reset_password_with(link)
        again = self.client.get(link, follow=True)
        self.assertContains(again, "bağlantı geçersiz")

    def test_a_reset_proves_ownership_of_the_address(self):
        self.assertFalse(User.objects.get().email_verified)
        self.client.post(self.url, {"email": "ali@example.com"})
        self.reset_password_with(emailed_link(mail.outbox[0], "/parola/sifirla/"))
        self.assertTrue(User.objects.get().email_verified)

    def test_a_weak_new_password_is_rejected(self):
        self.client.post(self.url, {"email": "ali@example.com"})
        response = self.reset_password_with(emailed_link(mail.outbox[0], "/parola/sifirla/"), password="12345678")
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(authenticate(email="ali@example.com", password=PASSWORD))

    @override_settings(THROTTLE_ENABLED=True, THROTTLE_LIMITS=limits(**{"password-reset-email": (2, 3600)}))
    def test_one_address_cannot_be_mail_bombed(self):
        statuses = [self.client.post(self.url, {"email": "ali@example.com"}).status_code for _ in range(3)]
        self.assertEqual(statuses, [302, 302, 429])
        self.assertEqual(len(mail.outbox), 2)

    @override_settings(THROTTLE_ENABLED=True, THROTTLE_LIMITS=limits(**{"password-reset": (2, 3600)}))
    def test_requests_from_one_ip_are_limited(self):
        statuses = [self.client.post(self.url, {"email": f"x{i}@example.com"}).status_code for i in range(3)]
        self.assertEqual(statuses, [302, 302, 429])

    @override_settings(EMAIL_FEATURES_ENABLED=False)
    def test_unavailable_without_a_mail_server(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse("accounts:login"), fetch_redirect_response=False)
        self.assertNotContains(self.client.get(reverse("accounts:login")), self.url)

    def test_duplicate_email_error_offers_the_reset(self):
        response = self.client.post(reverse("accounts:register"), register_data(email="ali@example.com"))
        self.assertContains(response, "Bu e-posta ile zaten bir hesap var.")
        self.assertContains(response, f'href="{self.url}"')

    @override_settings(EMAIL_FEATURES_ENABLED=False)
    def test_duplicate_email_error_has_no_offer_when_resets_are_unavailable(self):
        response = self.client.post(reverse("accounts:register"), register_data(email="ali@example.com"))
        self.assertNotContains(response, self.url)


@override_settings(EMAIL_FEATURES_ENABLED=True)
class EmailVerificationTests(TestCase):
    resend_url = reverse("accounts:resend_verification")

    def setUp(self):
        self.user = make_user()

    def link(self, user=None):
        return reverse("accounts:verify_email", args=[make_verification_token(user or self.user)])

    def test_new_members_start_unverified(self):
        self.assertFalse(self.user.email_verified)

    def test_superusers_are_created_verified(self):
        admin = User.objects.create_superuser(email="root@example.com", username="kok", password="x")
        self.assertTrue(admin.email_verified)

    def test_registration_sends_a_verification_mail(self):
        self.client.post(reverse("accounts:register"), register_data())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["yeni@example.com"])
        link = emailed_link(mail.outbox[0], "/e-posta/dogrula/")
        self.assertRedirects(self.client.get(link), "/")
        self.assertTrue(User.objects.get(username="yeniuye").email_verified)

    def test_the_link_verifies_the_address(self):
        response = self.client.get(self.link())
        self.assertRedirects(response, "/", fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertTrue(self.user.email_verified)
        self.assertContains(self.client.get("/"), "E-postan doğrulandı")

    def test_a_bad_token_does_nothing(self):
        response = self.client.get(reverse("accounts:verify_email", args=["sahte-bir-kod"]))
        self.assertRedirects(response, "/", fetch_redirect_response=False)
        self.assertContains(self.client.get("/"), "geçersiz ya da süresi dolmuş")
        self.user.refresh_from_db()
        self.assertFalse(self.user.email_verified)

    def test_an_old_token_expires(self):
        link = self.link()
        with mock.patch("django.core.signing.time.time", return_value=time.time() + 4 * 24 * 3600):
            self.client.get(link)
        self.user.refresh_from_db()
        self.assertFalse(self.user.email_verified)

    def test_a_token_for_an_address_the_account_no_longer_has_is_rejected(self):
        link = self.link()
        self.user.email = "baska@example.com"
        self.user.save()
        self.client.get(link)
        self.user.refresh_from_db()
        self.assertFalse(self.user.email_verified)

    def test_unverified_members_cannot_open_polls(self):
        self.client.force_login(self.user)
        for method in (self.client.get, self.client.post):
            response = method(reverse("polls:create"))
            self.assertContains(response, "doğrula", status_code=403)
        self.assertFalse(Poll.objects.exists())

    def test_verified_members_can_open_polls(self):
        self.user.email_verified = True
        self.user.save()
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("polls:create")).status_code, 200)

    def test_unverified_members_can_still_vote(self):
        poll = Poll.objects.create(author=make_user("sahip", "sahip@example.com"), question="Sinema mı restoran mı?")
        option = Option.objects.create(poll=poll, text="Sinema", position=0)
        Option.objects.create(poll=poll, text="Restoran", position=1)
        self.client.force_login(self.user)
        response = self.client.post(reverse("polls:vote", args=[poll.pk]), {"option_id": option.pk})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Vote.objects.count(), 1)

    def test_banner_with_resend_button_only_for_unverified_members(self):
        self.assertNotContains(self.client.get("/"), "tekrar gönder")
        self.client.force_login(self.user)
        self.assertContains(self.client.get("/"), "Doğrulama e-postasını tekrar gönder")
        self.user.email_verified = True
        self.user.save()
        self.assertNotContains(self.client.get("/"), "tekrar gönder")

    def test_resend_sends_a_fresh_mail(self):
        self.client.force_login(self.user)
        response = self.client.post(self.resend_url)
        self.assertRedirects(response, "/", fetch_redirect_response=False)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["ali@example.com"])

    def test_resend_for_a_verified_member_sends_nothing(self):
        self.user.email_verified = True
        self.user.save()
        self.client.force_login(self.user)
        self.client.post(self.resend_url)
        self.assertEqual(mail.outbox, [])

    def test_resend_needs_login_and_post(self):
        self.assertRedirects(self.client.post(self.resend_url), f"/giris/?next={self.resend_url}")
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.resend_url).status_code, 405)

    @override_settings(THROTTLE_ENABLED=True, THROTTLE_LIMITS=limits(**{"verify-mail": (2, 3600)}))
    def test_resend_is_limited(self):
        self.client.force_login(self.user)
        statuses = [self.client.post(self.resend_url).status_code for _ in range(3)]
        self.assertEqual(statuses, [302, 302, 429])
        self.assertEqual(len(mail.outbox), 2)

    def test_registration_survives_a_broken_mail_server(self):
        with mock.patch("accounts.emails.send_mail", side_effect=OSError("smtp down")), self.assertLogs(
            "accounts.views", level="ERROR"
        ):
            response = self.client.post(reverse("accounts:register"), register_data())
        self.assertRedirects(response, "/", fetch_redirect_response=False)
        self.assertTrue(User.objects.filter(username="yeniuye").exists())
        self.assertContains(self.client.get("/"), "gönderilemedi")

    @override_settings(EMAIL_FEATURES_ENABLED=False)
    def test_nothing_changes_while_no_mail_server_is_configured(self):
        self.client.post(reverse("accounts:register"), register_data())
        self.assertEqual(mail.outbox, [])
        self.assertEqual(self.client.get(reverse("polls:create")).status_code, 200)
        self.assertNotContains(self.client.get("/"), "tekrar gönder")
        self.assertEqual(self.client.post(self.resend_url).status_code, 404)
        self.assertEqual(self.client.get(self.link()).status_code, 404)

