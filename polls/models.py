from django.conf import settings
from django.core.validators import MinLengthValidator
from django.db import models
from django.db.models import Q
from django.urls import reverse

# Option colours by position (see the design guide); CSS classes use these names.
OPTION_COLORS = ["violet", "pink", "orange", "teal", "sky"]
MAX_OPTIONS = len(OPTION_COLORS)
MIN_OPTIONS = 2


class Poll(models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="polls")
    question = models.CharField(
        "soru",
        max_length=200,
        validators=[MinLengthValidator(5, "Soru en az 5 karakter olmalı.")],
    )
    description = models.CharField("açıklama", max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "anket"
        verbose_name_plural = "anketler"

    def __str__(self):
        return self.question

    def get_absolute_url(self):
        return reverse("polls:detail", args=[self.pk])


class Option(models.Model):
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name="options")
    text = models.CharField("seçenek", max_length=80)
    position = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["position"]
        verbose_name = "seçenek"
        verbose_name_plural = "seçenekler"
        constraints = [
            models.UniqueConstraint(fields=["poll", "position"], name="unique_option_position"),
            models.CheckConstraint(condition=Q(position__lt=MAX_OPTIONS), name="option_position_range"),
        ]

    def __str__(self):
        return self.text

    @property
    def color(self):
        return OPTION_COLORS[self.position % MAX_OPTIONS]


class Vote(models.Model):
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name="votes")
    option = models.ForeignKey(Option, on_delete=models.CASCADE, related_name="votes")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name="votes"
    )
    voter_token = models.CharField(max_length=64, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "oy"
        verbose_name_plural = "oylar"
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(user__isnull=False, voter_token__isnull=True)
                    | Q(user__isnull=True, voter_token__isnull=False)
                ),
                name="vote_user_xor_voter_token",
            ),
            models.UniqueConstraint(
                fields=["poll", "user"], condition=Q(user__isnull=False), name="one_vote_per_user"
            ),
            models.UniqueConstraint(
                fields=["poll", "voter_token"], condition=Q(voter_token__isnull=False), name="one_vote_per_visitor"
            ),
        ]

    def __str__(self):
        return f"{self.poll_id} → {self.option_id}"
