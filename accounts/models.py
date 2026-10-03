import zlib

from django.contrib.auth.models import AbstractUser, UserManager as DjangoUserManager
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.functions import Lower

RESERVED_USERNAMES = {
    "admin",
    "yonetici",
    "kararsizim",
    "anket",
    "giris",
    "kayit",
    "cikis",
    "api",
    "static",
    "u",
    "destek",
}

username_format_validator = RegexValidator(
    regex=r"^[A-Za-z0-9_.]{3,20}\Z",
    message="3–20 karakter; sadece harf, rakam, _ ve . kullanabilirsin.",
)


def validate_username_not_reserved(value):
    if value.lower() in RESERVED_USERNAMES:
        raise ValidationError("Bu kullanıcı adı kullanılamaz.")


class UserManager(DjangoUserManager):
    """Manager for a user model that logs in with email instead of username."""

    def _create_user(self, username, email, password, **extra_fields):
        if not email:
            raise ValueError("Email is required.")
        if not username:
            raise ValueError("Username is required.")
        user = self.model(username=username, email=email.strip().lower(), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, username, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(username, email, password, **extra_fields)

    def create_superuser(self, email, username, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(username, email, password, **extra_fields)

    def get_by_natural_key(self, email):
        return self.get(email__iexact=email)


class User(AbstractUser):
    email = models.EmailField(
        "e-posta",
        unique=True,
        error_messages={"unique": "Bu e-posta ile zaten bir hesap var."},
    )
    username = models.CharField(
        "kullanıcı adı",
        max_length=20,
        validators=[username_format_validator, validate_username_not_reserved],
        help_text="3–20 karakter; harf, rakam, _ ve . kullanabilirsin. Anketlerinde bu isim görünecek.",
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    objects = UserManager()

    class Meta:
        verbose_name = "kullanıcı"
        verbose_name_plural = "kullanıcılar"
        constraints = [
            models.UniqueConstraint(
                Lower("username"),
                name="unique_username_ci",
                violation_error_message="Bu kullanıcı adı alınmış.",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.username

    @property
    def avatar_color(self):
        # Deterministic across processes (unlike hash()); matches the option colour names.
        colors = ("violet", "pink", "orange", "teal", "sky")
        return colors[zlib.crc32(self.username.lower().encode()) % len(colors)]
