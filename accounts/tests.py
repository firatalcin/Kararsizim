from django.contrib.auth import authenticate, get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

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

