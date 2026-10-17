import uuid

from django.db import models


class TripPreset(models.Model):
    """A ready-made trip shown in the UI so reviewers can try the app in one click."""

    name = models.CharField(max_length=100, unique=True)
    origin_label = models.CharField(max_length=200)
    origin_lat = models.FloatField()
    origin_lon = models.FloatField()
    destination_label = models.CharField(max_length=200)
    destination_lat = models.FloatField()
    destination_lon = models.FloatField()
    load_lb = models.PositiveIntegerField()
    interval_miles = models.PositiveSmallIntegerField(default=25)
    simulate_storm = models.BooleanField(default=False)
    description = models.CharField(max_length=300, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name


class TripPlan(models.Model):
    """A computed plan. Stored so results can be shared by link and reopened."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    origin_label = models.CharField(max_length=200)
    origin_lat = models.FloatField()
    origin_lon = models.FloatField()
    destination_label = models.CharField(max_length=200)
    destination_lat = models.FloatField()
    destination_lon = models.FloatField()
    departure = models.DateTimeField()
    load_lb = models.PositiveIntegerField()
    interval_miles = models.PositiveSmallIntegerField()
    simulate_storm = models.BooleanField(default=False)
    result = models.JSONField()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.origin_label} → {self.destination_label} ({self.departure:%Y-%m-%d %H:%M})"
