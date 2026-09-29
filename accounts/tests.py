from django.contrib.auth import authenticate, get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


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

