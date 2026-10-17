from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from trips.models import TripPlan, TripPreset
from trips.planner import SAMPLE_INTERVALS_MILES

MAX_DEPARTURE_DAYS_AHEAD = 7  # forecast quality drops fast after a week
MAX_LOAD_LB = 120_000


def place_json(obj, prefix: str) -> dict:
    """Pack the flat `<prefix>_label/_lat/_lon` model fields into one object."""
    return {
        "label": getattr(obj, f"{prefix}_label"),
        "lat": getattr(obj, f"{prefix}_lat"),
        "lon": getattr(obj, f"{prefix}_lon"),
    }


class PlaceSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=200)
    lat = serializers.FloatField(min_value=-90, max_value=90)
    lon = serializers.FloatField(min_value=-180, max_value=180)


class PlanRequestSerializer(serializers.Serializer):
    origin = PlaceSerializer()
    destination = PlaceSerializer()
    departure = serializers.DateTimeField()
    load_lb = serializers.IntegerField(min_value=0, max_value=MAX_LOAD_LB)
    interval_miles = serializers.ChoiceField(choices=SAMPLE_INTERVALS_MILES, default=25)
    simulate_storm = serializers.BooleanField(default=False)

    def validate_departure(self, value):
        now = timezone.now()
        if value < now - timedelta(hours=1):
            raise serializers.ValidationError("Departure can't be in the past.")
        if value > now + timedelta(days=MAX_DEPARTURE_DAYS_AHEAD):
            raise serializers.ValidationError(
                f"Departure must be within {MAX_DEPARTURE_DAYS_AHEAD} days to get a forecast."
            )
        return value

    def validate(self, attrs):
        o, d = attrs["origin"], attrs["destination"]
        if abs(o["lat"] - d["lat"]) < 1e-3 and abs(o["lon"] - d["lon"]) < 1e-3:
            raise serializers.ValidationError("Origin and destination are the same place.")
        return attrs


class TripPlanSerializer(serializers.ModelSerializer):
    origin = serializers.SerializerMethodField()
    destination = serializers.SerializerMethodField()

    class Meta:
        model = TripPlan
        fields = [
            "id",
            "created_at",
            "origin",
            "destination",
            "departure",
            "load_lb",
            "interval_miles",
            "simulate_storm",
            "result",
        ]

    def get_origin(self, obj):
        return place_json(obj, "origin")

    def get_destination(self, obj):
        return place_json(obj, "destination")


class TripPlanListSerializer(TripPlanSerializer):
    class Meta(TripPlanSerializer.Meta):
        fields = [f for f in TripPlanSerializer.Meta.fields if f != "result"]


class TripPresetSerializer(serializers.ModelSerializer):
    origin = serializers.SerializerMethodField()
    destination = serializers.SerializerMethodField()

    class Meta:
        model = TripPreset
        fields = [
            "id",
            "name",
            "description",
            "origin",
            "destination",
            "load_lb",
            "interval_miles",
            "simulate_storm",
        ]

    def get_origin(self, obj):
        return place_json(obj, "origin")

    def get_destination(self, obj):
        return place_json(obj, "destination")
