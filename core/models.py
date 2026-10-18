from django.db import models


class ThrottleBucket(models.Model):
    """Request counter for one (scope, identifier, time window); see core.throttle."""

    key = models.CharField(max_length=64, unique=True)
    count = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(db_index=True)
